import pathlib
import subprocess
import sys
import os
import re
import shutil
import simplejson as json
import traceback
import tempfile
from datetime import datetime

import numpy as np
import nibabel as nib
from nibabel.tmpdirs import InTemporaryDirectory
from multiprocessing import Pool

log_txt = "/data/dataset/HABS_HD_bak/process_log.txt"
MNI_TEMPLATE = pathlib.Path("/data/yijie/Tractography/resources/MNI_FA_template.nii.gz")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_json_control_chars(json_path: pathlib.Path):
    if not json_path.exists():
        return

    try:
        with open(json_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_content = f.read()
            
        clean_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', raw_content)
        
        clean_content = re.sub(
            r'("SequenceVariant"\s*:\s*").*?"(\s*[,}])', 
            r'\1REMOVED_GARBAGE"\2', 
            clean_content
        )
        
        try:
            json.loads(clean_content)
        except json.JSONDecodeError as e:
            clean_content = re.sub(
                r'("SequenceVariant"\s*:\s*").*?("(?=\s*[,}\n\r]))', 
                r'\1REMOVED_GARBAGE"', 
                clean_content,
                flags=re.DOTALL
            )
            json.loads(clean_content)
        
        if clean_content != raw_content:
            log_line(f"[FIX] Sanitized corrupted JSON: {json_path.name}")
            new_path = json_path.with_name(json_path.stem + "_cleaned.json")
            with open(new_path, "w", encoding="utf-8") as f:
                f.write(clean_content)
            
    except Exception as e:
        log_line(f"[WARN] Failed to process JSON {json_path}: {e}")


def log_line(msg: str):
    line = f"[{_now()}] {msg}\n"
    try:
        pathlib.Path(log_txt).parent.mkdir(parents=True, exist_ok=True)
        with open(log_txt, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        sys.stderr.write(line)
        
        
def read_config_json(config_path: pathlib.Path) -> dict:
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        log_line(f"[WARN] step=read_config_json path={config_path} err={type(e).__name__}: {e}")
        return {}


def run_shell(cmd: str, step: str, cwd: pathlib.Path | None = None):
    log_line(f"[RUN] step={step} cmd={cmd}")
    try:
        p = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd) if cwd else None,
            check=True,
            text=True,
            capture_output=True,
        )
        return p
    except subprocess.CalledProcessError as e:
        log_line(f"[ERROR] step={step} returncode={e.returncode}")
        if e.stdout:
            log_line(f"[STDOUT] step={step}\n{e.stdout.strip()}")
        if e.stderr:
            log_line(f"[STDERR] step={step}\n{e.stderr.strip()}")
        raise


def safe_rmtree(p: pathlib.Path):
    """Best-effort rmtree.

    Returns a small stats dict; does NOT log per-path (cleanup caller logs once).
    """
    stats = {"removed": 0, "skipped": 0, "error": None}
    try:
        if not p.exists():
            stats["skipped"] = 1
            return stats
        shutil.rmtree(p)
        stats["removed"] = 1
        return stats
    except Exception as e:
        stats["error"] = f"{type(e).__name__}: {e}"
        return stats


def safe_unlink(p: pathlib.Path):
    """Best-effort unlink.

    Returns a small stats dict; does NOT log per-path (cleanup caller logs once).
    """
    stats = {"removed": 0, "skipped": 0, "error": None}
    try:
        # Note: Path.exists() is False for broken symlinks, so check is_symlink() first.
        if p.is_symlink() or p.is_file():
            p.unlink()
            stats["removed"] = 1
            return stats
        if not p.exists():
            stats["skipped"] = 1
            return stats
        # Exists but not a file/symlink
        stats["skipped"] = 1
        return stats
    except FileNotFoundError:
        stats["skipped"] = 1
        return stats
    except Exception as e:
        stats["error"] = f"{type(e).__name__}: {e}"
        return stats


def cleanup_on_failure(dwi_dir: pathlib.Path):
    removed = 0
    skipped = 0
    errors: list[str] = []
    for name in ["mrtrix_tmp", "gradcheck_tmp", "processed", "transforms", "gqi"]:
        st = safe_rmtree(dwi_dir / name)
        removed += int(st["removed"])
        skipped += int(st["skipped"])
        if st["error"]:
            errors.append(f"{dwi_dir / name} => {st['error']}")

    if errors:
        log_line(
            f"[CLEAN-ERROR] cleanup_on_failure dwi_dir={dwi_dir} removed={removed} skipped={skipped} errors={len(errors)} first={errors[0]}"
        )
    else:
        log_line(f"[CLEAN] cleanup_on_failure dwi_dir={dwi_dir} removed={removed} skipped={skipped}")
        

def b0_register_and_concat(cat_mif: pathlib.Path, out_mif: pathlib.Path):
    """
    Fallback when dwifslpreproc fails:
    - pick the first denoised as reference
    - compute mean b0 for each file
    - rigid-register each mean b0 to ref mean b0
    - apply transform to the whole 4D DWI
    - concatenate (mrcat) into out_mif
    """
    work_dir = cat_mif.parent / "b0reg_tmp"
    work_dir.mkdir(exist_ok=True, parents=True)

    ref_b0s = work_dir / "ref_b0s.mif"
    ref_b0 = work_dir / "ref_firstb0.mif"
    if not ref_b0.exists():
        if not ref_b0s.exists():
            cmd = f"dwiextract {cat_mif} -bzero {ref_b0s} -quiet"
            subprocess.run(
                cmd,
                shell=True,
                check=True,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        
        cmd = f"mrconvert {ref_b0s} -coord 3 0 {ref_b0} -quiet"
        subprocess.run(
            cmd,
            shell=True,
            check=True,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        
    def _mrinfo_nvols(mif: pathlib.Path) -> int:
        # mrinfo -size 输出类似: "128 128 70 257"
        out = subprocess.check_output(f"mrinfo {mif} -size", shell=True, text=True).strip()
        parts = [int(x) for x in out.split()]
        if len(parts) < 4:
            raise RuntimeError(f"mrinfo -size returned unexpected: {out}")
        return parts[3]
    
    nvols = _mrinfo_nvols(cat_mif)
    args = [(i, str(cat_mif), str(ref_b0), str(work_dir)) for i in range(nvols)]
    
    def _process_one_vol(args):
        idx, cat_mif, ref_b0, work_dir = args
        cat_mif = pathlib.Path(cat_mif)
        ref_b0 = pathlib.Path(ref_b0)
        work_dir = pathlib.Path(work_dir)

        vol = work_dir / "vols" / f"vol_{idx:04d}.mif"
        mat = work_dir / "mats" / f"vol_{idx:04d}_to_ref.txt"
        vol_reg = work_dir / "vols_reg" / f"vol_{idx:04d}_reg.mif"

        vol.parent.mkdir(exist_ok=True, parents=True)
        mat.parent.mkdir(exist_ok=True, parents=True)
        vol_reg.parent.mkdir(exist_ok=True, parents=True)

        if not vol.exists():
            cmd = f"mrconvert {cat_mif} -coord 3 {idx} {vol}"
            subprocess.run(
                cmd,
                shell=True,
                check=True,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        if not mat.exists():
            cmd = (
                f"mrregister {vol} {ref_b0} -type rigid "
                f"-rigid_init_translation none -rigid_init_rotation none "
                f"-rigid {mat}"
            )
            subprocess.run(
                cmd,
                shell=True,
                check=True,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        if not vol_reg.exists():
            cmd = (
                f"mrtransform {vol} -linear {mat} -template {ref_b0} "
                f"{vol_reg}"
            )
            subprocess.run(
                cmd,
                shell=True,
                check=True,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        return str(vol_reg)
    
    # with Pool(processes=20) as pool:
    #     reg_vols = pool.map(_process_one_vol, args)
    reg_vols = []
    for arg in args:
        reg_vol = _process_one_vol(arg)
        reg_vols.append(reg_vol)
        
    if not out_mif.exists():
        cmd = f"mrcat {' '.join(reg_vols)} {out_mif} -quiet"
        subprocess.run(
            cmd,
            shell=True,
            check=True,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        
    # Cleanup temp dir
    safe_rmtree(work_dir)

    return out_mif


def cleanup_on_success(gradcheck_dir: pathlib.Path, mrtrix_dir: pathlib.Path, transform_dir: pathlib.Path, prefix: str):
    removed_dirs = 0
    removed_files = 0
    skipped = 0
    errors: list[str] = []

    st = safe_rmtree(mrtrix_dir)
    removed_dirs += int(st["removed"])
    skipped += int(st["skipped"])
    if st["error"]:
        errors.append(f"{mrtrix_dir} => {st['error']}")
        
    st = safe_rmtree(gradcheck_dir)
    removed_dirs += int(st["removed"])
    skipped += int(st["skipped"])
    if st["error"]:
        errors.append(f"{gradcheck_dir} => {st['error']}")

    keep = {
        "FA_2_MNI0GenericAffine.mat",
        "FA_2_MNI.mat",
    }
    if transform_dir.exists():
        for p in transform_dir.iterdir():
            if p.name in keep:
                continue
            if p.is_dir():
                st = safe_rmtree(p)
                removed_dirs += int(st["removed"])
                skipped += int(st["skipped"])
                if st["error"]:
                    errors.append(f"{p} => {st['error']}")
            else:
                st = safe_unlink(p)
                removed_files += int(st["removed"])
                skipped += int(st["skipped"])
                if st["error"]:
                    errors.append(f"{p} => {st['error']}")

    if errors:
        log_line(
            f"[CLEAN-ERROR] cleanup_on_success gradcheck_dir={gradcheck_dir} mrtrix_dir={mrtrix_dir} transform_dir={transform_dir} removed_dirs={removed_dirs} removed_files={removed_files} skipped={skipped} errors={len(errors)} first={errors[0]}"
        )
    else:
        log_line(
            f"[CLEAN] cleanup_on_success gradcheck_dir={gradcheck_dir} mrtrix_dir={mrtrix_dir} transform_dir={transform_dir} removed_dirs={removed_dirs} removed_files={removed_files} skipped={skipped}"
        )


def parse_fsl_affine(file):
    with open(file) as f:
        lines = f.readlines()
    entries = [l.split() for l in lines]
    entries = [row for row in entries if len(row) > 0]  # remove empty rows
    return np.array(entries).astype(np.float32)


def rotate_bvecs(bvecs_in, affine_in, bvecs_out):
    bvecs = read_bvecs(bvecs_in)

    affine = parse_fsl_affine(affine_in)

    affine = affine[:3, :3]

    # Get rotation component of affine transformation
    col_norm = np.linalg.norm(affine, axis=0)
    safe = col_norm.copy()
    safe[safe == 0] = 1.0
    rotation = np.zeros((3, 3))
    rotation[:, 0] = affine[:, 0] / safe[0]
    rotation[:, 1] = affine[:, 1] / safe[1]
    rotation[:, 2] = affine[:, 2] / safe[2]

    # Apply rotation to bvecs
    if bvecs.shape[0] == 3:
        bvecs = np.array(bvecs)
    else:
        bvecs = np.array(bvecs).T  # [nr_vecs, 3] -> [3, nr_vecs]
    rotated_bvecs = np.matmul(rotation, bvecs)  # [3, nr_vecs]

    # Normalize bvecs
    rotated_bvecs = rotated_bvecs.copy()
    bvecs_norm = np.linalg.norm(rotated_bvecs, axis=0)
    idx = bvecs_norm != 0
    rotated_bvecs[:, idx] /= bvecs_norm[idx]

    np.savetxt(bvecs_out, rotated_bvecs, fmt="%1.6f")


def read_bvecs(this_fname):
    """
    Adapted from dipy.io.read_bvals_bvecs
    """
    with open(this_fname, "r") as f:
        content = f.read()
    # We replace coma and tab delimiter by space
    with InTemporaryDirectory():
        tmp_fname = "tmp_bvals_bvecs.txt"
        with open(tmp_fname, "w") as f:
            f.write(re.sub(r"(\t|,)", " ", content))
        bvecs = np.squeeze(np.loadtxt(tmp_fname)).T

    if bvecs.shape[0] == 3:
        bvecs = np.array(bvecs)
    else:
        bvecs = np.array(bvecs).T  # [nr_vecs, 3] -> [3, nr_vecs]

    return bvecs


def load_bvals(bval_path):
    with open(bval_path, "r") as f:
        return [float(num) for num in f.read().split()]


def run_command(subject_dir):
    subject_dir = pathlib.Path(subject_dir)
    dwi_dirs = list(subject_dir.rglob("dwi"))

    if not dwi_dirs:
        log_line(f"No dwi directory found in {subject_dir}")
        return

    for dwi_dir in dwi_dirs:
        prefix = subject_dir.name + "_" + dwi_dir.parent.name + "_"

        mrtrix_dir = dwi_dir / "mrtrix_tmp"
        gradcheck_dir = dwi_dir / "gradcheck_tmp"
        processed_dir = dwi_dir / "processed"
        transform_dir = dwi_dir / "transforms"
        gqi_dir = dwi_dir / "gqi"
        
        if gqi_dir.exists() and (gqi_dir / (prefix + "dwi.gqi.fz")).exists():
            log_line(f"[SKIP] gqi already exists for dwi_dir={dwi_dir}")
            continue

        try:
            for p in [mrtrix_dir, gradcheck_dir, processed_dir, transform_dir, gqi_dir]:
                p.mkdir(exist_ok=True)

            dwi_files = list(dwi_dir.rglob("*dwi.nii.gz"))

            if not dwi_files:
                raise FileNotFoundError(f"No DWI files found in {dwi_dir}")

            for dwi_file in dwi_files:
                bval_file = dwi_file.with_suffix('').with_suffix(".bval")
                bvec_file = dwi_file.with_suffix('').with_suffix(".bvec")
                
                config_file = dwi_file.with_suffix('').with_suffix(".json")
                clean_json_control_chars(config_file)
                config_file = config_file.parent / config_file.name.replace(".json", "_cleaned.json") if (config_file.parent / config_file.name.replace(".json", "_cleaned.json")).exists() else config_file

                if not bval_file.exists() or not bvec_file.exists() or not config_file.exists():
                    log_line(f"Missing bval, bvec, or json for {dwi_file}, skipping this file.")
                    continue

                dwi_img = nib.load(str(dwi_file))
                bval_data = load_bvals(str(bval_file))
                bvec_data = read_bvecs(str(bvec_file))

                if dwi_img.shape[-1] != len(bval_data) or dwi_img.shape[-1] != bvec_data.shape[1]:
                    log_line(f"Mismatch in number of volumes for {dwi_file}, skipping this file.")
                    continue

                checked_bvec = gradcheck_dir / bvec_file.name.replace(".bvec", "_grad_checked.bvec")
                checked_bval = gradcheck_dir / bval_file.name.replace(".bval", "_grad_checked.bval")

                if not (checked_bvec.exists() and checked_bval.exists()):
                    cmd = (
                        f"dwigradcheck {dwi_file} -fslgrad {bvec_file} {bval_file} "
                        f"-export_grad_fsl {checked_bvec} {checked_bval} -nthreads 20"
                    )
                    try:
                        run_shell(cmd, step="dwigradcheck")
                    except subprocess.CalledProcessError:
                        log_line(
                            f"[WARN] step=dwigradcheck failed, fallback to copy original grads "
                            f"bvec={bvec_file} bval={bval_file}"
                        )
                        shutil.copyfile(bvec_file, checked_bvec)
                        shutil.copyfile(bval_file, checked_bval)

                dwi_mif = mrtrix_dir / dwi_file.name.replace(".nii.gz", ".mif")
                if not dwi_mif.exists():
                    cmd = f"mrconvert {dwi_file} -json_import {config_file} -fslgrad {checked_bvec} {checked_bval} {dwi_mif}"
                    run_shell(cmd, step="mrconvert")

                dwi_denoised = mrtrix_dir / dwi_mif.name.replace(".mif", "_den.mif")
                if not dwi_denoised.exists():
                    cmd = f"dwidenoise {dwi_mif} {dwi_denoised}"
                    run_shell(cmd, step="dwidenoise")

            denoised_files = list(mrtrix_dir.rglob("*_den.mif"))
            if not denoised_files:
                raise FileNotFoundError(f"No denoised DWI files found in {mrtrix_dir}")
            
            cat_mif = mrtrix_dir / "dwi_cat.mif"
            if not cat_mif.exists():
                if len(denoised_files) == 1:
                    # soft link if only one file
                    os.symlink(denoised_files[0], cat_mif)
                    log_line(f"[LINK] step=mrcat single file linked to {cat_mif}")
                else:
                    cmd = f"mrcat {' '.join(map(str, denoised_files))} {cat_mif}"
                    run_shell(cmd, step="mrcat")
                
            preproc_mif = mrtrix_dir / "dwi_preproc.mif"
            if not preproc_mif.exists():
                cmd = (
                    f"dwifslpreproc {cat_mif} {preproc_mif} -rpe_header"
                    f" -eddy_options ' --slm=linear ' -nthreads 20"
                )
                try:
                    log_line(f"[RUN] step=dwifslpreproc cmd={cmd}")
                    subprocess.run(
                        cmd,
                        shell=True,
                        check=True,
                        text=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except subprocess.CalledProcessError:
                    log_line("[WARN] step=dwifslpreproc failed, fallback=affine_to_firstb0_of_firstfile")
                    b0_register_and_concat(cat_mif, preproc_mif)
                    
            bias_corrected = mrtrix_dir / "dwi_preproc_biascorr.mif"
            if not bias_corrected.exists():
                cmd = f"dwibiascorrect ants {preproc_mif} {bias_corrected} -nthreads 20"
                run_shell(cmd, step="dwibiascorrect_ants")

            preproc_dwi_nifti = processed_dir / (prefix + "dwi.nii.gz")
            preproc_dwi_bval = processed_dir / (prefix + "dwi.bval")
            preproc_dwi_bvec = processed_dir / (prefix + "dwi.bvec")
            preproc_dwi_config = processed_dir / (prefix + "dwi.json")
            if not preproc_dwi_nifti.exists():
                cmd = (
                    f"mrconvert {bias_corrected} {preproc_dwi_nifti} "
                    f"-export_grad_fsl {preproc_dwi_bvec} {preproc_dwi_bval} -json_export {preproc_dwi_config}"
                )
                run_shell(cmd, step="mrconvert_final_export_grad")

            brain_mask_mif = mrtrix_dir / "brain_mask.mif"
            if not brain_mask_mif.exists():
                cmd = f"dwi2mask {preproc_dwi_nifti} -fslgrad {preproc_dwi_bvec} {preproc_dwi_bval} {brain_mask_mif} -nthreads 20"
                run_shell(cmd, step="dwi2mask")
                
            brain_mask = processed_dir / (prefix + "brain_mask.nii.gz")
            if not brain_mask.exists():
                cmd = f"mrconvert {brain_mask_mif} {brain_mask}"
                run_shell(cmd, step="mrconvert_brain_mask")

            dti_dir = mrtrix_dir / "dti"
            dti_dir.mkdir(exist_ok=True)

            fa_file = dti_dir / "dti_FA.nii.gz"
            if not fa_file.exists():
                cmd = f"dtifit -k {preproc_dwi_nifti} -o {dti_dir / 'dti'} -m {brain_mask} -r {preproc_dwi_bvec} -b {preproc_dwi_bval}"
                run_shell(cmd, step="dtifit")

            affine_file = transform_dir / "FA_2_MNI0GenericAffine.mat"
            if not affine_file.exists():
                cmd = f"antsRegistrationSyNQuick.sh -d 3 -f {MNI_TEMPLATE} -m {fa_file} -o {transform_dir / 'FA_2_MNI'} -t r"
                run_shell(cmd, step="antsRegistrationSyNQuick")

            affine_mat_file = transform_dir / "FA_2_MNI.mat"
            if not affine_mat_file.exists():
                cmd = f"ConvertTransformFile 3 {affine_file} {affine_mat_file} --hm"
                run_shell(cmd, step="ConvertTransformFile")

            dwi_nifti_in_mni = transform_dir / (prefix + "dwi_MNI.nii.gz")
            if not dwi_nifti_in_mni.exists():
                cmd = f"antsApplyTransforms -d 3 -e 3 -i {preproc_dwi_nifti} -r {MNI_TEMPLATE} -o {dwi_nifti_in_mni} -t {affine_file} -n BSpline"
                run_shell(cmd, step="antsApplyTransforms_dwi")

            dwi_bval_in_mni = transform_dir / (prefix + "dwi_MNI.bval")
            if not dwi_bval_in_mni.exists():
                cmd = f"cp {preproc_dwi_bval} {dwi_bval_in_mni}"
                run_shell(cmd, step="copy_bval")

            dwi_bvec_in_mni = transform_dir / (prefix + "dwi_MNI.bvec")
            if not dwi_bvec_in_mni.exists():
                try:
                    rotate_bvecs(preproc_dwi_bvec, affine_mat_file, dwi_bvec_in_mni)
                    log_line(f"[OK] step=rotate_bvecs out={dwi_bvec_in_mni}")
                except Exception:
                    log_line(f"[ERROR] step=rotate_bvecs err={traceback.format_exc()}")
                    raise

            mask_in_mni = transform_dir / (prefix + "brain_mask_MNI.nii.gz")
            if not mask_in_mni.exists():
                cmd = f"antsApplyTransforms -d 3 -i {brain_mask} -r {MNI_TEMPLATE} -o {mask_in_mni} -t {affine_file} -n NearestNeighbor"
                run_shell(cmd, step="antsApplyTransforms_mask")

            gqi_file = gqi_dir / (prefix + "dwi.gqi.fz")
            if not gqi_file.exists():
                cmd = (
                    f"/data/yijie/software/dsi-studio/dsi_studio --action=rec "
                    f"--source={dwi_nifti_in_mni} --method=4 --mask={mask_in_mni} --apply_mask "
                    f"--output={gqi_dir / (prefix + 'dwi')}"
                )
                run_shell(cmd, step="dsi_studio_gqi")

            cleanup_on_success(gradcheck_dir=gradcheck_dir, mrtrix_dir=mrtrix_dir, transform_dir=transform_dir, prefix=prefix)
            log_line(f"[DONE] success for dwi_dir={dwi_dir}")

        except Exception:
            log_line(f"[FAIL] dwi_dir={dwi_dir} err={traceback.format_exc()}")
            cleanup_on_failure(dwi_dir)
            continue


if __name__ == "__main__":
    input_dir = pathlib.Path("/data/dataset/HABS_HD_bak/")
    
    subject_dirs = []
    for s in input_dir.iterdir():
        if s.is_dir():
            subject_dirs.append(s)
                    
    subject_dirs = sorted(subject_dirs)
    
    log_line(f"Found {len(subject_dirs)} subject directories to process.")
    # print(f"Found {len(subject_dirs)} subject directories to process.")

    with Pool(processes=14) as pool:
        pool.map(run_command, subject_dirs)
