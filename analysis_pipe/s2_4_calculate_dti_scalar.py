from pathlib import Path
import subprocess
import os
import concurrent.futures
import shutil
import nibabel as nib


SlicerPath = "/data01/software/Slicer-5.2.2-linux-amd64/Slicer"

root_dir = Path('/data04/ASD_Li_lab/')

subjects_folder = []

for site_folder in root_dir.iterdir():
    if site_folder.is_dir():
        
        if site_folder.name not in ["ASD_baseline", "HC_Time2", "TD_Time1"]:
            continue
        
        for subject_folder in site_folder.iterdir():
            if subject_folder.is_dir():
                subjects_folder.append(subject_folder)
                
subjects_folder = sorted(subjects_folder)
                

def cal_scalar_map(subject_dir):
    subfolder_name = os.path.basename(subject_dir)
    
    print(f"----- DTI Scalar Map for {subfolder_name} -----")
    
    dwi_folders = subject_dir.glob('**/dwi')
    
    for dwi_folder in dwi_folders:
        print(dwi_folder)
        
        dti_dir = dwi_folder / 'DTI'
        dti_dir.mkdir(parents=True, exist_ok=True)
        
        dti_path = dti_dir.glob('*dwi_DTI.nrrd')
        dti_path = list(dti_path)[0]
        
        FA_path = dti_dir / f'{subfolder_name}_FA.nii.gz'
        MD_path = dti_dir / f'{subfolder_name}_MD.nii.gz'
        MinE_path = dti_dir / f'{subfolder_name}_MinE.nii.gz'
        MidE_path = dti_dir / f'{subfolder_name}_MidE.nii.gz'
        AD_path = dti_dir / f'{subfolder_name}_AD.nii.gz'
        RA_path = dti_dir / f'{subfolder_name}_RA.nii.gz'
        
        if not FA_path.exists():
            cmd = [SlicerPath,
                '--launch', '/data01/software/Slicer-5.2.2-linux-amd64/NA-MIC/Extensions-31382/SlicerDMRI/lib/Slicer-5.2/cli-modules/DiffusionTensorScalarMeasurements',
                str(dti_path),
                str(FA_path).replace('.nii.gz', ".nrrd"),
                '-e', 'FractionalAnisotropy']
            subprocess.run(cmd)
            
            cmd = ["/data06/yijie/miniconda3/envs/wma/bin/python", "/home/yijie/conversion/conversion/nifti_write.py", "-i", str(FA_path).replace('.nii.gz', ".nrrd"), "-p", str(FA_path).replace('.nii.gz', "")]
            subprocess.run(cmd)
            os.remove(str(FA_path).replace('.nii.gz', ".nrrd"))
            
        if not MD_path.exists():
            cmd = [SlicerPath,
                '--launch', '/data01/software/Slicer-5.2.2-linux-amd64/NA-MIC/Extensions-31382/SlicerDMRI/lib/Slicer-5.2/cli-modules/DiffusionTensorScalarMeasurements',
                str(dti_path),
                str(MD_path).replace('.nii.gz', ".nrrd"),
                '-e', 'MeanDiffusivity']
            subprocess.run(cmd)
            
            cmd = ["/data06/yijie/miniconda3/envs/wma/bin/python", "/home/yijie/conversion/conversion/nifti_write.py", "-i", str(MD_path).replace('.nii.gz', ".nrrd"), "-p", str(MD_path).replace('.nii.gz', "")]
            subprocess.run(cmd)
            os.remove(str(MD_path).replace('.nii.gz', ".nrrd"))
            
        if not MinE_path.exists():
            cmd = [SlicerPath,
                '--launch', '/data01/software/Slicer-5.2.2-linux-amd64/NA-MIC/Extensions-31382/SlicerDMRI/lib/Slicer-5.2/cli-modules/DiffusionTensorScalarMeasurements',
                str(dti_path),
                str(MinE_path).replace('.nii.gz', ".nrrd"),
                '-e', 'MinEigenvalue']
            subprocess.run(cmd)
            
            cmd = ["/data06/yijie/miniconda3/envs/wma/bin/python", "/home/yijie/conversion/conversion/nifti_write.py", "-i", str(MinE_path).replace('.nii.gz', ".nrrd"), "-p", str(MinE_path).replace('.nii.gz', "")]
            subprocess.run(cmd)
            os.remove(str(MinE_path).replace('.nii.gz', ".nrrd"))
            
        if not MidE_path.exists():
            cmd = [SlicerPath,
                '--launch', '/data01/software/Slicer-5.2.2-linux-amd64/NA-MIC/Extensions-31382/SlicerDMRI/lib/Slicer-5.2/cli-modules/DiffusionTensorScalarMeasurements',
                str(dti_path),
                str(MidE_path).replace('.nii.gz', ".nrrd"),
                '-e', 'MidEigenvalue']
            subprocess.run(cmd)
            
            cmd = ["/data06/yijie/miniconda3/envs/wma/bin/python", "/home/yijie/conversion/conversion/nifti_write.py", "-i", str(MidE_path).replace('.nii.gz', ".nrrd"), "-p", str(MidE_path).replace('.nii.gz', "")]
            subprocess.run(cmd)
            os.remove(str(MidE_path).replace('.nii.gz', ".nrrd"))
            
        if not AD_path.exists():
            cmd = [SlicerPath,
                '--launch', '/data01/software/Slicer-5.2.2-linux-amd64/NA-MIC/Extensions-31382/SlicerDMRI/lib/Slicer-5.2/cli-modules/DiffusionTensorScalarMeasurements',
                str(dti_path),
                str(AD_path).replace('.nii.gz', ".nrrd"),
                '-e', 'MaxEigenvalue']
            subprocess.run(cmd)
            
            cmd = ["/data06/yijie/miniconda3/envs/wma/bin/python", "/home/yijie/conversion/conversion/nifti_write.py", "-i", str(AD_path).replace('.nii.gz', ".nrrd"), "-p", str(AD_path).replace('.nii.gz', "")]
            subprocess.run(cmd)
            os.remove(str(AD_path).replace('.nii.gz', ".nrrd"))
            
        if not RA_path.exists():
            cmd = [SlicerPath,
                '--launch', '/data01/software/Slicer-5.2.2-linux-amd64/NA-MIC/Extensions-31382/SlicerDMRI/lib/Slicer-5.2/cli-modules/DiffusionTensorScalarMeasurements',
                str(dti_path),
                str(RA_path).replace('.nii.gz', ".nrrd"),
                '-e', 'RelativeAnisotropy']
            subprocess.run(cmd)
            
            cmd = ["/data06/yijie/miniconda3/envs/wma/bin/python", "/home/yijie/conversion/conversion/nifti_write.py", "-i", str(RA_path).replace('.nii.gz', ".nrrd"), "-p", str(RA_path).replace('.nii.gz', "")]
            subprocess.run(cmd)
            os.remove(str(RA_path).replace('.nii.gz', ".nrrd"))
            
        RD_path = dti_dir / f'{subfolder_name}_RD.nii.gz'
        if not RD_path.exists() and MinE_path.exists() and MidE_path.exists():
            
            mid_data = nib.load(str(MidE_path)).get_fdata()
            min_data = nib.load(str(MinE_path)).get_fdata()
            
            rd_data = (mid_data + min_data) / 2.0
            rd_img = nib.Nifti1Image(rd_data, affine=nib.load(str(MidE_path)).affine)
            nib.save(rd_img, str(RD_path))
            

for subject_dir in subjects_folder:
    cal_scalar_map(subject_dir)
# with concurrent.futures.ProcessPoolExecutor(max_workers=10) as executor:
#     executor.map(cal_scalar_map, subjects_folder)
