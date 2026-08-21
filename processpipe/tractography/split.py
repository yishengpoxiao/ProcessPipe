"""Create train/validation/test symlink splits for tractography files."""

from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_INPUT_DIR = Path("/dataset/nfs_share01/HCP/HCP-YA/3T/Tractography_Downsampled")
DEFAULT_SPLITS = (
    (Path("/data/yijie/TractographyTemplate/train_dir_ukf"), 0, 100),
    (Path("/data/yijie/TractographyTemplate/val_dir_ukf"), 100, 120),
    (Path("/data/yijie/TractographyTemplate/test_dir_ukf"), 120, 140),
)


def link_split(files: list[Path], destination_dir: Path, start: int, end: int) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    for tract_file in files[start:end]:
        subject_id = tract_file.name.split("_")[0]
        destination = destination_dir / f"{subject_id}.vtk"
        if not destination.exists():
            destination.symlink_to(tract_file)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    files = sorted([*args.input_dir.glob("*.vtk"), *args.input_dir.glob("*.vtp")])
    if args.dry_run:
        for destination_dir, start, end in DEFAULT_SPLITS:
            for tract_file in files[start:end]:
                print(f"{tract_file} -> {destination_dir}")
        return
    for destination_dir, start, end in DEFAULT_SPLITS:
        link_split(files, destination_dir, start, end)


if __name__ == "__main__":
    main()
