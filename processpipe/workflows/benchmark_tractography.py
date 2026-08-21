"""Shared MRtrix and DSI Studio benchmark tractography workflow.

The four original dataset scripts differed chiefly in how subjects were found.
This module keeps those layouts as profiles while running one implementation.
"""

from __future__ import annotations

import argparse
import subprocess
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from processpipe.core.commands import run_command


DSI_STUDIO_BIN = Path("/data/yijie/software/dsi-studio/dsi_studio")
TRACK_CONVERTER = Path("/data/yijie/Tractography/utilize/track_convert.py")
TRACK_CONVERTER_PYTHON = Path("/data/yijie/miniconda3/envs/tractography/bin/python")
OUTPUT_ROOT = Path("/data/yijie/dataset_check")
TEMP_ROOT = Path("/data/yijie/process_tmp_check")


@dataclass(frozen=True)
class BenchmarkTask:
    """All dataset-specific information needed to process one DWI acquisition."""

    label: str
    subject_id: str
    output_stem: str
    dwi_file: Path
    bval_file: Path
    bvec_file: Path
    temp_dir: Path
    ifod_output_dirs: tuple[Path, Path, Path]
    dsi_output_dirs: tuple[Path, Path, Path]
    mask_file: Path | None = None


VARIANTS: tuple[tuple[str, str | None], ...] = (
    ("", None),
    ("_2", "12345"),
    ("_3", "54321"),
)


def _missing_inputs(task: BenchmarkTask) -> list[Path]:
    paths = [task.dwi_file, task.bval_file, task.bvec_file]
    if task.mask_file is not None:
        paths.append(task.mask_file)
    return [path for path in paths if not path.exists()]


def _run_quiet(command: list[str]) -> None:
    run_command(command, quiet=True)


def _convert_track(source: Path, destination: Path) -> None:
    if destination.exists():
        return
    _run_quiet([
        str(TRACK_CONVERTER_PYTHON),
        str(TRACK_CONVERTER),
        str(source),
        str(destination),
    ])


def process_task(task: BenchmarkTask) -> str:
    """Run all six repeated tractography outputs for a single acquisition."""
    missing = _missing_inputs(task)
    if missing:
        return f"[SKIP] {task.label}: missing {', '.join(str(path) for path in missing)}"

    try:
        print(f"[START] {task.label}", flush=True)
        task.temp_dir.mkdir(parents=True, exist_ok=True)
        for output_dir in (*task.ifod_output_dirs, *task.dsi_output_dirs):
            output_dir.mkdir(parents=True, exist_ok=True)

        dwi_mif = task.temp_dir / f"{task.output_stem}_dwi.mif"
        if not dwi_mif.exists():
            _run_quiet([
                "mrconvert", str(task.dwi_file), str(dwi_mif),
                "-fslgrad", str(task.bvec_file), str(task.bval_file), "-quiet",
            ])

        checked_bval = task.temp_dir / f"{task.output_stem}_checked.bval"
        checked_bvec = task.temp_dir / f"{task.output_stem}_checked.bvec"
        if not checked_bval.exists() or not checked_bvec.exists():
            _run_quiet([
                "dwigradcheck", str(dwi_mif),
                "-export_grad_fsl", str(checked_bvec), str(checked_bval), "-quiet",
            ])

        mask_file = task.mask_file or task.temp_dir / f"{task.output_stem}_mask.nii.gz"
        if not mask_file.exists():
            _run_quiet([
                "dwi2mask", str(task.dwi_file), str(mask_file),
                "-fslgrad", str(checked_bvec), str(checked_bval), "-quiet",
            ])

        response_file = task.temp_dir / f"{task.output_stem}_response.txt"
        if not response_file.exists():
            _run_quiet([
                "dwi2response", "tournier", str(task.dwi_file), str(response_file),
                "-fslgrad", str(checked_bvec), str(checked_bval),
                "-mask", str(mask_file), "-quiet",
            ])

        fod_file = task.temp_dir / f"{task.output_stem}_fod.mif"
        if not fod_file.exists():
            _run_quiet([
                "dwi2fod", "csd", str(task.dwi_file), str(response_file), str(fod_file),
                "-fslgrad", str(checked_bvec), str(checked_bval),
                "-mask", str(mask_file), "-quiet",
            ])

        for index, (suffix, random_seed) in enumerate(VARIANTS):
            ifod_track = task.temp_dir / f"{task.output_stem}_ifod2{suffix}.tck"
            if not ifod_track.exists():
                command = [
                    "tckgen", str(fod_file), str(ifod_track),
                    "-algorithm", "iFOD2", "-select", "10000", "-seed_dynamic", str(fod_file),
                    "-mask", str(mask_file), "-fslgrad", str(checked_bvec), str(checked_bval), "-quiet",
                ]
                _run_quiet(command)
            _convert_track(
                ifod_track,
                task.ifod_output_dirs[index] / f"{task.output_stem}_ifod2.vtk",
            )

        src_file = task.temp_dir / f"{task.output_stem}_dwi.sz"
        if not src_file.exists():
            _run_quiet([
                str(DSI_STUDIO_BIN), "--action=src",
                f"--source={task.dwi_file}", f"--bval={checked_bval}", f"--bvec={checked_bvec}",
                f"--output={src_file}", "--overwrite=1",
            ])

        gqi_file = task.temp_dir / f"{task.output_stem}_gqi.fz"
        if not gqi_file.exists():
            _run_quiet([
                str(DSI_STUDIO_BIN), "--action=rec",
                f"--source={src_file}", "--method=4", f"--mask={mask_file}", "--apply_mask=1",
                "--cmd=[Step T2][Corrections][Motion Correction]+[Step T2][Corrections][Volume Orientation Correction]+[Step T2][B-table][Check B-table]",
                f"--output={gqi_file}", "--overwrite=1",
            ])

        for index, (suffix, random_seed) in enumerate(VARIANTS):
            dsi_track = task.temp_dir / f"{task.output_stem}_dsi_studio{suffix}.tt.gz"
            if not dsi_track.exists():
                command = [
                    str(DSI_STUDIO_BIN), "--action=trk", f"--source={gqi_file}",
                    "--tract_count=10000", "--method=1", f"--output={dsi_track}",
                ]
                if random_seed is not None:
                    command.append(f"--random_seed={random_seed}")
                _run_quiet(command)
            _convert_track(
                dsi_track,
                task.dsi_output_dirs[index] / f"{task.output_stem}_dsi_studio.vtk",
            )
    except (OSError, subprocess.CalledProcessError) as error:
        return f"[ERROR] {task.label}: {error}"
    return f"[DONE] {task.label}"


def _output_dirs(dataset: str, site: str | None = None) -> tuple[tuple[Path, Path, Path], tuple[Path, Path, Path]]:
    suffix = Path(site) if site else Path()
    ifod_dirs = tuple(OUTPUT_ROOT / f"ifod2_{index}" / dataset / suffix for index in range(1, 4))
    dsi_dirs = tuple(OUTPUT_ROOT / f"dsi_studio_{index}" / dataset / suffix for index in range(1, 4))
    return ifod_dirs, dsi_dirs  # type: ignore[return-value]


def _standard_tasks(dataset: str, root_dir: Path, nested_dwi: bool) -> Iterable[BenchmarkTask]:
    ifod_dirs, dsi_dirs = _output_dirs(dataset)
    if nested_dwi:
        subject_dirs = (
            subject
            for site in root_dir.iterdir() if site.is_dir()
            for group in site.iterdir() if group.is_dir()
            for subject in group.iterdir()
            if subject.is_dir() and subject.name.startswith("sub-") and (subject / "dwi").is_dir()
        )
    else:
        subject_dirs = (path for path in root_dir.iterdir() if path.is_dir())

    for subject_dir in subject_dirs:
        subject_id = subject_dir.name
        dwi_dir = subject_dir / "dwi" if nested_dwi else subject_dir
        dwi_file = dwi_dir / f"{subject_id}_dwi.nii.gz"
        yield BenchmarkTask(
            label=f"dataset={dataset}, subject={subject_id}",
            subject_id=subject_id,
            output_stem=subject_id,
            dwi_file=dwi_file,
            bval_file=dwi_file.with_suffix("").with_suffix(".bval"),
            bvec_file=dwi_file.with_suffix("").with_suffix(".bvec"),
            temp_dir=TEMP_ROOT / dataset / subject_id,
            ifod_output_dirs=ifod_dirs,
            dsi_output_dirs=dsi_dirs,
        )


ABIDE_SITES = ("ABIDEII-NYU_1", "ABIDEII-NYU_2", "ABIDEII-SDSU_1", "ABIDEII-TCD_1")


def _abide_tasks(root_dir: Path) -> Iterable[BenchmarkTask]:
    for site in ABIDE_SITES:
        site_dir = root_dir / site
        if not site_dir.is_dir():
            print(f"[WARNING] Site directory {site_dir} does not exist, skipping.")
            continue
        ifod_dirs, dsi_dirs = _output_dirs("ABIDEII", site)
        for subject_dir in site_dir.iterdir():
            if not subject_dir.is_dir():
                continue
            for dwi_file in subject_dir.glob("**/*_dwi_QCed.nii.gz"):
                output_stem = dwi_file.name.removesuffix("_dwi_QCed.nii.gz")
                yield BenchmarkTask(
                    label=f"site={site}, subject={subject_dir.name}, dwi={dwi_file.name}",
                    subject_id=subject_dir.name,
                    output_stem=output_stem,
                    dwi_file=dwi_file,
                    bval_file=dwi_file.with_suffix("").with_suffix(".bval"),
                    bvec_file=dwi_file.with_suffix("").with_suffix(".bvec"),
                    mask_file=Path(str(dwi_file).replace(".nii.gz", "_bse-multi_BrainMask.nii.gz")),
                    temp_dir=TEMP_ROOT / "ABIDEII" / site / subject_dir.name,
                    ifod_output_dirs=ifod_dirs,
                    dsi_output_dirs=dsi_dirs,
                )


def collect_tasks(profile: str, root_dir: Path) -> tuple[list[BenchmarkTask], int]:
    if profile in {"adni", "ppmi"}:
        dataset = profile.upper()
        return list(_standard_tasks(dataset, root_dir, nested_dwi=False)), 6
    if profile == "cnp":
        return list(_standard_tasks("CNP", root_dir, nested_dwi=True)), 6
    if profile == "abideii":
        return list(_abide_tasks(root_dir)), 8
    raise ValueError(f"Unknown profile: {profile}")


DEFAULT_ROOTS = {
    "adni": Path("/dataset/nfs_share01/foundation_test/ADNI"),
    "ppmi": Path("/dataset/nfs_share01/foundation_test/PPMI"),
    "cnp": Path("/dataset/nfs_share01/CNP/Neuropsychiatric"),
    "abideii": Path("/dataset/nfs_share01/ASD/ASD_haolin"),
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(DEFAULT_ROOTS), required=True)
    parser.add_argument("--input-dir", type=Path, help="Override the profile's default input directory.")
    parser.add_argument("--workers", type=int, help="Override the profile's process count.")
    parser.add_argument("--dry-run", action="store_true", help="List work without invoking external tools.")
    args = parser.parse_args(argv)

    root_dir = args.input_dir or DEFAULT_ROOTS[args.profile]
    if not root_dir.is_dir():
        parser.error(f"Input directory does not exist: {root_dir}")
    tasks, default_workers = collect_tasks(args.profile, root_dir)
    print(f"[INFO] Total acquisitions to process: {len(tasks)}")
    if args.dry_run:
        for task in tasks:
            print(task.label)
        return

    for task in tasks:
        for output_dir in (*task.ifod_output_dirs, *task.dsi_output_dirs):
            output_dir.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers or default_workers) as executor:
        for result in executor.map(process_task, tasks):
            print(result, flush=True)


if __name__ == "__main__":
    main()
