import os
import sys
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pathlib import Path
import nibabel as nib
import numpy as np
from nibabel.orientations import io_orientation, ornt_transform, apply_orientation, aff2axcodes

# === PARSER ===
parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument(
    "--input", type=str, required=True,
    help="File brain_in_atlas da riorientare"
)
parser.add_argument(
    "--output", type=str, required=True,
    help="Directory di output dove salvare il file riorientato"
)
parser.add_argument(
    "--basename", type=str, required=True,
    help="Nome base del file (senza estensioni), usato per nominare l'output"
)
parser.add_argument(
    "--brats", type=str, required=False,
    default=os.path.join("deep_learning", "atlas", "BraTS-GLI-01-001.nii"),
    help="File BraTS di riferimento (default: BraTS-GLI-01-001.nii nel repo)"
)

if __name__ == "__main__":
    args = parser.parse_args()

    brain_in_atlas_file = args.input
    output_dir = Path(args.output)
    basename = args.basename
    brats_reference_path = args.brats

    # Verifica esistenza file BraTS di riferimento
    if not os.path.exists(brats_reference_path):
        sys.stderr.write(f"✗ File BraTS di riferimento non trovato: {brats_reference_path}\n")
        sys.exit(1)

    # Carica immagini
    my_img = nib.load(brain_in_atlas_file)
    brats_img = nib.load(brats_reference_path)

    # Ottieni affini e orientamenti
    my_affine = my_img.affine
    brats_affine = brats_img.affine

    my_ornt = io_orientation(my_affine)
    brats_ornt = io_orientation(brats_affine)

    sys.stdout.write(f"Orientamento brain_in_atlas: {my_ornt}\n")
    sys.stdout.write(f"Orientamento BraTS riferimento: {brats_ornt}\n")

    # Se necessario, riorienta
    if not (my_ornt == brats_ornt).all():
        sys.stdout.write("Orientamenti diversi - eseguo riorientazione...\n")
        transform = ornt_transform(my_ornt, brats_ornt)
        reoriented_data = apply_orientation(my_img.get_fdata(), transform)
    else:
        reoriented_data = my_img.get_fdata()
        sys.stdout.write("Orientamento già coerente con BraTS\n")


    img_corrected = reoriented_data / 10.0
    reoriented_img = nib.Nifti1Image(img_corrected, affine=brats_affine, header=brats_img.header)

    # Crea output
    # reoriented_img = nib.Nifti1Image(reoriented_data, affine=brats_affine)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_filename = f"{basename}_reoriented.nii.gz"
    reoriented_output_path = output_dir / output_filename

    nib.save(reoriented_img, reoriented_output_path)

    sys.stdout.write(f"✓ File riorientato salvato: {reoriented_output_path}\n")

    # Verifica orientamento finale
    final_img = nib.load(reoriented_output_path)
    final_ornt = aff2axcodes(final_img.affine)
    brats_ornt_codes = aff2axcodes(brats_affine)

    sys.stdout.write(f"Orientamento finale: {final_ornt}\n")
    sys.stdout.write(f"Orientamento BraTS: {brats_ornt_codes}\n")

    final_shape = final_img.get_fdata().shape
    brats_shape = brats_img.get_fdata().shape
    sys.stdout.write(f"Dimensioni file riorientato: {final_shape}\n")
    sys.stdout.write(f"Dimensioni BraTS riferimento: {brats_shape}\n")

    sys.exit(0)