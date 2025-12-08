import subprocess
from pathlib import Path
import re
import shutil
from typing import Sequence

import numpy as np
import nibabel as nib
from nibabel.tmpdirs import InTemporaryDirectory
from joblib import Parallel, delayed
import argparse

DSI_STUDIO_BIN = Path("/data/yijie/software/dsi-studio/dsi_studio")
DMRISEG_ENV = Path("/data/yijie/miniconda3/envs/dmri_seg/bin/python")
CNN_MASK_SCRIPT = Path("/data/yijie/software/CNN-Diffusion-MRIBrain-Segmentation-1.0/pipeline/dwi_masking.py")
CNN_MODEL_DIR = Path("/data/yijie/software/CNN-Diffusion-MRIBrain-Segmentation-1.0/model_folder")
MNI_TEMPLATE = Path("/data/yijie/Tractography/resources/MNI_FA_template.nii.gz")


def load_bvals(bval_path):
    with open(bval_path, 'r') as f:
        return [float(num) for num in f.read().split()]


def has_b0(bvals, threshold=50):
    return any(b < threshold for b in bvals)


def has_enough_shell(bvals, min_shell=6, threshold=50):
    return sum(1 for b in bvals if b > threshold) >= min_shell


def safe_rmtree(path):
    if path.exists():
        shutil.rmtree(path)
        
        
def safe_unlink(path):
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def join_ids(sub_id: str, ses_id: str, *parts: str) -> str:
    components = [sub_id]
    if ses_id:
        components.append(ses_id)
    components.extend(part for part in parts if part)
    return "_".join(components)


def cleanup_transform_products(transform_dir: Path, sub_id: str, ses_id: str):
    dwi_mni_stem = join_ids(sub_id, ses_id, "dwi_MNI")
    mask_mni_file = transform_dir / f"{join_ids(sub_id, ses_id, 'brain_mask_MNI')}.nii.gz"
    dwi_mni_file = transform_dir / f"{dwi_mni_stem}.nii.gz"
    dwi_mni_bval = transform_dir / f"{dwi_mni_stem}.bval"
    dwi_mni_bvec = transform_dir / f"{dwi_mni_stem}.bvec"
    fa_warped_file = transform_dir / "FA_2_MNIWarped.nii.gz"
    fa_inverse_warped_file = transform_dir / "FA_2_MNIInverseWarped.nii.gz"

    for path in (mask_mni_file, dwi_mni_file, dwi_mni_bval, dwi_mni_bvec, fa_warped_file, fa_inverse_warped_file):
        safe_unlink(path)


def log_error(log_path, message):
    with open(log_path, "a") as f:
        f.write(f"{message}\n")


def run_subprocess(cmd, *, shell=False):
    try:
        subprocess.run(cmd, check=True, shell=shell)
        return True
    except subprocess.CalledProcessError:
        return False


def build_rec_cmd(source, output, save_src, corrections):
    source, output, save_src = map(str, (source, output, save_src))
    correction_steps = [
        "[Step T2][Corrections][Volume Orientation Correction]",
        *corrections,
        "[Step T2][Corrections][Bias Field]",
        "[Step T2][B-table][Check B-table]",
        f"[Step T2][File][Save 4D NIFTI]={output}"
    ]
    return [
        "/data/yijie/software/dsi-studio/dsi_studio",
        "--action=rec",
        "--volume_correction=1",
        "--check_btable=1",
        f"--source={source}",
        f'--cmd="{"+".join(correction_steps)}"',
        f"--save_src={save_src}"
    ]


def run_with_fallback(commands):
    for cmd in commands:
        if run_subprocess(cmd):
            return True
    return False


def parse_fsl_affine(file):
    with open(file) as f:
        lines = f.readlines()
    entries = [l.split() for l in lines]
    entries = [row for row in entries if len(row) > 0]  # remove empty rows
    return np.array(entries).astype(np.float32)


def read_bvecs(this_fname):
    """
    Adapted from dipy.io.read_bvals_bvecs
    """
    with open(this_fname, 'r') as f:
        content = f.read()
    # We replace coma and tab delimiter by space
    with InTemporaryDirectory():
        tmp_fname = "tmp_bvals_bvecs.txt"
        with open(tmp_fname, 'w') as f:
            f.write(re.sub(r'(\t|,)', ' ', content))
        return np.squeeze(np.loadtxt(tmp_fname)).T
    

def new_bvecs(this_fname):
    bvecs = read_bvecs(this_fname)
    if bvecs.shape[0] == 3:
        bvecs = np.array(bvecs)
    else:        
        bvecs = np.array(bvecs).T  # change shape from [nr_vecs, 3] to [3, nr_vecs]
        
    bvecs_norm = np.linalg.norm(bvecs, axis=0)
    idx = bvecs_norm != 0
    bvecs[:, idx] /= bvecs_norm[idx]

    np.savetxt(this_fname, bvecs, fmt='%1.6f')


def rotate_bvecs(bvecs_in, affine_in, bvecs_out):
    bvecs = read_bvecs(bvecs_in)

    affine = parse_fsl_affine(affine_in)

    # Almost identical code to img_utils.apply_rotation_to_peaks except for order of peak array dims
    affine = affine[:3, :3]

    # Get rotation component of affine transformation
    len = np.linalg.norm(affine, axis=0)
    safe = len.copy()
    safe[safe == 0] = 1.0
    rotation = np.zeros((3,3))
    rotation[:, 0] = affine[:, 0] / safe[0]
    rotation[:, 1] = affine[:, 1] / safe[1]
    rotation[:, 2] = affine[:, 2] / safe[2]

    # Apply rotation to bvecs
    # check bvecs shape
    if bvecs.shape[0] == 3:
        bvecs = np.array(bvecs)
    else:        
        bvecs = np.array(bvecs).T  # change shape from [nr_vecs, 3] to [3, nr_vecs]
    rotated_bvecs = np.matmul(rotation, bvecs)  # output shape [3, nr_vecs]
    
    # Normalize bvecs
    rotated_bvecs = rotated_bvecs.copy()  # Avoid in-place modification.
    bvecs_norm = np.linalg.norm(rotated_bvecs, axis=0)
    idx = bvecs_norm != 0
    rotated_bvecs[:, idx] /= bvecs_norm[idx]

    np.savetxt(bvecs_out, rotated_bvecs, fmt='%1.6f')


def find_phase_dir(file_path):
    name = file_path.name.casefold()
    patterns = {
        "ap": r"(?:^|[\W_])a[\-_]?p(?=$|[\W_])",
        "pa": r"(?:^|[\W_])p[\-_]?a(?=$|[\W_])",
        "lr": r"(?:^|[\W_])l[\-_]?r(?=$|[\W_])",
        "rl": r"(?:^|[\W_])r[\-_]?l(?=$|[\W_])",
        "si": r"(?:^|[\W_])s[\-_]?i(?=$|[\W_])",
        "is": r"(?:^|[\W_])i[\-_]?s(?=$|[\W_])",
    }
    for key, pattern in patterns.items():
        if re.search(pattern, name):
            return key
    return None


def sort_files(file_list):
    def read_bvals_count(f: Path) -> int:
        bval_f = f.with_suffix("").with_suffix(".bval")
        return len(load_bvals(bval_f))
    
    return sorted(file_list, key=read_bvals_count, reverse=True)


DEFAULT_SESSION_ID = ""


def iter_session_dwi_dirs(sub_dir: Path):
    """
    Yield tuples of (session_id, dwi_directory) for a subject directory.

    The function first looks for session-level directories that contain a ``dwi``
    folder (e.g. ``sub-01/ses-01/dwi``).  When no such directory is found, a
    fallback to ``sub-01/dwi`` is used so that datasets without an explicit
    session hierarchy are still processed.
    """

    session_dirs = []
    try:
        children = list(sub_dir.iterdir())
    except OSError:
        return []

    for child in children:
        if not child.is_dir():
            continue
        dwi_dir = child / "dwi"
        if dwi_dir.is_dir():
            session_dirs.append((child.name, dwi_dir))

    if session_dirs:
        return session_dirs

    fallback_dwi = sub_dir / "dwi"
    if fallback_dwi.is_dir():
        return [(DEFAULT_SESSION_ID, fallback_dwi)]

    return []


args = argparse.ArgumentParser()
# input_dir累加列表
args.add_argument("-i", "--input_dir", dest="input_dir", type=str, action="append", required=True, help="Input directory containing subject folders.")
args = args.parse_args()

input_dirs = [Path(p).resolve() for p in args.input_dir]
error_log = '/data/dataset/dmri_preprocess_error.log'
sub_dirs = []

for input_dir in input_dirs:
    sub_dirs.extend([d for d in input_dir.iterdir() if d.is_dir()])


def process_subjects(sub_dir):
    sub_id = sub_dir.name

    for ses_id, dwi_dir in iter_session_dwi_dirs(sub_dir):
        
        nifti_files = sorted(dwi_dir.glob('*.nii.gz'))
        if not nifti_files:
            continue
        
        grad_dir = dwi_dir / 'gradcheck'
        dsi_process_dir = dwi_dir / 'dsi_studio'
        processed_dir = dwi_dir / 'processed'
        transform_dir = dwi_dir / 'transform'
        gqi_dir = dwi_dir / 'gqi'
        dwi_stem = join_ids(sub_id, ses_id, "dwi")
        gqi_file = gqi_dir / f"{dwi_stem}.gqi.fz"
        
        if gqi_file.exists():
            cleanup_transform_products(transform_dir, sub_id, ses_id)
            continue
        
        session_prefix = join_ids(sub_id, ses_id)
        processed_stem = join_ids(sub_id, ses_id, "dwi_processed")
        brain_mask_stem = join_ids(sub_id, ses_id, "dwi_processed_bse-multi_BrainMask")
        dwi_mni_stem = join_ids(sub_id, ses_id, "dwi_MNI")

        for path in (dsi_process_dir, processed_dir, transform_dir, gqi_dir, grad_dir):
            path.mkdir(parents=True, exist_ok=True)

        def cleanup_failure():
            for path in (dsi_process_dir, processed_dir, transform_dir, gqi_dir, grad_dir):
                safe_rmtree(path)
        
        tagged = []
        for p in nifti_files:
            if 'unknown' in p.name:
                tagged.append((p, 'unknown'))
                continue

            pd = find_phase_dir(p)
            tagged.append((p, pd if pd is not None else "main"))

        phase_files_dict = {}
        min_run = float('inf')
        min_pd = None
        
        for p, pd in tagged:
            if pd == 'unknown':
                log_error(error_log, f"unknown file in {dwi_dir}: {p}")
                continue
            
            bval_p = p.with_suffix("").with_suffix(".bval")
            bvec_p = p.with_suffix("").with_suffix(".bvec")
            if not bval_p.exists():
                log_error(error_log, f"missing bval file in {dwi_dir}: {p}")
                continue
            
            if not bvec_p.exists():
                log_error(error_log, f"missing bvec file in {dwi_dir}: {p}")
                continue
            
            try:
                bvals = load_bvals(bval_p)
            except ValueError:
                log_error(error_log, f"invalid bval file in {dwi_dir}: {bval_p}")
                continue
            
            try:
                bvecs = read_bvecs(bvec_p)
                if bvecs.shape[0] == 3:
                    bvecs = np.array(bvecs)
                else:        
                    bvecs = np.array(bvecs).T
            except Exception:
                log_error(error_log, f"invalid bvec file in {dwi_dir}: {bvec_p}")
                continue
            
            if not has_b0(bvals):
                log_error(error_log, f"no b0 image in {dwi_dir}: {p}")
                continue
            
            try:
                img = nib.load(p)
            except Exception:
                log_error(error_log, f"failed to load nifti in {dwi_dir}: {p}")
                continue

            if len(img.shape) != 4 or img.shape[3] != len(bvals) or img.shape[3] != bvecs.shape[1]:
                log_error(error_log, f"mismatched bvals, bvecs, and nifti dimensions in {dwi_dir}: {p}")
                continue
            
            run_match = re.search(r"run-(\d+)", p.name)
            if run_match:
                run_idx = int(run_match.group(1))
                if run_idx < min_run:
                    min_run = run_idx
                    min_pd = pd
            
            phase_files_dict.setdefault(pd, []).append(p)
            
        if not phase_files_dict:
            cleanup_failure()
            continue
        
        if len(phase_files_dict) > 2:
            log_error(error_log, f"more than 2 phase encoding directions in {dwi_dir}")
            phase_keys = list(phase_files_dict.keys())
            for pk in phase_keys:
                if pk != min_pd and pk != min_pd[::-1]:
                    del phase_files_dict[pk]
        
        phase_files_dict_gc = {}
        for pd, files in phase_files_dict.items():
            new_list = []
            for p in files:
                bval_p = p.with_suffix("").with_suffix(".bval")
                bvec_p = p.with_suffix("").with_suffix(".bvec")
                
                if not (bval_p.exists() and bvec_p.exists()):
                    log_error(error_log, f"missing bval/bvec in {dwi_dir}: {p}")
                    continue
                
                out_bvec = grad_dir / bvec_p.name
                out_bval = grad_dir / bval_p.name

                cmd = [
                    "dwigradcheck",
                    str(p),
                    "-fslgrad", str(bvec_p), str(bval_p),
                    "-export_grad_fsl", str(out_bvec), str(out_bval),
                    "-force",
                    "-nthread", "80",
                ]
                if not run_subprocess(cmd):
                    log_error(error_log, f"dwigradcheck failed in {dwi_dir}: {p}")
                    continue

                link_p = grad_dir / p.name
                if not link_p.exists():
                    link_p.symlink_to(p)

                new_list.append(link_p)
            
            if new_list:
                phase_files_dict_gc[pd] = new_list
                
        phase_files_dict = phase_files_dict_gc
        if not phase_files_dict:
            log_error(error_log, f"no valid file after gradcheck in {dwi_dir}")
            cleanup_failure()
            continue
        
        if 'main' in phase_files_dict:
            min_pd = 'main'
        elif min_pd not in phase_files_dict:
            min_pd = max(phase_files_dict, key=lambda k: len(phase_files_dict[k]))
        
        def find_direction(files, tol=50):
            d_count = 0
            for f in files:
                bval_f = f.with_suffix("").with_suffix(".bval")
                try:
                    bvals = load_bvals(bval_f)
                except ValueError:
                    log_error(error_log, f"invalid bval file in {dwi_dir}: {bval_f}")
                    continue
                
                d_count += sum(1 for b in bvals if b > tol)
            return d_count

        dir_count = {pd: find_direction(files) for pd, files in phase_files_dict.items()}
        
        if not dir_count:
            cleanup_failure()
            continue
        else:
            max_dir_pd = max(dir_count, key=lambda k: dir_count[k])
            if dir_count[max_dir_pd] < 6:
                log_error(error_log, f"not enough b-shell image in {dwi_dir}")
                cleanup_failure()
                continue
        
        print(dwi_dir)
        if min_pd != max_dir_pd:
            min_pd = max_dir_pd
        
        if not phase_files_dict:
            cleanup_failure()
            continue
        
        if len(phase_files_dict) > 2:
            log_error(error_log, f"more than 2 phase encoding directions in {dwi_dir} after gradcheck")
            phase_keys = list(phase_files_dict.keys())
            for pk in phase_keys:
                if pk != min_pd and pk != min_pd[::-1]:
                    del phase_files_dict[pk]
        
        if len(phase_files_dict) == 1:
            
            pd = next(iter(phase_files_dict))
            pd_files = sort_files(phase_files_dict[pd])

            src = str(pd_files[0])
            others = [str(p) for p in pd_files[1:]]

            sz_file = dsi_process_dir / f"{dwi_stem}.sz"
            if not sz_file.exists():
                cmd = [
                    str(DSI_STUDIO_BIN),
                    "--action=src",
                    f"--source={src}",
                    f"--output={sz_file}",
                ]
                if others:
                    cmd.append(f"--other_source={','.join(others)}")
                if not run_subprocess(cmd):
                    log_error(error_log, f"dsi-studio src failed in {dwi_dir}")
                    cleanup_failure()
                    continue

            preprocessed_file = processed_dir / f"{processed_stem}.nii.gz"
            preprocessed_src = preprocessed_file.with_suffix('').with_suffix('.sz')
            if not preprocessed_file.exists():
                rec_commands = [
                    build_rec_cmd(sz_file, preprocessed_file, preprocessed_src, ["[Step T2][Corrections][EDDY]"]),
                    build_rec_cmd(sz_file, preprocessed_file, preprocessed_src, ["[Step T2][Corrections][Motion Correction]"]),
                ]
                if not run_with_fallback(rec_commands):
                    log_error(error_log, f"preprocessing failed in {dwi_dir}")
                    cleanup_failure()
                    continue
        else:
            phase_keys = list(phase_files_dict.keys())
            if min_pd not in phase_keys:
                min_pd = max(phase_files_dict, key=lambda k: len(phase_files_dict[k]))
            rev_pd = phase_keys[0] if phase_keys[1] == min_pd else phase_keys[1]
            
            main_files = sort_files(phase_files_dict[min_pd])
            rev_files = sort_files(phase_files_dict[rev_pd])
            
            main_src = main_files[0]
            main_sz_file = dsi_process_dir / f"{join_ids(sub_id, ses_id, 'dwi_main_phase_dir')}.sz"
            main_others = [str(p) for p in main_files[1:]]
            if not main_sz_file.exists():
                cmd = [
                    str(DSI_STUDIO_BIN),
                    "--action=src",
                    f"--source={main_src}",
                    f"--output={main_sz_file}",
                ]
                if main_others:
                    cmd.append(f"--other_source={','.join(main_others)}")
                if not run_subprocess(cmd):
                    log_error(error_log, f"dsi-studio src failed for main phase in {dwi_dir}")
                    cleanup_failure()
                    continue

            rev_src = rev_files[0]
            rev_sz_file = dsi_process_dir / f"{join_ids(sub_id, ses_id, 'dwi_rev_phase_dir')}.sz"
            rev_others = [str(p) for p in rev_files[1:]]
            if not rev_sz_file.exists():
                cmd = [
                    str(DSI_STUDIO_BIN),
                    "--action=src",
                    f"--source={rev_src}",
                    f"--output={rev_sz_file}",
                ]
                if rev_others:
                    cmd.append(f"--other_source={','.join(rev_others)}")
                if not run_subprocess(cmd):
                    log_error(error_log, f"dsi-studio src failed for reverse phase in {dwi_dir}")
                    cleanup_failure()
                    continue

            preprocessed_file = processed_dir / f"{processed_stem}.nii.gz"
            preprocessed_src = preprocessed_file.with_suffix("").with_suffix(".sz")
            if not preprocessed_file.exists():
                rec_commands = [
                    build_rec_cmd(
                        main_sz_file,
                        preprocessed_file,
                        preprocessed_src,
                        [f"[Step T2][Corrections][TOPUP EDDY]={rev_sz_file}"],
                    ),
                    build_rec_cmd(main_sz_file, preprocessed_file, preprocessed_src, ["[Step T2][Corrections][EDDY]"]),
                    build_rec_cmd(main_sz_file, preprocessed_file, preprocessed_src, ["[Step T2][Corrections][Motion Correction]"]),
                ]
                if not run_with_fallback(rec_commands):
                    log_error(error_log, f"preprocessing failed in {dwi_dir}")
                    cleanup_failure()
                    continue

        preprocessed_file = processed_dir / f"{processed_stem}.nii.gz"
        if not preprocessed_file.exists():
            log_error(error_log, f"preprocessed nifti not found in {dwi_dir}")
            cleanup_failure()
            continue
        
        preprocessed_src = preprocessed_file.with_suffix("").with_suffix(".sz")
        
        preprocessed_bval_file = preprocessed_file.with_suffix("").with_suffix(".bval")
        preprocessed_bvec_file = preprocessed_file.with_suffix("").with_suffix(".bvec")
        if not preprocessed_bval_file.exists() or not preprocessed_bvec_file.exists():
            log_error(error_log, f"missing bval/bvec for preprocessed nifti in {dwi_dir}")
            cleanup_failure()
            continue
        
        try:
            preprocessed_bvals = load_bvals(preprocessed_bval_file)
        except ValueError:
            log_error(error_log, f"invalid bval file for preprocessed nifti in {dwi_dir}")
            cleanup_failure()
            continue
        
        if not has_b0(preprocessed_bvals):
            log_error(error_log, f"no b0 image in preprocessed nifti in {dwi_dir}")
            cleanup_failure()
            continue
        
        if not has_enough_shell(preprocessed_bvals):
            log_error(error_log, f"not enough b-shell image in preprocessed nifti in {dwi_dir}")
            cleanup_failure()
            continue
            
        txt_file = processed_dir / f"{session_prefix}.txt"
        with open(txt_file, "w") as f:
            f.write(f"{preprocessed_file}\n")

        brain_mask_file = processed_dir / f"{brain_mask_stem}.nii.gz"
        if not brain_mask_file.exists():
            cmd = [
                str(DMRISEG_ENV),
                str(CNN_MASK_SCRIPT),
                "-i",
                str(txt_file),
                "-f",
                str(CNN_MODEL_DIR),
            ]
            if not run_subprocess(cmd):
                log_error(error_log, f"brain mask generation failed in {dwi_dir}")
                cleanup_failure()
                continue
            
        def rm_mask_tmp_files(process_dir):
            process_dir = Path(process_dir)
            tmp_files = list(process_dir.glob(f"*binary_s")) + list(process_dir.glob(f"*binary_c")) + list(process_dir.glob(f"*binary_a"))
            for tf in tmp_files:
                safe_unlink(tf)
        
        rm_mask_tmp_files(processed_dir)

        new_bvecs(preprocessed_bvec_file)
            
        dti_dir = processed_dir / "dti"
        dti_dir.mkdir(parents=True, exist_ok=True)
        
        fa_path = dti_dir / "dti_FA.nii.gz"
        if not fa_path.exists():
            cmd = [
                "dtifit",
                "-k", str(preprocessed_file),
                "-o", str(dti_dir / "dti"),
                "-m", str(brain_mask_file),
                "-r", str(preprocessed_bvec_file),
                "-b", str(preprocessed_bval_file),
            ]
            if not run_subprocess(cmd):
                log_error(error_log, f"dtifit failed in {dwi_dir}")
                cleanup_failure()
                continue
                
        affine_file = transform_dir / "FA_2_MNI0GenericAffine.mat"
        if not affine_file.exists():
            cmd = [
                "antsRegistrationSyNQuick.sh",
                "-d", "3",
                "-f", str(MNI_TEMPLATE),
                "-m", str(fa_path),
                "-o", str(transform_dir / "FA_2_MNI"),
                "-t", "r",
                "-n", "-1",
            ]
            if not run_subprocess(cmd):
                log_error(error_log, f"antsRegistrationSyNQuick failed in {dwi_dir}")
                cleanup_failure()
                continue
        
        affine_mat_file = transform_dir / "FA_2_MNI.mat"
        if not affine_mat_file.exists():
            cmd = [
                "ConvertTransformFile",
                "3",
                str(affine_file),
                str(affine_mat_file),
                "--hm",
            ]
            if not run_subprocess(cmd):
                log_error(error_log, f"ConvertTransformFile failed in {dwi_dir}")
                cleanup_failure()
                continue         

        dwi_nifti_in_mni = transform_dir / f"{dwi_mni_stem}.nii.gz"
        if not dwi_nifti_in_mni.exists():
            cmd = [
                "antsApplyTransforms",
                "-d", "3",
                "-e", "3",
                "-i", str(preprocessed_file),
                "-r", str(MNI_TEMPLATE),
                "-o", str(dwi_nifti_in_mni),
                "-t", str(affine_file),
                "-n", "BSpline",
            ]
            if not run_subprocess(cmd):
                log_error(error_log, f"antsApplyTransforms failed for dwi in {dwi_dir}")
                cleanup_failure()
                continue
            
        dwi_bval_in_mni = transform_dir / f"{dwi_mni_stem}.bval"
        if not dwi_bval_in_mni.exists():
            shutil.copy(preprocessed_bval_file, dwi_bval_in_mni)
        
        dwi_bvec_in_mni = transform_dir / f"{dwi_mni_stem}.bvec"
        if not dwi_bvec_in_mni.exists():
            try:
                rotate_bvecs(str(preprocessed_bvec_file), str(affine_mat_file), str(dwi_bvec_in_mni))
            except Exception:
                log_error(error_log, f"failed to rotate bvecs in {dwi_dir}")
                cleanup_failure()
                continue
        
        mask_in_mni = transform_dir / f"{join_ids(sub_id, ses_id, 'brain_mask_MNI')}.nii.gz"
        if not mask_in_mni.exists():
            cmd = [
                "antsApplyTransforms",
                "-d", "3",
                "-i", str(brain_mask_file),
                "-r", str(MNI_TEMPLATE),
                "-o", str(mask_in_mni),
                "-t", str(affine_file),
                "-n", "NearestNeighbor",
            ]
            if not run_subprocess(cmd):
                log_error(error_log, f"antsApplyTransforms failed for mask in {dwi_dir}")
                cleanup_failure()
                continue
            
        gqi_prefix = gqi_dir / dwi_stem
        if not gqi_file.exists():
            cmd = [
                str(DSI_STUDIO_BIN),
                "--action=rec",
                f"--source={dwi_nifti_in_mni}",
                "--method=4",
                "--param0=1.25",
                f"--mask={mask_in_mni}",
                "--apply_mask",
                f"--output={gqi_prefix}",
            ]
            if not run_subprocess(cmd):
                log_error(error_log, f"GQI reconstruction failed in {dwi_dir}")
                cleanup_failure()
                continue
            
        cleanup_transform_products(transform_dir, sub_id, ses_id)

        safe_rmtree(dsi_process_dir)
        safe_rmtree(dti_dir)
        for path in (processed_dir, transform_dir, gqi_dir):
            if path.exists() and not any(path.iterdir()):
                path.rmdir()

tmp = Parallel(n_jobs=20, backend='loky')(
    delayed(process_subjects)(sub_dir) for sub_dir in sub_dirs
)
