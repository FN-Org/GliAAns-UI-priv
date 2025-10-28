import os
import sys
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pathlib import Path

from utils.coreg import align, transform

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# retrieve args from command line
parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument(
    "-o", "--output", type=str, required=True,
    help="Directory where to save the final NIfTI predictions"
)
parser.add_argument(
    "--mri", type=str, required=True,
    help="Original FLAIR mri"
)
parser.add_argument(
    "--skull", type=str, required=True,
    help="Skull stripped file (with synthstrip)"
)
parser.add_argument(
    "--atlas", type=str, required=True,
    help="T1 atlas"
)
parser.add_argument(
    "--clobber",
    action="store_true",          # diventa un flag
    help="Overwrite existing files (default: False)"
)

if __name__ == "__main__":
    args = parser.parse_args()

    mri = args.mri
    mri_str = args.skull
    stx = args.atlas
    clobber = args.clobber

    input_basename = Path(mri).stem.replace('.nii', '')
    output_dir = Path(args.output)
    prefix = str(output_dir / f"{input_basename}_")

    # Esegue la registrazione
    stx_space_mri, mri_space_stx, stx2mri_tfm, mri2stx_tfm = align(
        fx=mri,
        mv=stx,
        transform_method='SyNAggro',
        outprefix=f'{prefix}_stx2mri_SyN_'
    )

    # Applica la trasformazione al brain mask skull-stripped
    brain_in_atlas = transform(
        prefix=prefix,
        fx=stx,
        mv=mri_str,
        tfm=mri2stx_tfm,
        clobber=clobber
    )