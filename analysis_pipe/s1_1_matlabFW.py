import os
import argparse
import subprocess
from multiprocessing.pool import ThreadPool
import pathlib

root_dir = pathlib.Path("/data04/ASD_Li_lab")


def process_subfolder(subfolder_path):
    subfolder_name = os.path.basename(subfolder_path) 
    print(f"----- matlab FW for {subfolder_name} -----")
    
    dwi_folders = subfolder_path.rglob('**/dwi')
    
    for dwi_folder in dwi_folders:
        qc_folder = dwi_folder / 'corrected_masked'
        
        dwi_files = sorted(pathlib.Path(qc_folder).glob(f'*_QCed.nii.gz'))
        print(f"dwi_files: {dwi_files}")

        for dwi_file in dwi_files:
            case_id = f"{subfolder_name}"
            print(case_id)
            
            dwi_nifti_path = dwi_file
            bval_path = qc_folder / dwi_file.name.replace('_QCed.nii.gz', '_QCed.bval')
            bvec_path = qc_folder / dwi_file.name.replace('_QCed.nii.gz', '_QCed.bvec')

            mask_nifti_path = qc_folder / dwi_file.name.replace('_QCed.nii.gz', '_QCed_bse-multi_BrainMask.nii.gz')

            output_folder = dwi_folder / 'matlabFW' / dwi_file.name.replace('_QCed.nii.gz', '')
            
            log_path = output_folder / dwi_file.name.replace('_QCed.nii.gz', '_FW.log')
            
            output_folder.mkdir(parents=True, exist_ok=True)
            
            matlab_com = f"addpath('/home/haolin/Research/Preprocess/FreeWater/'); addpath('/home/haolin/Research/Preprocess/FreeWater/lib'); addpath('/home/haolin/Research/Preprocess/FreeWater/lib/IO'); FreeWater_OneCase(\'{case_id}\', \'{dwi_nifti_path}\', \'{bval_path}\', \'{bvec_path}\', \'{mask_nifti_path}\', \'{output_folder}\'); exit"
            command = [
                "/data01/software/MATLAB/R2022b/bin/matlab",
                "-nodisplay", "-nosplash", "-nodesktop",
                "-logfile", log_path,
                "-r", matlab_com  
            ]

            # Execute the command
            print(f"Processing {case_id} ...")
            subprocess.call(command)


subjects_folder = []

for site_folder in root_dir.iterdir():
    site_name = site_folder.name
    if site_name not in ["ASD_baseline", "TD_Time1", "HC_Time2"]:
        continue
    
    if site_folder.is_dir():
        for subject_folder in site_folder.iterdir():
            if subject_folder.is_dir():
                subjects_folder.append(subject_folder)

subjects_folder = sorted(subjects_folder)

with ThreadPool(processes=10) as pool:
    print(f"subjects_folder: {subjects_folder}")
    pool.map(process_subfolder, subjects_folder)

# for subfolder in subjects_folder:
#     process_subfolder(subfolder)