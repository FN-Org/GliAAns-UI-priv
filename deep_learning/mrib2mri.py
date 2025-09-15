from pediatric_fdopa_pipeline.utils import align, transform

if __name__ == "__main__":
    mri = ".workspace/sub-01/anat/sub-01_run-1_flair.nii.gz"
    atlas_brats = "pediatric_fdopa_pipeline/atlas/T1.nii.gz"
    mrib = ".workspace/outputs/dl_postprocess/sub-01_run-1_flair_reoriented-seg.nii.gz"
    prefix = ".workspace/outputs/nifti/sub-01_"

    mri_space_mrib, mrib_space_mri, mrib2mri_tfm, mri2mrib_tfm = align(mri, atlas_brats,
                                                                                           transform_method='SyNAggro',
                                                                                           outprefix=f'_mrib2mri_Rigid_')

    new_mri = transform(prefix, mri, mrib, mrib2mri_tfm)