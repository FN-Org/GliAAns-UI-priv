import numpy as np
import nibabel as nib
import re
import os
os.environ["OMP_NUM_THREADS"] = "30"  # export OMP_NUM_THREADS=1
os.environ["OPENBLAS_NUM_THREADS"] = "30" # export OPENBLAS_NUM_THREADS=1
os.environ["MKL_NUM_THREADS"] = "30"  # export MKL_NUM_THREADS=1
os.environ["VECLIB_MAXIMUM_THREADS"] = "30" # export VECLIB_MAXIMUM_THREADS=1
os.environ["NUMEXPR_NUM_THREADS"] = "30"  # export NUMEXPR_NUM_THREADS=1
import ants
import argparse
import pandas as pd
from argparse import ArgumentParser
from pathlib import Path
from sys import argv
from glob import glob
from pediatric_fdopa_pipeline.subject import Subject
from pediatric_fdopa_pipeline.analysis import tumor_striatum_analysis
from pediatric_fdopa_pipeline.utils import get_file, get_dynamic_parameters



def find_subject_ids(data_dir):
    get_id = lambda fn: re.sub('sub-','',os.path.basename(fn).split('_')[0])
    pet_images_list = Path(data_dir).rglob('*_ses-01_pet.nii.gz')
    return [ get_id(fn) for fn in pet_images_list ]

        
def get_parser():
    parser = ArgumentParser(usage="useage: ")
    parser.add_argument("-i",dest="data_dir", default='pediatric/', help="Path for input file directory")
    parser.add_argument("-o",dest="out_dir", default='output/', help="Path for output file directory")
    parser.add_argument("-s",dest="stx_fn", default='atlas/mni_icbm152_t1_tal_nlin_asym_09c.nii.gz', help="Path for stereotaxic template file")
    parser.add_argument("-a",dest="atlas_fn", default='atlas/dka_atlas_eroded.nii.gz', help="Path for stereotaxic label file")
    parser.add_argument("--vol_MRI", dest="flair_tumor", default='tumor_MRI/', help="Path for MRI volume")
    return parser


def run_pipeline_from_config(config_path, work_dir, out_dir="output/"):
    import json

    with open(config_path, "r", encoding="utf-8") as f:
        pipeline_config = json.load(f)

    print("\nRunning pipeline from JSON config:", config_path)

    tumor_striatum_csv = os.path.join(out_dir, 'tumor_striatum_ibrido.csv')
    dynamic_parameters = os.path.join(out_dir, 'Dynamic_Parameters_ibrido.csv')
    H_tumor_percentage = os.path.join(out_dir, 'H_tumor_percentage_ibrido.csv')

    print("Outputs:")
    print(f"  Tumor striatum ratio csv: {tumor_striatum_csv}")
    print(f"  Dynamic Parameters csv: {dynamic_parameters}")
    print(f"  H_tumor_percentage csv: {H_tumor_percentage}")
    print()

    subject_list = []
    for patient_id, files in pipeline_config.items():
        flair_tumor = files.get("tumor_mri")
        pet_file = files.get("pet")
        pet_json_file = files.get("pet_json")
        pet4d_file = files.get("pet4d")
        mri_file = files.get("mri")
        mri_str_file = files.get("mri_str")

        # estrai solo il numero dopo "sub-"
        sub_number = patient_id.replace("sub-", "")

        # Qui costruiamo l'oggetto Subject come nel main originale
        subj = Subject(
            work_dir=work_dir,
            out_dir=out_dir,
            sub=sub_number,
            stx_fn="./pediatric_fdopa_pipeline/atlas/mni_icbm152_t1_tal_nlin_asym_09c.nii.gz",
            atlas_fn="./pediatric_fdopa_pipeline/atlas/dka_atlas_eroded.nii.gz",
            flair_tumor=flair_tumor,
            pet_file=pet_file,
            pet_json_file=pet_json_file,
            pet4d_file=pet4d_file,
            mri_file=mri_file,
            mri_str_file=mri_str_file
        )
        subj.process()
        subject_list.append(subj)

    # Analisi
    subject_list = [tumor_striatum_analysis(subj, subj.roi_labels, subj.ref_labels) for subj in subject_list]
    tumor_striatum_df = pd.concat([subj.suvr_df for subj in subject_list])
    tumor_striatum_df.to_csv(tumor_striatum_csv, index=False)

    dy_param_data, ratio_data = [], []

    for subject in subject_list:
        if (Path(subject.data_dir + '/sub-' + subject.sub + '/ses-02').is_dir()):
            dy_param_data.append(subject.dy_df)
            if (subject.bool_flag):
                ratio_data.append({'subject': subject.sub, 'percentage': subject.tum_percentage})

    if dy_param_data:
        pd.concat(dy_param_data).to_csv(dynamic_parameters, index=False)
    else:
        pd.DataFrame().to_csv(dynamic_parameters, index=False)

    if ratio_data:
        pd.DataFrame(ratio_data).to_csv(H_tumor_percentage, index=False)
    else:
        pd.DataFrame().to_csv(H_tumor_percentage, index=False)

    print("Pipeline completed successfully.")

if __name__ == '__main__' :

    opts = get_parser().parse_args()
    print('\n Pediatric FDOPA Pipeline\n ________________________\n')
    print('\tOptions')
    print('\t\tData directory:', opts.data_dir)
    print('\t\tOutput directory:', opts.out_dir)
    print('\t\tTemplate:',opts.stx_fn)
    print('\t\tAtlas:', opts.atlas_fn)
    print('\t\tTumor:', opts.flair_tumor)
    print()

    tumor_striatum_csv = opts.out_dir+os.sep+'tumor_striatum_ibrido.csv'
    print('\tOutputs')
    print('\t\tTumor striatum ratio csv:'+tumor_striatum_csv)
    print()

    dynamic_parameters = opts.out_dir+os.sep+'Dynamic_Parameters_ibrido.csv'
    print('\tOutputs')
    print('\t\tDynamic Parameters csv:'+dynamic_parameters)
    print()

    H_tumor_percentage = opts.out_dir+os.sep+'H_tumor_percentage_ibrido.csv'
    print('\tOutputs')
    print('\t\tH_tumor_percentage csv:'+H_tumor_percentage)
    print()

    subject_id_list = find_subject_ids(opts.data_dir)
    print('\tRuntime parameters:')
    print(f'\t\tSubject IDs: {subject_id_list}')
    print()
        
    # Create a list of instances of the Subject class. 
    subject_list = [ Subject(opts.data_dir, opts.out_dir, sub, opts.stx_fn, opts.atlas_fn, opts.flair_tumor) for sub in subject_id_list ]
    
    # Do initial processing for each subject (e.g., alignment to MRI and stereotaxic atlas)
    [ subj.process() for subj in subject_list ] 

    # Do analysis to find maximum tumor and striatum PET values
    subject_list = [ tumor_striatum_analysis(subj, subj.roi_labels, subj.ref_labels) for subj in subject_list ]
    tumor_striatum_df = pd.concat([ subject.suvr_df for subject in subject_list ])
    tumor_striatum_df.to_csv(tumor_striatum_csv, index=False)

    # Initialize lists to store data
    dy_param_data = []
    ratio_data = []

    for subject in subject_list:
    # Checking if PET file exists
        if (Path(subject.data_dir+'/sub-'+subject.sub+'/ses-02').is_dir()):
            # Extract dynamic parameters
            dy_param_data.append(subject.dy_df)
            if (subject.bool_flag):
                ratio_data.append({'subject': subject.sub, 'percentage': subject.tum_percentage})
        
    # Concatenate dynamic parameters dataframes
    if dy_param_data:
        dy_param_df = pd.concat(dy_param_data)
    else:
        dy_param_df = pd.DataFrame()  

    # Concatenate tumor percentage data
    if ratio_data:
        df_ratio = pd.DataFrame(ratio_data)
    else:
        df_ratio = pd.DataFrame() 

    # Write dataframes to CSV files
    dy_param_df.to_csv(dynamic_parameters, index=False)
    df_ratio.to_csv(H_tumor_percentage, index=False)

    print()

