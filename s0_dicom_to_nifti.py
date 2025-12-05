import subprocess
import os, glob
import simplejson as json
import re


input_dir = "/data/private_data/ASD_Li_lab"

for site in os.listdir(input_dir):
    site_path = os.path.join(input_dir, site)
    if not os.path.isdir(site_path):
        continue

    for subject in os.listdir(site_path):
        subject_path = os.path.join(site_path, subject)
        if not os.path.isdir(subject_path):
            continue

        # unzip file
        zip_file = glob.glob(os.path.join(subject_path, "*.zip"))
        command = ['unzip', zip_file[0], '-d', site_path]
        subprocess.run(command)
        
        nifti_convert_dir = os.path.join(subject_path, "nifti_convert")
        os.makedirs(nifti_convert_dir, exist_ok=True)
        
        for session in os.listdir(subject_path):
            session_path = os.path.join(subject_path, session)
            if not os.path.isdir(session_path):
                continue
            
            command = [
                "/data/software/dcm2niix",
                "-f", "%i_%s_%d",
                "-b", "y",
                "-z", "y",
                "-o", nifti_convert_dir,
                session_path
            ]
            subprocess.run(command)
            
        for json_file in glob.glob(os.path.join(nifti_convert_dir, "*.json")):
            with open(json_file) as jf:
                content = jf.read()
                content_fixed = re.sub(r'(?<!\\)\\(?![\\ntr"u])', r'\\\\', content)
                json_data = json.loads(content_fixed, strict=False)
            
            bids_guess = json_data.get('BidsGuess', None)
            
            prefix = os.path.basename(json_file).replace('.json', '')
            
            print(prefix)
            
            if bids_guess is None:
                new_dir = os.path.join(subject_path, "unknown")
                os.makedirs(new_dir, exist_ok=True)
                
                new_name = f"{subject}_unknown"
            else:
                new_dir = os.path.join(subject_path, bids_guess[0])
                os.makedirs(new_dir, exist_ok=True)
                
                description = bids_guess[1].split('_')
                
                if len(description) == 4:
                    run_id = description[2]
                    modality = description[3]
                    if modality == 'epi':
                        modality = 'dwi'
                    new_name = f"{subject}_{run_id}_{modality}"
                elif len(description) == 5:     
                    direction = description[2]
                    run_id = description[3]
                    modality = description[4]
                    if modality == 'epi':
                        modality = 'dwi'
                    
                    new_name = f"{subject}_{direction}_{run_id}_{modality}"
                
            for ext in ['.nii.gz', '.bval', '.bvec', '.json']:
                old_file = os.path.join(nifti_convert_dir, prefix + ext)
                if os.path.exists(old_file):
                    new_file = os.path.join(new_dir, new_name + ext)
                    os.rename(old_file, new_file)
        