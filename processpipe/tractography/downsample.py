"""Downsample tractography directories once each with White Matter Analysis."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from processpipe.core.commands import run_command


WMA_PYTHON = Path("/data/yijie/miniconda3/envs/wma/bin/python")
WMA_PREPROCESS = Path("/data/yijie/whitematteranalysis/bin/wm_preprocess_all.py")
DEFAULT_ROOT = Path("/dataset/nfs_share01/HCP/HCP-YA/3T")


def process_directory(source_dir: Path, destination_dir: Path) -> None:
    run_command([
        str(WMA_PYTHON), str(WMA_PREPROCESS), str(source_dir), str(destination_dir),
        "-f", "100000", "-l", "20", "-lmax", "260",
    ])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_ROOT / "Tractography")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ROOT / "Tractography_Downsampled")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    files = [*args.input_dir.rglob("*.vtk"), *args.input_dir.rglob("*.vtp")]
    source_dirs = sorted({path.parent for path in files})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        print("\n".join(str(path) for path in source_dirs))
        return
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        list(executor.map(lambda path: process_directory(path, args.output_dir), source_dirs))


if __name__ == "__main__":
    main()
