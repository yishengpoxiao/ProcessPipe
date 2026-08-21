"""Legacy MRtrix, UKF tractography, and White Matter Analysis workflow."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from processpipe.core.commands import run_command


DEFAULT_INPUT_DIR = Path("/data/private_data/ASD_Li_lab")
SLICER = Path("/data/software/Slicer-5.2.2-linux-amd64/Slicer")
SLICER_DWI_CONVERT = SLICER.parent / "lib/Slicer-5.2/cli-modules/DWIConvert"
UKF_TRACTOGRAPHY = SLICER.parent / "NA-MIC/Extensions-31382/UKFTractography/lib/Slicer-5.2/cli-modules/UKFTractography"
CNN_MODEL_DIR = Path("/data/software/CNN-Diffusion-MRIBrain-Segmentation-1.0/model_folder")
CNN_MASK_SCRIPT = Path("/data/software/CNN-Diffusion-MRIBrain-Segmentation-1.0/pipeline/dwi_masking.py")
ORG_ATLAS_DIR = Path("/data/software/ORG-Atlases")


def _run(command: list[str] | str, *, shell: bool = False) -> None:
    """Keep the original workflow's non-failing command behavior."""
    run_command(command, shell=shell, check=False)


def _replace_nifti_suffix(path: Path, suffix: str) -> Path:
    return path.with_suffix("").with_suffix(suffix)


def _run_if_missing(output: Path, command: list[str] | str, *, shell: bool = False) -> None:
    if not output.exists():
        _run(command, shell=shell)


def convert_to_nrrd(nifti_file: Path, bval_file: Path, bvec_file: Path, output_dir: Path) -> Path:
    output_volume = output_dir / f"{nifti_file.name.removesuffix('.nii.gz')}.nrrd"
    _run_if_missing(output_volume, [
        str(SLICER), "--launch", str(SLICER_DWI_CONVERT),
        "--conversionMode", "FSLToNrrd", "--transposeInputBVectors",
        "--outputVolume", str(output_volume), "--smallGradientThreshold", "0.2",
        "--inputBValues", str(bval_file), "--inputBVectors", str(bvec_file),
        "--fslNIFTIFile", str(nifti_file), "--allowLossyConversion",
        "--writeProtocolGradientsFile",
    ])
    return output_volume


def _gradient_check(dwi_file: Path) -> None:
    checked_bvec = _replace_nifti_suffix(dwi_file, "_gradcheck.bvec")
    checked_bval = _replace_nifti_suffix(dwi_file, "_gradcheck.bval")
    if checked_bvec.exists() and checked_bval.exists():
        return
    _run([
        "dwigradcheck", str(dwi_file), "-fslgrad",
        str(_replace_nifti_suffix(dwi_file, ".bvec")),
        str(_replace_nifti_suffix(dwi_file, ".bval")),
        "-export_grad_fsl", str(checked_bvec), str(checked_bval), "-nthreads", "80",
    ])


def _mif_from_dwi(dwi_file: Path, temp_dir: Path) -> Path:
    output = temp_dir / f"{dwi_file.name.removesuffix('.nii.gz')}.mif"
    _run_if_missing(output, [
        "mrconvert", str(dwi_file), str(output), "-fslgrad",
        str(_replace_nifti_suffix(dwi_file, "_gradcheck.bvec")),
        str(_replace_nifti_suffix(dwi_file, "_gradcheck.bval")),
        "-json_import", str(_replace_nifti_suffix(dwi_file, ".json")), "-nthreads", "80",
    ])
    return output


def _denoise(mif_file: Path, temp_dir: Path) -> Path:
    output = temp_dir / f"{mif_file.name.removesuffix('.mif')}_den.mif"
    _run_if_missing(output, ["dwidenoise", str(mif_file), str(output), "-nthreads", "80"])
    return output


def _preprocess_mrtrix(dwi_files: list[Path], subject: str, temp_dir: Path) -> Path | None:
    if len(dwi_files) == 1:
        denoised = _denoise(_mif_from_dwi(dwi_files[0], temp_dir), temp_dir)
        output = temp_dir / f"{subject}_dwi_preproc.mif"
        _run_if_missing(output, [
            "dwifslpreproc", str(denoised), str(output), "-rpe_none", "-pe_dir", "PA",
            "-eddy_options", " --slm=linear ", "-nthreads", "80",
        ])
        return output
    if len(dwi_files) != 2:
        return None
    try:
        pa_file = next(path for path in dwi_files if "PA_" in path.name)
        ap_file = next(path for path in dwi_files if "AP_" in path.name)
    except StopIteration:
        return None
    denoised_pa = _denoise(_mif_from_dwi(pa_file, temp_dir), temp_dir)
    denoised_ap = _denoise(_mif_from_dwi(ap_file, temp_dir), temp_dir)
    concatenated = temp_dir / f"{subject}_2pe_dwi.mif"
    _run_if_missing(concatenated, [
        "mrcat", str(denoised_pa), str(denoised_ap), str(concatenated),
        "-axis", "3", "-nthreads", "80",
    ])
    output = temp_dir / f"{subject}_dwi_preproc.mif"
    _run_if_missing(output, [
        "dwifslpreproc", str(concatenated), str(output), "-rpe_header",
        "-eddy_options", " --slm=linear ", "-nthreads", "80",
    ])
    return output


def process_subject(task: tuple[str, str, Path]) -> None:
    import nibabel as nib

    site, subject, input_dir = task
    subject_dir = input_dir / site / subject
    dwi_dir = subject_dir / "dwi"
    if not dwi_dir.is_dir():
        print(f"[WARN] No dwi dir for subject, skip: {subject_dir}")
        return
    dwi_files = sorted(dwi_dir.glob("*_dwi.nii.gz"))
    if not dwi_files:
        print(f"[WARN] No dwi files for subject, skip: {subject_dir}")
        return
    print(f"[INFO] Start processing: site={site}, subject={subject}")
    for dwi_file in dwi_files:
        _gradient_check(dwi_file)
    if len(dwi_files) >= 2 and nib.load(dwi_files[0]).shape[:3] != nib.load(dwi_files[1]).shape[:3]:
        dwi_files = sorted(dwi_dir.glob("*PA*_dwi.nii.gz"))

    temp_dir = dwi_dir / "mrtrix_temp"
    temp_dir.mkdir(exist_ok=True)
    preprocessed_mif = _preprocess_mrtrix(dwi_files, subject, temp_dir)
    if preprocessed_mif is None:
        print(f"[WARN] dwi_files must contain one DWI or an AP/PA pair, skip: {subject_dir}")
        return

    biascorrected = temp_dir / f"{subject}_dwi_preproc_biascorr.mif"
    _run_if_missing(biascorrected, [
        "dwibiascorrect", "ants", str(preprocessed_mif), str(biascorrected), "-nthreads", "80",
    ])
    processed_dir = dwi_dir / "processed"
    processed_dir.mkdir(exist_ok=True)
    processed_nifti = processed_dir / f"{subject}_dwi_processed.nii.gz"
    processed_bvec = processed_dir / f"{subject}_dwi_processed.bvec"
    processed_bval = processed_dir / f"{subject}_dwi_processed.bval"
    _run_if_missing(processed_nifti, [
        "mrconvert", str(biascorrected), str(processed_nifti), "-export_grad_fsl",
        str(processed_bvec), str(processed_bval), "-nthreads", "80",
    ])
    dwi_nrrd = convert_to_nrrd(processed_nifti, processed_bval, processed_bvec, processed_dir)

    input_list = processed_dir / f"{subject}.txt"
    input_list.write_text(f"{dwi_nrrd}\n")
    brain_mask = processed_dir / f"{subject}_dwi_processed_bse-multi_BrainMask.nii.gz"
    _run_if_missing(brain_mask, "\n".join([
        "export ANTSPATH=/data/software/ANTs/bin",
        "export PATH=${ANTSPATH}:$PATH",
        "/data/software/miniconda3/envs/dmri_seg/bin/python "
        f"{CNN_MASK_SCRIPT} -i {input_list} -f {CNN_MODEL_DIR}",
    ]), shell=True)
    brain_mask_nhdr = brain_mask.with_suffix("").with_suffix(".nhdr")
    _run_if_missing(brain_mask_nhdr, [
        "/data/software/miniconda3/envs/wma/bin/python",
        "/data/software/conversion/conversion/nhdr_write.py",
        "--nifti", str(brain_mask), "--nhdr", str(brain_mask_nhdr),
    ])

    tractography_dir = dwi_dir / "tractography"
    tractography_dir.mkdir(exist_ok=True)
    tractography_path = tractography_dir / f"{subject}.vtk"
    _run_if_missing(tractography_path, [
        str(SLICER), "--launch", str(UKF_TRACTOGRAPHY), "--numThreads", "80", "--numTensor", "2",
        "--dwiFile", str(dwi_nrrd), "--maskFile", str(brain_mask_nhdr), "--tracts", str(tractography_path),
        "--seedingThreshold", "0.1", "--stoppingFA", "0.08", "--stoppingThreshold", "0.06",
        "--seedsPerVoxel", "3", "--recordFA", "--freeWater", "--recordTrace", "--recordTensors",
        "--recordFreeWater",
    ])

    wma_dir = dwi_dir / "WMA"
    wma_dir.mkdir(exist_ok=True)
    completed_measurements = wma_dir / subject / "AnatomicalTracts/diffusion_measurements_anatomical_tracts.csv"
    _run_if_missing(completed_measurements, "\n".join([
        ". /data/software/miniconda3/etc/profile.d/conda.sh",
        "conda activate wma",
        "/data/software/whitematteranalysis/bin/wm_apply_ORG_atlas_to_subject.sh "
        f"-i {tractography_path} -o {wma_dir} -a {ORG_ATLAS_DIR} -s {SLICER} "
        f"-n 8 -c 2 -x 1 -d 1 -m '{SLICER} --launch "
        "/data/software/Slicer-5.2.2-linux-amd64/NA-MIC/Extensions-31382/SlicerDMRI/lib/Slicer-5.2/cli-modules/FiberTractMeasurements'",
    ]), shell=True)
    print(f"[INFO] Finished processing: site={site}, subject={subject}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    tasks = [
        (site_dir.name, subject_dir.name, args.input_dir)
        for site_dir in args.input_dir.iterdir() if site_dir.is_dir()
        for subject_dir in site_dir.iterdir()
        if subject_dir.is_dir() and any((subject_dir / "dwi").glob("*_dwi.nii.gz"))
    ]
    print(f"[INFO] Total subjects to process: {len(tasks)}")
    if args.dry_run:
        for site, subject, _ in tasks:
            print(f"site={site}, subject={subject}")
        return
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        list(executor.map(process_subject, tasks))


if __name__ == "__main__":
    main()
