import numpy as np
import nibabel as nib
import re
import os
import ants
import argparse
import json
from argparse import ArgumentParser
from pathlib import Path
from sys import argv
from glob import glob
from pediatric_fdopa_pipeline.utils import get_file, align, transform, get_tacs, get_dynamic_parameters
from pediatric_fdopa_pipeline.analysis import variable_def
from pediatric_fdopa_pipeline.roi_selection import region_selection
from pediatric_fdopa_pipeline.qc import ImageParam
from pediatric_fdopa_pipeline.utils import log_progress,log_message,log_error

class Subject():

    def __init__(self, work_dir, out_dir, sub, stx_fn, atlas_fn, flair_tumor, pet_file, pet_json_file, pet4d_file, mri_file, mri_str_file,progress,clobber=False):
        
        '''
        Inputs:
            data_dir :  str, directory from which to get pet and mri data for each subject
            out_dir  :  str, directory where outputs will be written
            sub :       str, subject id
            stx_fn :    str, file path to stereotaxic anatomic template
            atlat_fn:   str, file path to stereotaxic atlas
            labels:     dict, labels to use for extracting tacs 
            clobber:    bool, overwrite
        '''

        # Inputs :
        self.work_dir = work_dir
        self.sub = sub
        self.clobber = clobber

        self.pet = os.path.join(self.work_dir, pet_file)

        if pet4d_file:
            self.pet4d = os.path.join(self.work_dir, pet4d_file)

        self.mri = os.path.join(self.work_dir, mri_file)
        self.mri_str = os.path.join(self.work_dir, mri_str_file)
        self.stx = stx_fn
        self.atlas_fn = atlas_fn
        self.tumor_MRI = os.path.join(self.work_dir, flair_tumor)

        # Outputs :
        self.sub_dir = out_dir + os.sep + 'sub-'+ sub
        self.qc_dir = self.sub_dir + os.sep + 'qc/'
        self.coreg_dir = self.sub_dir + os.sep + 'coregistration/'
        self.ref_dir = self.sub_dir + os.sep + 'refinement/'
        self.data_dir = self.sub_dir + os.sep + 'data/'

        self.pet_json = pet_json_file
        if self.pet_json is not None:
            self.pet_header = json.load(open(os.path.join(self.work_dir, self.pet_json), 'r'))

        self.tacs_csv = self.sub_dir + '/' + f'sub-{sub}_TACs.csv'
        self.tacs_sub_regions_csv = self.sub_dir + '/' + f'sub-{sub}_TACs_sub_regions.csv'
        self.values_csv = self.sub_dir + '/' + f'sub-{sub}_values.csv'
        self.tacs_sub_regions_qc_plot = self.qc_dir + f'sub-{sub}_TAC_sub_regions.png'
        self.tacs_qc_plot = self.qc_dir + f'sub-{sub}_TACs.png'
        self.regline_plot = self.qc_dir + f'sub-{sub}_regline.png'
        self.mri2pet_qc_gif = self.qc_dir + f'sub-{sub}_mri2pet.gif'
        self.pet2pet_qc_gif = self.qc_dir + f'sub-{sub}_pet2pet.gif'
        self.stx2mri_qc_gif = self.qc_dir + f'sub-{sub}_stx2mri.gif'

        # Class variables
        self.prefix = self.sub_dir + '/' + 'sub-' + sub + '_'
        self.coreg_prefix = self.coreg_dir + os.sep + 'sub-' + sub + '_'
        self.ref_prefix = self.ref_dir + os.sep + 'sub-' + sub + '_'
        self.data_prefix = self.data_dir + os.sep + 'sub-' + sub + '_'

        # following variables are defined during <process()>. 
        # not necessary to define these variables here, but helps keeps things clear
        self.atlas_space_pet = None
        self.mri_space_pet = None
        self.pet_space_mri = None
        self.mri2pet_tfm = None
        self.pet2mri_tfm = None
        self.stx_space_mri = None
        self.mri_space_stx = None
        self.stx2mri_tfm = None
        self.mri2stx_tfm = None
        self.ref_labels = None
        self.roi_labels = None
        self.brain = None
        self.volume_MRI = None
        self.volume_ven = None
        self.suvr_m = None
        self.striatum_atlas = None
        self.striatum_label = None
        self.tumor_atlas = None
        self.tumor_label = None
        self.tum_percentage = None

        self.progress = progress
        
        # create output directories
        os.makedirs(self.sub_dir, exist_ok=True)
        os.makedirs(self.qc_dir, exist_ok=True)
        os.makedirs(self.coreg_dir, exist_ok=True)
        os.makedirs(self.ref_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)

        if (Path(self.work_dir+'/sub-'+self.sub+'/ses-02').is_dir()):
            self.frame_duration, self.frame_time_start, self.frame_weight = self.set_frame_times()

    def process(self):

        progress_per_process = int(self.progress[1]/9)

        # Align MRI to PET with Rigid Alignment
        self.mri2pet()

        current_progress = self.progress[0] + progress_per_process
        log_progress(current_progress)

        # Align Stereotaxic template to MRI with non-linear SyN transformation
        self.stx2mri()

        current_progress = current_progress + progress_per_process
        log_progress(current_progress)
        # Combine transformations so that we can transform from stereotaxic to PET coord space
        self.stx2pet_tfm = [self.mri2pet_tfm,self.stx2mri_tfm ]
        
        # Apply stx2pet transformation to get a brain mask
        self.brain = transform(self.coreg_prefix, self.pet, self.mri_str, self.mri2pet_tfm, qc_filename=f'{self.qc_dir}/pet_brain.gif', clobber=self.clobber )

        current_progress = current_progress + progress_per_process
        log_progress(current_progress)

        # Apply mri2pet transformation to get tumor volume in PET space
        self.volume_MRI = transform(self.coreg_prefix, self.pet, self.tumor_MRI, self.mri2pet_tfm, interpolator='nearestNeighbor',qc_filename=f'{self.qc_dir}/volume_MRI.gif', clobber=self.clobber )

        current_progress = current_progress + progress_per_process
        log_progress(current_progress)

        # Apply stx2pet transformation to stereotaxic atlas
        self.atlas_space_pet = transform(self.coreg_prefix, self.pet, self.atlas_fn, self.stx2pet_tfm, interpolator='nearestNeighbor', qc_filename=f'{self.qc_dir}/atlas_pet_space.gif', clobber=self.clobber )

        current_progress = current_progress + progress_per_process
        log_progress(current_progress)

        # Apply stx2pet transformation to stereotaxic template
        self.stx_space_pet = transform(self.coreg_prefix, self.pet, self.stx, self.stx2pet_tfm,  qc_filename=f'{self.qc_dir}/template_pet_space.gif', clobber=self.clobber)

        current_progress = current_progress + progress_per_process
        log_progress(current_progress)

        # Roi and Ref selection
        self = region_selection(self)

        current_progress = current_progress + progress_per_process
        log_progress(current_progress)

        # Defining attributes for static and dynamic analysis
        self.tumor_atlas, self.tumor_label, self.striatum_atlas, self.striatum_label, self.suvr_m = variable_def(self)

        if (Path(self.work_dir+'/sub-'+self.sub+'/ses-02').is_dir()):
            # Extract time-activity curves (TACs) from PET image using atlas in PET space 
            self.tacs = get_tacs(self, self.roi_labels, self.ref_labels ,  self.frame_time_start, self.tacs_csv, self.tacs_qc_plot, self.tacs_sub_regions_qc_plot)
            current_progress = current_progress + progress_per_process
            log_progress(current_progress)
            #Extract Dynamic Parameters from TACs
            self = get_dynamic_parameters(self, self.regline_plot)

            current_progress = current_progress + progress_per_process
            log_progress(current_progress)

        log_progress(int(self.progress[0]+self.progress[1]))

    def set_frame_times(self):
        frame_duration = np.array(self.pet_header['FrameDuration']).astype(float)
        frame_time_start = np.array(self.pet_header['FrameTimesStart']).astype(float)
        frame_weight = frame_duration / np.sum(frame_duration)
        return frame_duration, frame_time_start, frame_weight

    def pet_to_3d(self):
        img = nib.load(self.pet4d)
        vol = img.get_fdata()
        if len(vol.shape) == 4 : vol = np.sum(vol*self.frame_weight, axis=3)
        nib.Nifti1Image(vol, img.affine).to_filename(self.pet3d)

    ### Co-Registration ###
    def mri2pet(self):
        self.mri_space_pet, self.pet_space_mri, self.mri2pet_tfm, self.pet2mri_tfm = align(self.pet, self.mri, transform_method='Rigid', outprefix=f'{self.coreg_dir}/sub-{self.sub}_mri2pet_Rigid_', qc_filename = self.mri2pet_qc_gif)

    def stx2mri(self):
        self.stx_space_mri, self.mri_space_stx, self.stx2mri_tfm, self.mri2stx_tfm = align(self.mri, self.stx, transform_method='SyNAggro', outprefix=f'{self.coreg_dir}/sub-{self.sub}_stx2mri_SyN_', qc_filename = self.stx2mri_qc_gif)