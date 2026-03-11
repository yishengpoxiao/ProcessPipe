# import subprocess
# import os
# import glob
# import simplejson as json
# import re
# from multiprocessing import Pool, cpu_count

# input_dir = "/data04/ASD_Li_lab/TD_Time1"


# def process_subject(args):
#     site, subject = args
#     site_path = os.path.join(input_dir, site)
#     subject_path = os.path.join(site_path, subject)

#     if not os.path.isdir(subject_path):
#         print(f"[WARN] Not a dir, skip: {subject_path}")
#         return

#     print(f"[INFO] Start subject: site={site}, subject={subject}")

#     zip_files = glob.glob(os.path.join(subject_path, "*.zip"))
#     if not zip_files:
#         print(f"[WARN] No zip file for subject, skip: {subject_path}")
#         return

#     zip_file = zip_files[0]
#     command = ['unzip', zip_file, '-d', site_path]
#     subprocess.run(command)

#     nifti_convert_dir = os.path.join(subject_path, "nifti_convert")
#     os.makedirs(nifti_convert_dir, exist_ok=True)

#     for session in os.listdir(subject_path):
#         session_path = os.path.join(subject_path, session)
#         if not os.path.isdir(session_path):
#             continue

#         command = [
#             "/home/yijie/dcm2niix",
#             "-f", "%i_%s_%d",
#             "-b", "y",
#             "-z", "y",
#             "-o", nifti_convert_dir,
#             session_path
#         ]
#         subprocess.run(command)

#     for json_file in glob.glob(os.path.join(nifti_convert_dir, "*.json")):
#         with open(json_file) as jf:
#             content = jf.read()
#             content_fixed = re.sub(
#                 r'(?<!\\)\\(?![\\ntr"u])',
#                 r'\\\\',
#                 content
#             )
#             json_data = json.loads(content_fixed, strict=False)

#         bids_guess = json_data.get('BidsGuess', None)

#         prefix = os.path.basename(json_file).replace('.json', '')

#         print(f"[INFO] {site}/{subject} -> {prefix}")

#         if bids_guess is None:
#             new_dir = os.path.join(subject_path, "unknown")
#             os.makedirs(new_dir, exist_ok=True)
#             new_name = f"{subject}_unknown"
#         else:
#             new_dir = os.path.join(subject_path, bids_guess[0])
#             os.makedirs(new_dir, exist_ok=True)

#             description = bids_guess[1].split('_')

#             if len(description) == 4:
#                 run_id = description[2]
#                 modality = description[3]
#                 if modality == 'epi':
#                     modality = 'dwi'
#                 new_name = f"{subject}_{run_id}_{modality}"

#             elif len(description) == 5:
#                 direction = description[2]
#                 run_id = description[3]
#                 modality = description[4]
#                 if modality == 'epi':
#                     modality = 'dwi'
#                 new_name = f"{subject}_{direction}_{run_id}_{modality}"
#             else:
#                 new_dir = os.path.join(subject_path, "unknown")
#                 os.makedirs(new_dir, exist_ok=True)
#                 new_name = f"{subject}_unknown"

#         for ext in ['.nii.gz', '.bval', '.bvec', '.json']:
#             old_file = os.path.join(nifti_convert_dir, prefix + ext)
#             if os.path.exists(old_file):
#                 new_file = os.path.join(new_dir, new_name + ext)
#                 os.rename(old_file, new_file)

#     print(f"[INFO] Finished subject: site={site}, subject={subject}")


# if __name__ == "__main__":
#     subject_list = []

#     for site in os.listdir(input_dir):
#         site_path = os.path.join(input_dir, site)
#         if not os.path.isdir(site_path):
#             continue

#         for subject in os.listdir(site_path):
#             subject_path = os.path.join(site_path, subject)
#             if not os.path.isdir(subject_path):
#                 continue

#             if glob.glob(os.path.join(subject_path, "*.zip")):
#                 subject_list.append((site, subject))

#     print(f"[INFO] Total subjects to process: {len(subject_list)}")

#     # 并行跑
#     NUM_WORKERS = min(4, cpu_count())
#     with Pool(processes=NUM_WORKERS) as pool:
#         pool.map(process_subject, subject_list)

import subprocess
import os
import glob
import simplejson as json
import re
from multiprocessing import Pool, cpu_count

input_dir = "/data04/ASD_Li_lab"


def process_subject(args):
    site, subject = args
    site_path = os.path.join(input_dir, site)
    subject_path = os.path.join(site_path, subject)

    # depth=2: site/subject.zip
    site_level_zip = os.path.join(site_path, f"{subject}.zip")

    # 如果 subject 目录不存在，但 site 下有同名 zip，就创建 subject 目录
    if not os.path.isdir(subject_path):
        if os.path.exists(site_level_zip):
            os.makedirs(subject_path, exist_ok=True)
        else:
            print(f"[WARN] Not a dir and no site-level zip, skip: {subject_path}")
            return

    print(f"[INFO] Start subject: site={site}, subject={subject}")

    # 先找 subject 目录下 zip；没有则找 site 目录下同名 zip
    zip_files = glob.glob(os.path.join(subject_path, "*.zip"))
    if zip_files:
        zip_file = zip_files[0]
    elif os.path.exists(site_level_zip):
        zip_file = site_level_zip
    else:
        print(f"[WARN] No zip file for subject, skip: {subject_path}")
        return

    # 解压到 subject_path（避免并行时在同一 site 目录下混文件）
    command = ['unzip', zip_file, '-d', subject_path]
    subprocess.run(command)

    nifti_convert_dir = os.path.join(subject_path, "nifti_convert")
    os.makedirs(nifti_convert_dir, exist_ok=True)

    # 避免把输出目录当成 session 再喂给 dcm2niix
    skip_dirs = {"nifti_convert", "unknown", "anat", "func", "dwi", "fmap"}

    for session in os.listdir(subject_path):
        if session in skip_dirs:
            continue
        session_path = os.path.join(subject_path, session)
        if not os.path.isdir(session_path):
            continue

        command = [
            "/home/yijie/dcm2niix",
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
            content_fixed = re.sub(
                r'(?<!\\)\\(?![\\ntr"u])',
                r'\\\\',
                content
            )
            json_data = json.loads(content_fixed, strict=False)

        bids_guess = json_data.get('BidsGuess', None)
        prefix = os.path.basename(json_file).replace('.json', '')

        print(f"[INFO] {site}/{subject} -> {prefix}")

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
            else:
                new_dir = os.path.join(subject_path, "unknown")
                os.makedirs(new_dir, exist_ok=True)
                new_name = f"{subject}_unknown"

        for ext in ['.nii.gz', '.bval', '.bvec', '.json']:
            old_file = os.path.join(nifti_convert_dir, prefix + ext)
            if os.path.exists(old_file):
                new_file = os.path.join(new_dir, new_name + ext)
                os.rename(old_file, new_file)

    print(f"[INFO] Finished subject: site={site}, subject={subject}")


if __name__ == "__main__":
    # 用 set 去重：同时兼容 depth=3 和 depth=2
    subject_set = set()

    for site in os.listdir(input_dir):
        site_path = os.path.join(input_dir, site)
        if not os.path.isdir(site_path):
            continue

        # (A) 原逻辑：site/subject/*.zip (depth=3)
        for subject in os.listdir(site_path):
            subject_path = os.path.join(site_path, subject)
            if not os.path.isdir(subject_path):
                continue
            if glob.glob(os.path.join(subject_path, "*.zip")):
                subject_set.add((site, subject))

        # (B) 新增：site/*.zip (depth=2)
        for z in glob.glob(os.path.join(site_path, "*.zip")):
            subject = os.path.basename(z)[:-4]  
            subject_set.add((site, subject))

    subject_list = sorted(subject_set)
    print(f"[INFO] Total subjects to process: {len(subject_list)}")

    NUM_WORKERS = min(4, cpu_count())
    with Pool(processes=NUM_WORKERS) as pool:
        pool.map(process_subject, subject_list)