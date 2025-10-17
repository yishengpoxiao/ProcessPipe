import os
from pathlib import Path
import shutil
import simplejson as json
import re


def has_sidecars(stem):
    return all((stem.with_suffix(sfx)).exists() for sfx in ('.bval', '.bvec', '.json'))


def dwi_has_multi_dirs(stem):
    bval_path = stem.with_suffix('.bval')
    try:
        with open(bval_path, 'r') as f:
            bvals = [float(num) for num in f.read().split()]
        return len(bvals) > 1
    except Exception:
        return False


def phase_dir(file_path):
    name = file_path.name.casefold()
    if re.search(r'(?:^|(?:\W|_))a[\-_]?p(?=$|(?:\W|_))', name):
        return 'ap'
    if re.search(r'(?:^|(?:\W|_))p[\-_]?a(?=$|(?:\W|_))', name):
        return 'pa'
    if re.search(r'(?:^|(?:\W|_))l[\-_]?r(?=$|(?:\W|_))', name):
        return 'lr'
    if re.search(r'(?:^|(?:\W|_))r[\-_]?l(?=$|(?:\W|_))', name):
        return 'rl' 
    if re.search(r'(?:^|(?:\W|_))s[\-_]?i(?=$|(?:\W|_))', name):
        return 'si'
    if re.search(r'(?:^|(?:\W|_))i[\-_]?s(?=$|(?:\W|_))', name):
        return 'is'
    return None


def keep_file(nifti_path):
    base = nifti_path.name
    # rule 1：AP/PA
    pd = phase_dir(nifti_path)
    if pd in ('ap', 'pa', 'lr', 'rl', 'si', 'is'):
        return True
    # rule 2：true dwi
    if has_sidecars(nifti_path.with_suffix('')) and dwi_has_multi_dirs(nifti_path.with_suffix('')):
        return True
    return False


def move_with_sidecars(src_nifti, dst_nifti):
    dst_nifti.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src_nifti), str(dst_nifti))
    stem_src = src_nifti.with_suffix('')
    stem_dst = dst_nifti.with_suffix('')
    for sfx in ('.bval', '.bvec', '.json'):
        p_src = stem_src.with_suffix(sfx)
        if p_src.exists():
            shutil.move(str(p_src), str(stem_dst.with_suffix(sfx)))

root_dir = Path('/data/dataset/ABVIB/nifti')

for sub_dir in root_dir.iterdir():
    if not sub_dir.is_dir():
        continue
    sub_id = sub_dir.name

    for ses_dir in sub_dir.iterdir():
        if not ses_dir.is_dir():
            continue
        ses_id = ses_dir.name
        
        dwi_dir = ses_dir / 'dwi'
        
        nifti_files = sorted(ses_dir.glob('*.nii.gz'))

        keep = [p for p in nifti_files if keep_file(p)]
        drop = [p for p in nifti_files if p not in keep]
        
        for r_file in drop:
            r_stem = r_file.with_suffix('')
            for path in (r_file, r_stem.with_suffix('.bval'), r_stem.with_suffix('.bvec'), r_stem.with_suffix('.json')):
                if path.exists():
                    path.unlink()
        
        if len(keep) == 0:
            try:
                if not any(ses_dir.iterdir()):
                    ses_dir.rmdir()
            except FileNotFoundError:
                pass
            
            continue

        remaining = []
        for f in keep:
            json_file = f.with_suffix('').with_suffix('.json')

            with json_file.open() as jf:
                content = jf.read()
                content_fixed = re.sub(r'(?<!\\)\\(?![\\ntr"u])', r'\\\\', content)
                json_data = json.loads(content_fixed, strict=False)
            
            bids_guess = json_data.get('BidsGuess', None)
            
            if bids_guess is None:
                new_name = f"{sub_id}_{ses_id}_unknown.nii.gz"
            else:
                description = bids_guess[1].split('_')
                
                if len(description) == 4:
                    run_id = description[2]
                    modality = description[3]
                    new_name = f"{sub_id}_{ses_id}_{run_id}_{modality}.nii.gz"
                elif len(description) == 5:     
                    direction = description[2]
                    run_id = description[3]
                    modality = description[4]
                    
                    new_name = f"{sub_id}_{ses_id}_{direction}_{run_id}_{modality}.nii.gz"
                    
            move_with_sidecars(f, dwi_dir / new_name)
    