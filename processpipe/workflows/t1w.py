"""FreeSurfer T1w preprocessing workflow."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from processpipe.core.commands import run_command


DEFAULT_INPUT_DIR = Path("/data/private_data/ASD_Li_lab")
DEFAULT_FREESURFER_DIR = Path("/data/software/freesurfer")


def _process_subject(task: tuple[str, str, Path, Path]) -> None:
    site, subject, input_dir, freesurfer_dir = task
    anat_dir = input_dir / site / subject / "anat"
    t1w_files = sorted(anat_dir.glob("*_T1w.nii.gz"))
    if not t1w_files:
        print(f"[WARN] No T1w for: site={site}, subject={subject}")
        return
    print(f"[INFO] Start recon-all: site={site}, subject={subject}")
    command = "\n".join([
        f"export FREESURFER_HOME={freesurfer_dir}",
        "source $FREESURFER_HOME/SetUpFreeSurfer.sh",
        f"export SUBJECTS_DIR={anat_dir}",
        f"recon-all -i {t1w_files[0]} -s {subject} -all -threads 80",
    ])
    run_command(command, shell=True, check=False)
    print(f"[INFO] Finished processing subject {subject} at site {site}.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--freesurfer-dir", type=Path, default=DEFAULT_FREESURFER_DIR)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    tasks = [
        (site_dir.name, subject_dir.name, args.input_dir, args.freesurfer_dir)
        for site_dir in args.input_dir.iterdir() if site_dir.is_dir()
        for subject_dir in site_dir.iterdir()
        if subject_dir.is_dir() and any((subject_dir / "anat").glob("*_T1w.nii.gz"))
    ]
    print(f"[INFO] Total subjects to process: {len(tasks)}")
    if args.dry_run:
        for site, subject, _, _ in tasks:
            print(f"site={site}, subject={subject}")
        return
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        list(executor.map(_process_subject, tasks))


if __name__ == "__main__":
    main()
