from pathlib import Path
import shutil


root_dir = Path('/data04/ASD_Li_lab/2B_pre')
download_dir = Path('/data04/ASD_Li_lab/results/download')
download_dir.mkdir(parents=True, exist_ok=True)

for site_folder in root_dir.iterdir():
    site_name = site_folder.name
    
    if site_folder.is_dir():  
        for subject_folder in site_folder.iterdir():
            if subject_folder.is_dir():
                subject_id = subject_folder.name
                dest_folder = download_dir / site_folder.name
                dest_folder.mkdir(parents=True, exist_ok=True)
                DTI_file = list(subject_folder.rglob('**/dwi/DTI/*_DTI.nrrd'))[0]
                
                dest_file = dest_folder / DTI_file.name
                shutil.copy2(DTI_file, dest_file)