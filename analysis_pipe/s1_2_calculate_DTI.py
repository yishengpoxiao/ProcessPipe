from pathlib import Path
import subprocess
import os


SlicerPath = "/data01/software/Slicer-5.2.2-linux-amd64/Slicer"

root_dir = Path('/data04/ASD_Li_lab/2B_pre')

subjects_folder = []

for site_folder in root_dir.iterdir():
    if site_folder.is_dir():
        for subject_folder in site_folder.iterdir():
            if subject_folder.is_dir():
                subjects_folder.append(subject_folder)
                

def cal_DTI(subject_dir):
    subfolder_name = os.path.basename(subject_dir)
    
    print(f"----- DTI calculation for {subfolder_name} -----")
    
    dwi_folders = subject_dir.glob('**/dwi')
    
    for dwi_folder in dwi_folders:
        print(dwi_folder)
        qc_folder = dwi_folder / 'corrected_masked'
        
        dwi_files = sorted(Path(qc_folder).glob(f'*_QCed.nrrd'))
        print(f"dwi_files: {dwi_files}")
        
        dti_dir = dwi_folder / 'DTI'
        dti_dir.mkdir(parents=True, exist_ok=True)
        
        for dwi_file in dwi_files:
            base_name = dwi_file.name.replace('_QCed.nrrd', '')
            
            mask_file = qc_folder / dwi_file.name.replace('.nrrd', '_bse-multi_BrainMask.nhdr')
            
            cmd = [SlicerPath,
                '--launch', '/data01/software/Slicer-5.2.2-linux-amd64/NA-MIC/Extensions-31382/SlicerDMRI/lib/Slicer-5.2/cli-modules/DWIToDTIEstimation',
                '-m', str(mask_file),
                str(dwi_file),
                str(dti_dir / f'{base_name}_DTI.nrrd'),
                str(dti_dir / f'{base_name}_b0.nrrd')]
            subprocess.run(cmd)
            
for subject_dir in subjects_folder:
    cal_DTI(subject_dir)
