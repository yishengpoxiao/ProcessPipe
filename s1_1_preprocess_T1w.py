import os, shutil, glob
import subprocess


input_dir = "/data/private_data/ASD_Li_lab"

freesurfer_dir = "/data/software/freesurfer/"

for site in os.listdir(input_dir):
    site_path = os.path.join(input_dir, site)
    if not os.path.isdir(site_path):
        continue

    for subject in os.listdir(site_path):
        subject_path = os.path.join(site_path, subject)
        if not os.path.isdir(subject_path):
            continue
        
        anat_dir = os.path.join(subject_path, "anat")
        if not os.path.exists(anat_dir) or not os.path.isdir(anat_dir):
            continue
        
        t1w_file = glob.glob(os.path.join(anat_dir, "*_T1w.nii.gz"))[0]
        
        command = f"""
        export FREESURFER_HOME={freesurfer_dir}
        source $FREESURFER_HOME/SetUpFreeSurfer.sh
        export SUBJECTS_DIR={anat_dir}
        
        recon-all -i {t1w_file} -s {subject} -all -threads 80
        """
        subprocess.run(command, shell=True, executable='/bin/bash')
        print(f"Finished processing subject {subject} at site {site}.")
