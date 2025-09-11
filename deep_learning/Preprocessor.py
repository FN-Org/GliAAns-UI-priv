import glob
import shutil
from os import mkdir

import numpy as np
import monai.transforms as transforms
import json
import math
import os
import pickle
import nibabel

from joblib import Parallel, delayed
from subprocess import run


# inspired by the NVIDIA nnU-Net GitHub repository available at:
# https://github.com/NVIDIA/DeepLearningExamples/tree/master/PyTorch/Segmentation/nnUNet

# preprocessing makes use of the MONAI toolkit available at:
# https://github.com/Project-MONAI/MONAI


# configs
task = {
    "train": "BraTS2021_train",
    "val": "BraTS2021_val",
}


class Preprocessor:
    def __init__(self, args):
        """
        Initialize the preprocessor.
        :param args: args
        """
        self.args = args
        self.target_spacing = [1.0, 1.0, 1.0]
        # get task (here either "train" or "val" for BraTS21 training and validating respectively)
        self.task = args.task
        # get task code
        self.task_code = f"{args.task}_{args.dim}d"
        self.verbose = args.verbose
        self.patch_size = [128, 128, 128]
        # determine if training
        self.training = args.exec_mode == "training"
        self.results = os.path.join(args.results, self.task_code)
        self.ct_min, self.ct_max, self.ct_mean, self.ct_std = (0,) * 4
        if not self.training:
            self.results = os.path.join(self.results, self.args.exec_mode)
        # MONAI foreground cropping
        self.crop_foreg = transforms.CropForegroundd(keys=["image", "label"], source_key="image")
        # normalize only non-zero region for MRI
        self.normalize_intensity = transforms.NormalizeIntensity(nonzero=True, channel_wise=True)

    def run(self):
        """
        Apply preprocessing step.
        """
        nifti_paths = glob.glob(os.path.join(self.args.data, "**", "*.nii"), recursive=True)
        nifti_paths += glob.glob(os.path.join(self.args.data, "**", "*.nii.gz"), recursive=True)
        print(nifti_paths)

        Parallel(n_jobs=os.cpu_count())(
            delayed(self.prepare_nifti)(img) for img in nifti_paths
        )

        # make directory for results
        shutil.rmtree(self.results, ignore_errors=True)
        os.makedirs(self.results)
        print(f"Preprocessing {self.args.data}")
        if self.verbose:
            print(f"Target spacing {self.target_spacing}")

        nifti_paths = glob.glob(os.path.join(self.args.data, "..", "prepared", "**","*.nii"), recursive=True)
        nifti_paths += glob.glob(os.path.join(self.args.data, "..", "prepared", "**", "*.nii.gz"), recursive=True)
        print(nifti_paths)

        self.run_parallel(self.preprocess_pair, nifti_paths)
        # create pickle with infos
        pickle.dump(
            {
                "patch_size": self.patch_size,
                "spacings": self.target_spacing,
                "n_class": 2, # len(self.metadata["labels"])
                "in_channels": 1 + int(self.args.ohe), # len(self.metadata["modality"]) + int(self.args.ohe)
            },
            open(os.path.join(self.results, "config.pkl"), "wb"),
        )

    def preprocess_pair(self, img):
        """
        Preprocess a pair (image path, label path) and save them as numpy array.
        :param img: image path
        """
        fname = os.path.basename(img)
        print(fname)
        image, label, image_spacings = self.load_img(img)

        # Crop foreground and store original shapes
        orig_shape = image.shape[1:]
        bbox = transforms.utils.generate_spatial_bounding_box(image)
        image = transforms.SpatialCrop(roi_start=bbox[0], roi_end=bbox[1])(image)
        image_metadata = np.vstack([bbox, orig_shape, image.shape[1:]])
        if label is not None:
            label = transforms.SpatialCrop(roi_start=bbox[0], roi_end=bbox[1])(label)
            self.save_npy(label, fname, "_orig_lbl.npy")

        # Normalize intensities
        image = self.normalize(image)
        if self.training:
            image, label = self.standardize(image, label)

        if self.args.ohe:
            # one hot encoding
            mask = np.ones(image.shape[1:], dtype=np.float32)
            for i in range(image.shape[0]):
                zeros = np.where(image[i] <= 0)
                mask[zeros] *= 0.0
            image = self.normalize_intensity(image).astype(np.float32)
            mask = np.expand_dims(mask, 0)
            image = np.concatenate([image, mask])

        self.save(image, label, fname, image_metadata)

    def prepare_nifti(self, image):
        """
        Prepare stacked NIfTI containing all modalities.
        If present, convert segmentation to uint8 and assign label 3 to enhancing tumor (BraTS assigns 4 by default).
        :param directory: patient file directory
        :param modalities: iterable with patient scan modalities. Choose one or more between ("flair", "t1", "t1ce", "t2")
        """
        scan = nibabel.load(image)

        # retrieve homogeneous affine and header metadata
        affine = scan.affine
        header = scan.header

        # stack modalities, create NIfTI and save it
        dataobj = np.stack([self.get_data(nifti=scan)], axis=-1)
        img = nibabel.nifti1.Nifti1Image(dataobj=dataobj, affine=affine, header=header)
        directory = os.path.join(self.args.data, "..", "prepared")
        os.makedirs(directory, exist_ok=True)
        nibabel.save(img=img, filename=os.path.join(directory, os.path.basename(image)))

    def get_data(self, nifti, dtype="int16"):
        """
        Retrieve NIfTI file data as numpy array.
        :param nifti: NIfTI file
        :param dtype: numpy matrix dtype (default "int16". If different, "uint8" is used)
        :return: NIfTI file data as numpy array
        """
        if dtype == "int16":
            data = np.abs(nifti.get_fdata().astype(np.int16))
            data[data == -32768] = 0  # outlier value
            return data

        return nifti.get_fdata().astype(np.uint8)

    def standardize(self, image, label):
        """
        Standardize image and label format, so the shape is for sure grater than the patch size.
        :param image: image
        :param label: label
        :return: standardized image, standardized label (i.e. eventually padded)
        """
        pad_shape = self.calculate_pad_shape(image)
        image_shape = image.shape[1:]
        if pad_shape != image_shape:
            paddings = [(pad_sh - image_sh) / 2 for (pad_sh, image_sh) in zip(pad_shape, image_shape)]
            image = self.pad(image, paddings)
            label = self.pad(label, paddings)

        return image, label

    def normalize(self, image):
        """
        Normalize image intensity.
        :param image: image
        :return: normalized image
        """
        return self.normalize_intensity(image)

    def save(self, image, label, fname, image_metadata):
        """
        Save image and label with respective metadata as numpy array.
        :param image: image
        :param label: label
        :param fname: file name
        :param image_metadata: image metadata
        """
        mean = np.round(np.mean(image, (1, 2, 3)), 2)
        std = np.round(np.std(image, (1, 2, 3)), 2)
        if self.verbose:
            print(f"Saving {fname} shape {image.shape} mean {mean} std {std}")
        # save all you need as numpy files
        self.save_npy(image, fname, "_x.npy")
        if label is not None:
            self.save_npy(label, fname, "_y.npy")
        if image_metadata is not None:
            self.save_npy(image_metadata, fname, "_meta.npy")

    def load_img(self, img):
        """
        Load image, label and spacings from previously saved NIfTI.
        :param pair: (image path, label path) if training, just image path otherwise
        :return: image, label, image_spacing
        """
        image = self.load_nifti(img)
        # load spacing
        image_spacing = image.header["pixdim"][1:4].tolist()[::-1]
        image = image.get_fdata().astype(np.float32)
        print(f"Loaded image shape: {image.shape}")

        # standardize layout in (C, D, H, W)
        image = np.transpose(image, (3, 2, 1, 0))

        label = None

        return image, label, image_spacing

    def calculate_pad_shape(self, image):
        """
        Compute the pad needed for an image.
        :param image: image
        :return: needed pad shape
        """
        min_shape = self.patch_size[:]
        image_shape = image.shape[1:]
        pad_shape = [max(mshape, ishape) for mshape, ishape in zip(min_shape, image_shape)]

        return pad_shape

    def save_npy(self, image, fname, suffix):
        """
        Save the result image as numpy file.
        :param image: image
        :param fname: file name
        :param suffix: file suffix
        """
        np.save(os.path.join(self.results, fname.replace(".nii.gz", suffix)), image, allow_pickle=False)

    def run_parallel(self, func, img_list):
        """
        Run parallelized jobs.
        :param func: function
        :param img_list: list of images
        :return: joblib.Parallel() call
        """
        return Parallel(n_jobs=self.args.n_jobs)(delayed(func)(img) for img in img_list)

    def load_nifti(self, img):
        """
        Load a NIfTI file.
        :return: loaded NIfTI data
        """
        return nibabel.load(img)

    @staticmethod
    def pad(image, padding):
        """
        Retrieve the pad for an image.
        :param image: image
        :param padding: padding
        :return: numpy.array with required pad
        """
        pad_d, pad_w, pad_h = padding

        return np.pad(
            image,
            (
                (0, 0),
                (math.floor(pad_d), math.ceil(pad_d)),
                (math.floor(pad_w), math.ceil(pad_w)),
                (math.floor(pad_h), math.ceil(pad_h)),
            ),
        )
