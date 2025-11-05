import os
import json
import sys
import argparse
import pandas as pd
from pathlib import Path

from pediatric_fdopa_pipeline.analysis import tumor_striatum_analysis
from pediatric_fdopa_pipeline.subject import Subject
from pediatric_fdopa_pipeline.utils import log_progress,log_message,log_error

os.environ["OMP_NUM_THREADS"] = "30"
os.environ["OPENBLAS_NUM_THREADS"] = "30"
os.environ["MKL_NUM_THREADS"] = "30"
os.environ["VECLIB_MAXIMUM_THREADS"] = "30"
os.environ["NUMEXPR_NUM_THREADS"] = "30"


def run_pipeline_from_config(config_path, work_dir, out_dir):
    log_message("Loading configuration file...")

    with open(config_path, "r", encoding="utf-8") as f:
        pipeline_config = json.load(f)

    log_message(f"Configuration loaded. Found {len(pipeline_config)} patients.")

    tumor_striatum_csv = os.path.join(out_dir, 'tumor_striatum_ibrido.csv')
    dynamic_parameters = os.path.join(out_dir, 'Dynamic_Parameters_ibrido.csv')
    H_tumor_percentage = os.path.join(out_dir, 'H_tumor_percentage_ibrido.csv')

    log_message("Output files will be saved as:")
    log_message(f"  - Tumor striatum ratio: {os.path.basename(tumor_striatum_csv)}")
    log_message(f"  - Dynamic Parameters: {os.path.basename(dynamic_parameters)}")
    log_message(f"  - H tumor percentage: {os.path.basename(H_tumor_percentage)}")

    subject_list = []
    total_patients = len(pipeline_config)
    current_patient = 0

    log_message("Starting patient processing...")
    log_progress(10)

    progress_per_patient = int(90/total_patients)
    current_progress = 10

    for patient_id, files in pipeline_config.items():
        current_patient += 1
        log_message(f"Processing patient {current_patient}/{total_patients}: {patient_id}")

        flair_tumor = files.get("tumor_mri")
        pet_file = files.get("pet")
        pet4d_file = files.get("pet4d")
        pet_json_file = files.get("pet4d_json")
        mri_file = files.get("mri")
        mri_str_file = files.get("mri_str")

        # Estrai solo il numero dopo "sub-"
        sub_number = patient_id.replace("sub-", "")

        log_message(f"  - Creating Subject object for {patient_id}")

        # Costruisci l'oggetto Subject
        subj = Subject(
            work_dir=work_dir,
            out_dir=out_dir,
            sub=sub_number,
            stx_fn=os.path.join(os.path.dirname(sys.argv[0]), "atlas", "mni_icbm152_t1_tal_nlin_asym_09c.nii.gz"),
            atlas_fn=os.path.join(os.path.dirname(sys.argv[0]), "atlas", "dka_atlas_eroded.nii.gz"),
            flair_tumor=flair_tumor,
            pet_file=pet_file,
            pet_json_file=pet_json_file,
            pet4d_file=pet4d_file,
            mri_file=mri_file,
            mri_str_file=mri_str_file,
            progress = [current_progress,progress_per_patient]
        )

        log_message(f"  - Processing {patient_id}...")
        subj.process()
        current_progress = current_progress + progress_per_patient

        log_progress(current_progress)

        subject_list.append(subj)
        log_message(f"  - Completed processing for {patient_id}")
        print(f"PATIENT: {patient_id}")

    log_message("Patient processing completed. Starting analysis phase...")

    # Analisi
    log_message("Performing tumor striatum analysis...")
    subject_list = [tumor_striatum_analysis(subj, subj.roi_labels, subj.ref_labels) for subj in subject_list]

    log_message("Creating tumor striatum dataframe...")
    tumor_striatum_df = pd.concat([subj.suvr_df for subj in subject_list])
    tumor_striatum_df.to_csv(tumor_striatum_csv, index=False)
    log_message(f"Saved tumor striatum results to: {tumor_striatum_csv}")

    dy_param_data, ratio_data = [], []

    log_message("Processing dynamic parameters...")
    for subject in subject_list:
        if (Path(subject.data_dir) / f"sub-{subject.sub}" / "ses-02").is_dir():
            log_message(f"Adding dynamic parameters for subject {subject.sub}")
            dy_param_data.append(subject.dy_df)
            if subject.bool_flag:
                ratio_data.append({'subject': subject.sub, 'percentage': subject.tum_percentage})

    if dy_param_data:
        log_message(f"Saving dynamic parameters for {len(dy_param_data)} subjects...")
        pd.concat(dy_param_data).to_csv(dynamic_parameters, index=False)
        log_message(f"Saved dynamic parameters to: {dynamic_parameters}")
    else:
        log_message("No dynamic parameters data found, creating empty file...")
        pd.DataFrame().to_csv(dynamic_parameters, index=False)

    if ratio_data:
        log_message(f"Saving H tumor percentage data for {len(ratio_data)} subjects...")
        pd.DataFrame(ratio_data).to_csv(H_tumor_percentage, index=False)
        log_message(f"Saved H tumor percentage to: {H_tumor_percentage}")
    else:
        log_message("No H tumor percentage data found, creating empty file...")
        pd.DataFrame().to_csv(H_tumor_percentage, index=False)

    log_message("All analysis completed successfully!")

def main():
    parser = argparse.ArgumentParser(description='Run FDOPA pipeline')
    parser.add_argument('--config', required=True, help='Path to configuration file')
    parser.add_argument('--work-dir', required=True, help='Working directory')
    parser.add_argument('--out-dir', required=True, help='Output directory')

    args = parser.parse_args()

    try:
        run_pipeline_from_config(args.config, args.work_dir, args.out_dir)
        print("FINISHED: Pipeline completed successfully")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log_error(f"Pipeline failed: {str(e)}")
        log_error(f"Traceback: {tb}")
        sys.exit(1)

if __name__ == "__main__":
    main()