import os
import subprocess
import glob
import numpy as np
from joblib import Parallel, delayed

root_dir = '/data/dataset/ABVIB/ABVIB/'
output_dir = '/data/dataset/ABVIB/nifti/'
os.makedirs(output_dir, exist_ok=True)


def group_convert(dcm_dir, nifti_dir):
    if not os.path.isdir(dcm_dir):
        return

    os.makedirs(nifti_dir, exist_ok=True)

    year_list = []

    for modality in os.listdir(dcm_dir):
        for year in os.listdir(os.path.join(dcm_dir, modality)):
            year_list.append(year[:7])

    year_list = sorted(list(set(year_list)))

    for modality in os.listdir(dcm_dir):
        for year in os.listdir(os.path.join(dcm_dir, modality)):
            ses_idx = np.where(np.array(year_list) == year[:7])[0][0] + 1
            ses_dir = os.path.join(nifti_dir, f'ses-{ses_idx:02d}')
            os.makedirs(ses_dir, exist_ok=True)

            exact_dcm_dir = os.path.dirname(glob.glob(os.path.join(dcm_dir, modality, year, '**', '*.dcm'), recursive=True)[0])
            command = ["/data/yijie/software/dcm2niix", "-f", "%i_%s_%d", "-b", "y", "-z", "y", "-o", ses_dir, exact_dcm_dir]
            subprocess.run(command)


subjects = []

for sub_id in os.listdir(root_dir):
    sub_dir = os.path.join(root_dir, sub_id)
    if not os.path.isdir(sub_dir):
        continue

    subjects.append(sub_dir)

tmp = Parallel(n_jobs=30, backend='loky')(delayed(group_convert)(sub_dir, os.path.join(output_dir, os.path.basename(sub_dir))) for sub_dir in subjects)
