import os
import glob
import subprocess
from multiprocessing import Pool, cpu_count


input_dir = "/data04/ASD_Li_lab/2B_pre"
freesurfer_dir = "/data01/software/freesurfer/"


def process_subject(args):
    site, subject = args

    site_path = os.path.join(input_dir, site)
    subject_path = os.path.join(site_path, subject)

    anat_dir = os.path.join(subject_path, "anat")
    if not os.path.exists(anat_dir) or not os.path.isdir(anat_dir):
        print(f"[WARN] anat dir not found, skip: site={site}, subject={subject}")
        return

    t1w_files = glob.glob(os.path.join(anat_dir, "*_T1w.nii.gz"))
    if not t1w_files:
        print(f"[WARN] No T1w for: site={site}, subject={subject}")
        return

    t1w_file = t1w_files[0]

    print(f"[INFO] Start recon-all: site={site}, subject={subject}")

    command = f"""
    export FREESURFER_HOME={freesurfer_dir}
    source $FREESURFER_HOME/SetUpFreeSurfer.sh
    export SUBJECTS_DIR={anat_dir}

    recon-all -i {t1w_file} -s {subject} -all -threads 40
    """
    subprocess.run(command, shell=True, executable='/bin/bash')

    print(f"[INFO] Finished processing subject {subject} at site {site}.")


if __name__ == "__main__":
    subject_list = []

    for site in os.listdir(input_dir):
        if site not in ["HC_Time2", "TD_Time1_1"]:
            continue
        
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

            t1w_files = glob.glob(os.path.join(anat_dir, "*_T1w.nii.gz"))
            if not t1w_files:
                continue

            subject_list.append((site, subject))

    print(f"[INFO] Total subjects to process: {len(subject_list)}")

    NUM_WORKERS = min(3, cpu_count())

    with Pool(processes=NUM_WORKERS) as pool:
        pool.map(process_subject, subject_list)
