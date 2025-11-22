import re
import shutil
import sys
from pathlib import Path

import numpy as np
import nibabel as nib
import os

from glob import glob
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser

from utils.coreg import align, transform

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


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


def prepare_predictions(preds, brats, output_dir):
    saved_files = []
    for pred in preds:
        fname = os.path.basename(pred).split(".")[0]
        pred_npy = np.load(pred)
        pred_mean = np.mean(pred_npy, axis=0)

        # convert back to original BraTS labels
        p = back_to_original_labels(pred_mean)

        # save as NIfTI
        img = nib.load(brats)
        out_path = os.path.join(output_dir, f"{fname}-seg.nii.gz")
        nib.save(
            nib.Nifti1Image(p, img.affine, header=img.header),
            out_path,
        )
        saved_files.append(out_path)

    return saved_files

def extract_subject_id(filepath):
    """
    Estrae il subject ID da un filepath con pattern sub-*_*_flair.nii(.gz)

    Args:
        filepath (str): Path del file MRI flair

    Returns:
        str: Subject ID (es. "sub-01") o None se non trovato
    """
    # Estrai solo il nome del file dal path completo
    filename = os.path.basename(filepath)

    # Pattern per match: sub-qualcosa_qualcosa_flair.nii(.gz)
    pattern = r'^(sub-[^_]+).*_flair\.nii(\.gz)?$'

    match = re.match(pattern, filename)
    if match:
        return match.group(1)  # Ritorna solo il gruppo sub-*
    else:
        return None

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
    "--w", type=str, required=True,
    help="Workspace path"
)
parser.add_argument(
    "--atlas", type=str, required=True,
    help="T1 atlas"
)
parser.add_argument(
    "--brats", type=str, required=False,
    default=os.path.join("deep_learning", "atlas", "BraTS-GLI-01-001.nii"),
    help="File BraTS di riferimento (default: BraTS-GLI-01-001.nii nel repo)"
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
    brats_reference_path = args.brats
    save_preds = prepare_predictions(preds, brats_reference_path, output_dir=args.output)

    # === FASE 2: FROM BRATS TO MRI ===
    mri = args.mri # Flair originale
    mrib = save_preds[0]
    atlas_brats = args.atlas

    subject_id = extract_subject_id(mri)
    if subject_id is None:
        raise ValueError(f"Cannot extract subject ID from filename: {os.path.basename(mri)}")

    prefix = f"{args.w}/derivatives/deep_learning_seg/{subject_id}/anat/"
    print(f"Final path: {prefix}")
    outprefix = f"{args.output}/{subject_id}_mrib2mri_Rigid_"

    print(f"Extracted subject ID: {subject_id}")
    print(f"Output directory: {prefix}")

    # Crea la directory se non esiste
    os.makedirs(prefix, exist_ok=True)

    mri_space_mrib, mrib_space_mri, mrib2mri_tfm, mri2mrib_tfm = align(
        fx=mri,
        mv=atlas_brats,
        transform_method='SyNAggro',
        outprefix=outprefix
    )

    new_mri = transform(
        prefix=prefix,
        fx=mri,
        mv=mrib,
        tfm=mrib2mri_tfm,
        interpolator='nearestNeighbor'
    )

    new_mri = Path(new_mri)

    mri_name = Path(mri).name
    if mri_name.endswith('.nii.gz'):
        seg_name = mri_name[:-7] + '_seg.nii.gz'
    else:
        seg_name = Path(mri).stem + '_seg' + Path(mri).suffix

    seg_path = Path(prefix) / seg_name

    if seg_path.exists():
        seg_path.unlink()

    shutil.move(str(new_mri), str(seg_path))

    new_mri = seg_path
    print("Final saved file:", new_mri)

    print("Finished!")