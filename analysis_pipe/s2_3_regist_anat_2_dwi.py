import pathlib
import os
import subprocess
import concurrent.futures


root_dir = pathlib.Path("/data04/ASD_Li_lab/")
freesurfer_dir = "/data01/software/freesurfer/"


def process_subject(subject_dir):
    subject = subject_dir.name
    print(f"Processing subject: {subject}")
    
    dwi_dir = subject_dir / "dwi"
    anat_dir = subject_dir / "anat"
    
    b0_file = (dwi_dir / "corrected_masked").glob("*bse.nii.gz")
    b0_file = list(b0_file)[0]
    
    mask_file = (dwi_dir / "corrected_masked").glob("*bse-multi_BrainMask.nii.gz")
    mask_file = list(mask_file)[0]
    
    masked_b0 = dwi_dir / f"{subject}_b0_masked.nii.gz"
    
    if not masked_b0.exists():
        command = f"fslmaths {b0_file} -mas {mask_file} {masked_b0}"
        subprocess.run(command, shell=True, check=True)
    
    # register b0 to t1 use bbregister
    transform_dir = subject_dir / "dwi2anat"
    transform_dir.mkdir(exist_ok=True, parents=True)
    
    transform_file = transform_dir / "bbreg_to_t1w.dat"
    
    if not transform_file.exists():
        command = f"""
        export FREESURFER_HOME={freesurfer_dir}
        source $FREESURFER_HOME/SetUpFreeSurfer.sh
        export SUBJECTS_DIR={anat_dir}
        bbregister --s {subject} --mov {masked_b0} --dti --init-fsl --reg {transform_file}
        """
        subprocess.run(command, shell=True, executable='/bin/bash')

    aseg_in_dwi = dwi_dir / f"{subject}_aparc_dwi.nii.gz"
    if not aseg_in_dwi.exists():
        command = f"""
        export FREESURFER_HOME={freesurfer_dir}
        source $FREESURFER_HOME/SetUpFreeSurfer.sh
        export SUBJECTS_DIR={anat_dir}
        mri_vol2vol --mov {masked_b0} --targ {anat_dir / subject / 'mri' / 'aparc+aseg.mgz'} --inv --reg {transform_file} --o {aseg_in_dwi} --nearest
        """
        subprocess.run(command, shell=True, executable='/bin/bash')

subject_dirs = []

for site in root_dir.iterdir():
    if not site.is_dir():
        continue

    if site.name not in ["ASD_baseline", "HC_Time2", "TD_Time1"]:
        continue
    
    for subj_dir in site.iterdir():
        if not subj_dir.is_dir():
            continue

        subject_dirs.append(subj_dir)
        
subject_dirs = sorted(subject_dirs)

# for subject_dir in subject_dirs:
#     process_subject(subject_dir)
        
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    executor.map(process_subject, subject_dirs)
    