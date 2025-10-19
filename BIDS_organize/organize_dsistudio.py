from pathlib import Path
import shutil
import os


root_dir = Path('/data/dataset/FiberDataHub/')

for sub_owner in root_dir.iterdir():
    if sub_owner.is_dir():
        if sub_owner.exists() and not any(sub_owner.iterdir()):
            sub_owner.rmdir()
        else:
            for sub_repo in sub_owner.iterdir():
                if sub_repo.is_dir():
                    if sub_repo.exists() and not any(sub_repo.iterdir()):
                        sub_repo.rmdir()
                    else:
                        for sub_data in sub_repo.iterdir():
                            if sub_data.exists() and not any(sub_data.iterdir()):
                                sub_data.rmdir()
                            else:
                                if sub_data.is_dir():
                                    for subject_file in sub_data.iterdir():
                                        if subject_file.is_dir():
                                            continue
                                        subject_prefix = str(subject_file.name).split('.')[0]
                                        partion = subject_prefix.split('_')
                                        if len(partion) == 1:
                                            subject_id = partion[0]
                                            session_id = 'ses-01'
                                        elif len(partion) == 2:
                                            subject_id = partion[0]
                                            if partion[1].startswith('ses-'):
                                                session_id = partion[1]
                                            elif partion[1] == 'dwi':
                                                session_id = 'ses-01'
                                        elif len(partion) == 3:
                                            subject_id = partion[0]
                                            session_id = partion[1]
                                        elif len(partion) > 3:
                                            subject_id = partion[0]
                                            session_id = partion[1]
                                        else:
                                            print(f"Unrecognized file format: {subject_file}")
                                            continue
                                        
                                        new_dir = sub_data / f"{subject_id}" / f"{session_id}" / "dwi" / "gqi"
                                        new_dir.mkdir(parents=True, exist_ok=True)
                                        
                                        new_file_path = new_dir / f"{subject_file.name}"
                                        shutil.move(str(subject_file), str(new_file_path))