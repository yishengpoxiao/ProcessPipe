import numpy as np
import pathlib
import os, glob
from scipy import ndimage as nd
import nibabel as nib
from matplotlib import pyplot as plt
from skimage import filters
import skimage.morphology as mp
from multiprocessing import Pool, cpu_count

def run_frangi(args):
    site, subject = args

    site_path = os.path.join(input_dir, site)
    subject_path = os.path.join(site_path, subject)

    anatdir = os.path.join(subject_path, "anat")
    
    subject_id = pathlib.Path(anatdir).parent.name

    if ( pathlib.Path(anatdir) / f'{subject_id}_pvs.nii.gz' ).exists():
        print(f'{subject_id} has been processed')
        return
    
    orig_path = pathlib.Path(anatdir) / subject_id / 'mri' / 'nu.mgz'
    img = nib.load(orig_path)
    vol_raw = img.get_fdata()
    affine = img.affine
    fvs = filters.frangi(vol_raw,sigmas=np.linspace(0.5, 2.0, 6))
    img = nib.Nifti1Image(fvs, affine)
    img.to_filename(pathlib.Path(anatdir) / f'{subject_id}_pvs.nii.gz')
    print(f'Finished frangi for {subject_id}')
    # subprocess.run(f'cp {orig_path} {anatdir / f"{subject_id}_T1_nu.mgz"}', shell=True)
    
if __name__ == "__main__":
    subject_list = []
    
    input_dir = "/data04/ASD_Li_lab"

    for site in os.listdir(input_dir):
        if site not in ["ASD_baseline", "TD_Time1", "HC_Time2", "error_subj"]:
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

    NUM_WORKERS = min(20, cpu_count())

    with Pool(processes=NUM_WORKERS) as pool:
        pool.map(run_frangi, subject_list)

