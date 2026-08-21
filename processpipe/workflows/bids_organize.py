"""DICOM conversion and BIDS-style data organization workflows."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from processpipe.core.bids import (
    bids_guess_stem,
    move_nifti_bundle,
    nifti_stem,
    phase_direction,
    read_bids_json,
    sidecar_paths,
)
from processpipe.core.commands import run_command


ASD_INPUT_DIR = Path("/data/private_data/ASD_Li_lab")
ABVIB_DICOM_ROOT = Path("/data/dataset/ABVIB/ABVIB")
ABVIB_NIFTI_ROOT = Path("/data/dataset/ABVIB/nifti")
PPMI_NIFTI_ROOT = Path("/data/dataset/PPMI/nifti")
FIBER_DATA_HUB = Path("/data/dataset/FiberDataHub")


def _process_asd_subject(task: tuple[Path, str, str]) -> None:
    input_dir, site, subject = task
    subject_path = input_dir / site / subject
    if not subject_path.is_dir():
        print(f"[WARN] Not a dir, skip: {subject_path}")
        return
    zip_files = sorted(subject_path.glob("*.zip"))
    if not zip_files:
        print(f"[WARN] No zip file for subject, skip: {subject_path}")
        return

    print(f"[INFO] Start subject: site={site}, subject={subject}")
    run_command(["unzip", str(zip_files[0]), "-d", str(subject_path.parent)])
    converted_dir = subject_path / "nifti_convert"
    converted_dir.mkdir(exist_ok=True)
    for session_path in subject_path.iterdir():
        if session_path.is_dir():
            run_command([
                "/data/software/dcm2niix", "-f", "%i_%s_%d", "-b", "y", "-z", "y",
                "-o", str(converted_dir), str(session_path),
            ])

    for json_path in converted_dir.glob("*.json"):
        modality_dir, new_stem = bids_guess_stem(
            read_bids_json(json_path).get("BidsGuess"), subject,
        )
        source_nifti = json_path.with_suffix(".nii.gz")
        if source_nifti.exists():
            move_nifti_bundle(source_nifti, subject_path / modality_dir / f"{new_stem}.nii.gz")
    print(f"[INFO] Finished subject: site={site}, subject={subject}")


def main_convert_asd(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Convert ASD DICOM archives to NIfTI and organize by BidsGuess.")
    parser.add_argument("--input-dir", type=Path, default=ASD_INPUT_DIR)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    tasks = [
        (args.input_dir, site_path.name, subject_path.name)
        for site_path in args.input_dir.iterdir() if site_path.is_dir()
        for subject_path in site_path.iterdir()
        if subject_path.is_dir() and any(subject_path.glob("*.zip"))
    ]
    print(f"[INFO] Total subjects to process: {len(tasks)}")
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        list(executor.map(_process_asd_subject, tasks))


def _convert_abvib_subject(dicom_dir: Path, nifti_dir: Path) -> None:
    if not dicom_dir.is_dir():
        return
    nifti_dir.mkdir(parents=True, exist_ok=True)
    scans = [
        year_path
        for modality_path in dicom_dir.iterdir() if modality_path.is_dir()
        for year_path in modality_path.iterdir() if year_path.is_dir()
    ]
    year_list = sorted({scan.name[:7] for scan in scans})
    for scan in scans:
        dcm_files = list(scan.rglob("*.dcm"))
        if not dcm_files:
            continue
        session_index = year_list.index(scan.name[:7]) + 1
        session_dir = nifti_dir / f"ses-{session_index:02d}"
        session_dir.mkdir(exist_ok=True)
        run_command([
            "/data/yijie/software/dcm2niix", "-f", "%i_%s_%d", "-b", "y", "-z", "y",
            "-o", str(session_dir), str(dcm_files[0].parent),
        ])


def main_convert_abvib(argv: list[str] | None = None) -> None:
    from joblib import Parallel, delayed

    parser = argparse.ArgumentParser(description="Convert ABVIB DICOM directories to session-level NIfTI.")
    parser.add_argument("--input-dir", type=Path, default=ABVIB_DICOM_ROOT)
    parser.add_argument("--output-dir", type=Path, default=ABVIB_NIFTI_ROOT)
    parser.add_argument("--workers", type=int, default=30)
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    subject_dirs = [path for path in args.input_dir.iterdir() if path.is_dir()]
    Parallel(n_jobs=args.workers, backend="loky")(
        delayed(_convert_abvib_subject)(subject, args.output_dir / subject.name)
        for subject in subject_dirs
    )


def _rename_using_bids_guess(root_dir: Path) -> None:
    for subject_dir in root_dir.iterdir():
        if not subject_dir.is_dir():
            continue
        for session_dir in subject_dir.iterdir():
            dwi_dir = session_dir / "dwi"
            if not session_dir.is_dir() or not dwi_dir.is_dir():
                continue
            for nifti_path in sorted(dwi_dir.glob("*.nii.gz")):
                json_path = sidecar_paths(nifti_path)[".json"]
                if not json_path.exists():
                    print(f"[WARNING] Missing JSON sidecar: {nifti_path}")
                    continue
                _, new_stem = bids_guess_stem(
                    read_bids_json(json_path).get("BidsGuess"), subject_dir.name, session_dir.name,
                )
                destination = dwi_dir / f"{new_stem}.nii.gz"
                if nifti_path == destination:
                    continue
                move_nifti_bundle(nifti_path, destination)


def main_rename_ppmi(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Rename PPMI DWI files using BidsGuess metadata.")
    parser.add_argument("--input-dir", type=Path, default=PPMI_NIFTI_ROOT)
    args = parser.parse_args(argv)
    _rename_using_bids_guess(args.input_dir)


def _has_sidecars(nifti_path: Path) -> bool:
    return all(path.exists() for path in sidecar_paths(nifti_path).values())


def _has_multiple_volumes(nifti_path: Path) -> bool:
    try:
        return len(sidecar_paths(nifti_path)[".bval"].read_text().split()) > 1
    except OSError:
        return False


def _keep_dwi(nifti_path: Path) -> bool:
    return phase_direction(nifti_path) is not None or (
        _has_sidecars(nifti_path) and _has_multiple_volumes(nifti_path)
    )


def _delete_nifti_bundle(nifti_path: Path) -> None:
    for path in (nifti_path, *sidecar_paths(nifti_path).values()):
        path.unlink(missing_ok=True)


def reorganize_dwi(root_dir: Path) -> None:
    """Filter a flat session directory and move retained files into `dwi/`."""
    for subject_dir in root_dir.iterdir():
        if not subject_dir.is_dir():
            continue
        for session_dir in subject_dir.iterdir():
            if not session_dir.is_dir():
                continue
            nifti_files = sorted(session_dir.glob("*.nii.gz"))
            retained = [path for path in nifti_files if _keep_dwi(path)]
            for path in nifti_files:
                if path not in retained:
                    _delete_nifti_bundle(path)
            if not retained:
                if not any(session_dir.iterdir()):
                    session_dir.rmdir()
                continue

            dwi_dir = session_dir / "dwi"
            for nifti_path in retained:
                json_path = sidecar_paths(nifti_path)[".json"]
                if not json_path.exists():
                    print(f"[WARNING] Missing JSON sidecar: {nifti_path}")
                    continue
                _, new_stem = bids_guess_stem(
                    read_bids_json(json_path).get("BidsGuess"), subject_dir.name, session_dir.name,
                )
                move_nifti_bundle(nifti_path, dwi_dir / f"{new_stem}.nii.gz")


def main_reorganize_abvib(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Filter and BIDS-organize ABVIB DWI acquisitions.")
    parser.add_argument("--input-dir", type=Path, default=ABVIB_NIFTI_ROOT)
    args = parser.parse_args(argv)
    reorganize_dwi(args.input_dir)


def organize_dsi_studio(root_dir: Path) -> None:
    for owner_dir in root_dir.iterdir():
        if not owner_dir.is_dir():
            continue
        for repo_dir in owner_dir.iterdir():
            if not repo_dir.is_dir():
                continue
            for data_dir in repo_dir.iterdir():
                if not data_dir.is_dir():
                    continue
                for source_file in list(data_dir.iterdir()):
                    if source_file.is_dir():
                        continue
                    parts = source_file.name.split(".")[0].split("_")
                    if len(parts) == 1 or (len(parts) == 2 and parts[1] == "dwi"):
                        subject_id, session_id = parts[0], "ses-01"
                    elif len(parts) >= 2:
                        subject_id, session_id = parts[0], parts[1]
                    else:
                        print(f"[WARNING] Unrecognized file format: {source_file}")
                        continue
                    destination = data_dir / subject_id / session_id / "dwi" / "gqi" / source_file.name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    source_file.rename(destination)
                if data_dir.exists() and not any(data_dir.iterdir()):
                    data_dir.rmdir()
            if repo_dir.exists() and not any(repo_dir.iterdir()):
                repo_dir.rmdir()
        if owner_dir.exists() and not any(owner_dir.iterdir()):
            owner_dir.rmdir()


def main_organize_dsi(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Organize DSI Studio outputs into subject/session folders.")
    parser.add_argument("--input-dir", type=Path, default=FIBER_DATA_HUB)
    args = parser.parse_args(argv)
    organize_dsi_studio(args.input_dir)
