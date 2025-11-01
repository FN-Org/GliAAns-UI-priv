
import os
import time

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser

from Preprocessor import Preprocessor

# inspired by the NVIDIA nnU-Net GitHub repository available at:
# https://github.com/NVIDIA/DeepLearningExamples/tree/master/PyTorch/Segmentation/nnUNet


# retrieve args from command line
parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument("--data", type=str, help="Path to data directory")
parser.add_argument("--results", type=str, help="Path for saving results directory")
parser.add_argument(
    "--exec_mode",
    type=str,
    default="test",
    choices=["training", "test"],
    help="Mode for data preprocessing",
)
parser.add_argument("--ohe", action="store_true", help="Add one-hot-encoding for foreground voxels (voxels > 0)")
parser.add_argument("--verbose", action="store_true")
parser.add_argument("--task", type=str, default="val", choices=["train", "val"], help="Choose between train or val on BraTS")
parser.add_argument("--dim", type=int, default=3, choices=[2, 3], help="Data dimension to prepare")
parser.add_argument("--n_jobs", type=int, default=-1, help="Number of parallel jobs for data preprocessing")


if __name__ == "__main__":
    args = parser.parse_args()
    # run the Preprocessor
    start = time.time()
    Preprocessor(args).run()
    end = time.time()
    print(f"Pre-processing time: {(end - start):.2f}")
