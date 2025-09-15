import logging
import os
import torch
import argparse
torch.serialization.add_safe_globals([argparse.Namespace])

from pytorch_lightning import Trainer, seed_everything
from pytorch_lightning.callbacks import ModelCheckpoint, ModelSummary, RichProgressBar
from pytorch_lightning.loggers import TensorBoardLogger

from data_loading.data_module import DataModule, DataModulePostop
from nnunet.nn_unet import NNUnet
from utils.args import get_main_args
from utils.utils import make_empty_dir, set_cuda_devices, set_granularity, verify_ckpt_path


# inspired by the NVIDIA nnU-Net GitHub repository available at:
# https://github.com/NVIDIA/DeepLearningExamples/tree/master/PyTorch/Segmentation/nnUNet


if __name__ == "__main__":
    args = get_main_args()
    set_granularity()  # increase maximum fetch granularity of L2 to 128 bytes
    set_cuda_devices(args)
    if args.seed is not None:
        seed_everything(args.seed)
        #DataModulePostop(args)
    data_module = DataModule(args) if args.freeze >= 0 else DataModule(args)
    if args.exec_mode == "predict":
        data_module.setup()  # call setup for pytorch_lightning compatibility
    ckpt_path = verify_ckpt_path(args)

    nnunet = NNUnet(args)
    # check transfer learning feasibility
    if args.freeze >= 0:
        # load weights only
        print(f"Loading state dict from {ckpt_path} for transfer learning...")
        checkpoint = torch.load(ckpt_path, weights_only=False)
        nnunet.load_state_dict(checkpoint['state_dict'], strict = False)
        max_freezing = 2 * args.depth + 1
        assert args.freeze <= max_freezing, "Not enough blocks to freeze!"
        flag = 0
        for child in nnunet.model.children():
            if flag < args.freeze:
                # keep freezing
                if hasattr(child, '__iter__'):  # iterate over nn.ModuleList
                    for block in child:
                        flag += 1
                        for param in block.parameters():
                            param.requires_grad = False
                        if flag > args.freeze:
                            break
                else:
                    flag += 1
                    for param in child.parameters():
                        param.requires_grad = False

    callbacks = [RichProgressBar(), ModelSummary(max_depth=2)]
    logger = False
    if args.exec_mode == "train":
        if args.tb_logs:
            logger = TensorBoardLogger(
                save_dir=f"{args.results}/tb_logs",
                name=f"task={args.task}_dim=3_fold={args.fold}_precision={16 if args.amp else 32}",
                default_hp_metric=False,
                version=0,
            )
        if args.save_ckpt:
            callbacks.append(
                ModelCheckpoint(
                    dirpath=f"{args.ckpt_store_dir}/checkpoints/fold{args.fold}",
                    filename="{epoch}-{dice:.2f}",
                    monitor="dice",
                    mode="max",
                    save_last=True,
                )
            )

    # define the trainer
    trainer = Trainer(
        logger=logger,  # logger for experiment tracking
        default_root_dir=args.results,   # default path for logs and weights when no logger or ckpt callback is passed
        benchmark=True,
        deterministic=False,   # sets whether PyTorch operations must use deterministic algorithms
        max_epochs=args.epochs,
        precision=16 if args.amp else 32,
        gradient_clip_val=args.gradient_clip_val,
        enable_checkpointing=args.save_ckpt,
        callbacks=callbacks,
        num_sanity_val_steps=0,  # sanity check runs 0 validation batches before starting the training routine
        accelerator="gpu",
        devices=args.gpus,
        num_nodes=args.nodes,
        strategy="ddp" if args.gpus > 1 else "auto",
    )

    print(f"Save preds {args.save_preds}")
    if args.exec_mode == "train":
        # do not load whole state under transfer learning
        trainer.fit(nnunet, datamodule=data_module, ckpt_path=None if args.freeze >= 0 else ckpt_path)
    elif args.exec_mode == "predict":
        if args.save_preds:
            # define prediction directory
            ckpt_name = "_".join(args.ckpt_path.split("/")[-1].split(".")[:-1])
            dir_name = f"predictions_{ckpt_name}"
            dir_name += f"_task={nnunet.args.task}_fold={nnunet.args.fold}"
            if args.tta:
                dir_name += "_tta"
            save_dir = os.path.join(args.results, dir_name)
            print(f"Saving predictions to {save_dir}")
            nnunet.save_dir = save_dir
            make_empty_dir(save_dir)

        nnunet.args = args
        checkpoint = torch.load(ckpt_path, weights_only=False)
        nnunet.load_state_dict(checkpoint['state_dict'], strict = False)
        trainer.test(nnunet, dataloaders=data_module.test_dataloader())
