import simplejson as json
import shutil
from pathlib import Path
import re

root_dir = Path('/data/dataset/PPMI/nifti')

for sub_dir in root_dir.iterdir():
    if not sub_dir.is_dir():
        continue
    sub_id = sub_dir.name

    for ses_dir in sub_dir.iterdir():
        if not ses_dir.is_dir():
            continue
        ses_id = ses_dir.name
        
        dwi_dir = ses_dir / 'dwi'
        
        nifti_files = sorted(dwi_dir.glob('*.nii.gz'))
        
        for f in nifti_files:
            json_file = f.with_suffix('').with_suffix('.json')

            with json_file.open() as jf:
                content = jf.read()
                content_fixed = re.sub(r'(?<!\\)\\(?![\\ntr"u])', r'\\\\', content)
                json_data = json.loads(content_fixed, strict=False)
            
            bids_guess = json_data.get('BidsGuess', None)
            
            print(json_file)
            
            if bids_guess is None:
                new_name = f"{sub_id}_{ses_id}_unknown.nii.gz"

                shutil.move(str(f), str(dwi_dir / new_name))
                shutil.move(str(f.with_suffix('').with_suffix('.bval')), str((dwi_dir / new_name).with_suffix('').with_suffix('.bval')))
                shutil.move(str(f.with_suffix('').with_suffix('.bvec')), str((dwi_dir / new_name).with_suffix('').with_suffix('.bvec')))
                shutil.move(str(json_file), str((dwi_dir / new_name).with_suffix('').with_suffix('.json')))

            else:
                description = bids_guess[1].split('_')
                
                if len(description) == 4:
                    run_id = description[2]
                    modality = description[3]
                    if modality == 'epi':
                        modality = 'dwi'
                    new_name = f"{sub_id}_{ses_id}_{run_id}_{modality}.nii.gz"
                elif len(description) == 5:     
                    direction = description[2]
                    run_id = description[3]
                    modality = description[4]
                    if modality == 'epi':
                        modality = 'dwi'
                    
                    new_name = f"{sub_id}_{ses_id}_{direction}_{run_id}_{modality}.nii.gz"
                
                shutil.move(str(f), str(dwi_dir / new_name))
                shutil.move(str(f.with_suffix('').with_suffix('.bval')), str((dwi_dir / new_name).with_suffix('').with_suffix('.bval')))
                shutil.move(str(f.with_suffix('').with_suffix('.bvec')), str((dwi_dir / new_name).with_suffix('').with_suffix('.bvec')))
                shutil.move(str(json_file), str((dwi_dir / new_name).with_suffix('').with_suffix('.json')))
