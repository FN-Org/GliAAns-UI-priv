import sys

import numpy as np
import nibabel as nib
import os

from glob import glob
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pediatric_fdopa_pipeline.utils import align, transform


# inspired by the NVIDIA nnU-Net GitHub repository available at:
# https://github.com/NVIDIA/DeepLearningExamples/tree/master/PyTorch/Segmentation/nnUNet


def back_to_original_labels(pred):
    """
    Convert back the triplet (ET, TC, WT) to the original (NCR, ED, ET) for a given prdiction.
    :param pred: prediction
    :param preop: boolean value to check if postprocessing is applied for pre-operative segmentation.
    :return: converted prediction
    """
    bin_pred = (pred > 0.40).astype(np.uint8)
    if (np.sum(bin_pred == 1)) == 0:
        bin_pred = (pred > 0.30).astype(np.uint8)

    # transpose to fit BraTS orientation
    bin_pred = np.transpose(bin_pred, (2, 1, 0)).astype(np.uint8)

    return bin_pred


def prepare_predictions(preds, output_dir):
    saved_files = []
    for pred in preds:
        fname = os.path.basename(pred).split(".")[0]
        pred_npy = np.load(pred)
        pred_mean = np.mean(pred_npy, axis=0)

        # convert back to original BraTS labels
        p = back_to_original_labels(pred_mean)

        # save as NIfTI
        img = nib.load(f"/mnt/c/Users/nicol/Desktop/codice_per_DL/prepared/{fname}.nii.gz")
        out_path = os.path.join(output_dir, f"{fname}-seg.nii.gz")
        nib.save(
            nib.Nifti1Image(p, img.affine, header=img.header),
            out_path,
        )
        saved_files.append(out_path)

    return saved_files


# === CLI ARGUMENTS ===
parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument(
    "-i", "--input", type=str, required=True,
    help="Directory containing prediction .npy files"
)
parser.add_argument(
    "-o", "--output", type=str, required=True,
    help="Directory where to save the final NIfTI predictions"
)
parser.add_argument(
    "--mri", type=str, required=True,
    help="Original FLAIR mri"
)

if __name__ == "__main__":
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # search for all npy files inside the input directory
    preds = glob(os.path.join(args.input, "**", "*.npy"), recursive=True)

    if not preds:
        raise RuntimeError(f"No .npy prediction files found in {args.input}")

    print(f"Preparing final predictions from {len(preds)} files...")

    # === FASE 1: FROM NPY TO NIFTI ===
    save_preds = prepare_predictions(preds, output_dir=args.output)

    # === FASE 2: FROM BRATS TO MRI ===
    mri = args.mri # Flair originale
    mrib = save_preds[0]
    atlas_brats = "pediatric_fdopa_pipeline/atlas/T1.nii.gz"
    prefix = ".workspace/outputs/nifti/"

    os.makedirs(os.path.dirname(prefix), exist_ok=True)

    mri_space_mrib, mrib_space_mri, mrib2mri_tfm, mri2mrib_tfm = align(
        mri, atlas_brats,
        transform_method='SyNAggro',
        outprefix=f'_mrib2mri_Rigid_'
    )

    new_mri = transform(prefix, mri, mrib, mrib2mri_tfm)

    print("Finished!")