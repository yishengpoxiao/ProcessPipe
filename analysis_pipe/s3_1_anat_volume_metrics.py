import pathlib
import nibabel as nib
import subprocess
import numpy as np
import pandas as pd
import concurrent.futures


def process_subject(subject_dir):
    subject = subject_dir.name
    
    site_name = subject_dir.parent.name
    
    anat_dir = subject_dir / "anat"
    dwi_dir = subject_dir / "dwi"
    
    freesurfer_seg = anat_dir / subject / "mri" / "aparc+aseg.mgz"
    nib_data = nib.load(str(freesurfer_seg))
    
    voxel_size = nib_data.header.get_zooms()
    volume_per_voxel = voxel_size[0] * voxel_size[1] * voxel_size[2]  # in mm^3
    
    nib_array = nib_data.get_fdata()
    
    # wm volume
    wm_mask = np.isin(nib_array, [2, 41])
    wm_volume_voxels = np.sum(wm_mask)
    wm_volume_mm3 = wm_volume_voxels * volume_per_voxel
    
    # intra volume
    dwi_mask = dwi_dir.rglob("*_dwi_QCed_bse-multi_BrainMask.nii.gz")
    dwi_mask = list(dwi_mask)[0]
    dwi_nib = nib.load(str(dwi_mask))
    volume_per_voxel_dwi = dwi_nib.header.get_zooms()[0] * dwi_nib.header.get_zooms()[1] * dwi_nib.header.get_zooms()[2]
    dwi_array = dwi_nib.get_fdata()
    intra_volume_voxels = dwi_array.sum()
    intra_volume_mm3 = intra_volume_voxels * volume_per_voxel_dwi
    
    # gm volume
    gm_mask = (nib_array < 3000) & (nib_array > 1000)
    gm_volume_voxels = np.sum(gm_mask)
    gm_volume_mm3 = gm_volume_voxels * volume_per_voxel
    
    # extra csf volume
    # csf_label = 24
    # csf = nib_array == csf_label
    # ventrcles_label = (4, 43, 14, 15, 72, 73)
    # vent = np.isin(nib_array, ventrcles_label)
    # mask = csf & (~vent)
    # choroid_plexus_label = (31, 63)
    # choroid = np.isin(nib_array, choroid_plexus_label)
    # extra_csf_mask = mask & (~choroid)
    # extra_csf_volume_voxels = np.sum(extra_csf_mask)
    # extra_csf_volume_mm3 = extra_csf_volume_voxels * volume_per_voxel

    dwi_seg = dwi_dir / f"{subject}_aparc_dwi.nii.gz"
    dwi_seg_nib = nib.load(str(dwi_seg))
    dwi_seg_array = dwi_seg_nib.get_fdata()
    extra_csf_volume = dwi_array.sum() - np.sum(dwi_seg_array > 0)
    extra_csf_volume_mm3 = extra_csf_volume * volume_per_voxel_dwi
    
    return {
        "subject": subject,
        "site": site_name,
        "wm_volume_mm3": wm_volume_mm3,
        "intra_volume_mm3": intra_volume_mm3,
        "gm_volume_mm3": gm_volume_mm3,
        "extra_csf_volume_mm3": extra_csf_volume_mm3,
        "voxel size": f"{voxel_size[0]:.2f} x {voxel_size[1]:.2f} x {voxel_size[2]:.2f} mm^3"
    }


root_dir = pathlib.Path("/data04/ASD_Li_lab/")

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

df = pd.DataFrame(columns=["subject", "category", "wm_volume_mm3", "intra_volume_mm3", "gm_volume_mm3", "extra_csf_volume_mm3"])

with concurrent.futures.ProcessPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(process_subject, subject_dirs))
    
df = pd.DataFrame(results)
df.to_csv("/data04/ASD_Li_lab/results/anat_volume_metrics.csv", index=False)
