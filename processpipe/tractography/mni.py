"""Generate DSI Studio tractography and register it to MNI space."""

from __future__ import annotations

import argparse
from pathlib import Path

from processpipe.core.commands import run_command


DSI_STUDIO_BIN = Path("/data/yijie/software/dsi-studio/dsi_studio")
MNI_TEMPLATE = Path("/data/yijie/Tractography/resources/MNI_FA_template.nii.gz")
DEFAULT_ROOT = Path("/data/dataset/FiberDataHub/data-hcp/lifespan/hcp-ya")
DEFAULT_SPLITS = (
    (Path("/data/yijie/TractData/larger_train"), 0, 200),
    (Path("/data/yijie/TractData/larger_val"), 200, 220),
    (Path("/data/yijie/TractData/one_test"), 220, 225),
)


def export_dti_metric(gqi_file: Path) -> Path:
    dwi_dir = gqi_file.parent.parent
    dti_dir = dwi_dir / "dti"
    dti_dir.mkdir(parents=True, exist_ok=True)
    exported_fa = dti_dir / f"{gqi_file.name}.dti_fa.nii.gz"
    source_fa = gqi_file.parent / f"{gqi_file.name}.dti_fa.nii.gz"
    if not exported_fa.exists() and not source_fa.exists():
        run_command([
            str(DSI_STUDIO_BIN), "--action=exp", f"--source={gqi_file}", "--export=dti_fa",
        ])
    if not exported_fa.exists() and source_fa.exists():
        source_fa.rename(exported_fa)
    return exported_fa


def run_tractography(gqi_file: Path, tract_count: int = 100_000) -> Path:
    """Create the original-space tractogram for a GQI reconstruction."""
    tractogram = gqi_file.parent / gqi_file.name.replace(".gqi.fz", ".orig.tt.gz")
    run_command([
        str(DSI_STUDIO_BIN), "--action=trk", f"--source={gqi_file}",
        f"--tract_count={tract_count}", "--method=1", "--thread_count=64",
        f"--output={tractogram}",
    ])
    return tractogram


def register_to_mni(gqi_file: Path, fa_file: Path | None = None) -> Path:
    dwi_dir = gqi_file.parent.parent
    dti_dir = dwi_dir / "dti"
    fa_file = fa_file or dti_dir / f"{gqi_file.name}.dti_fa.nii.gz"
    original_tractogram = gqi_file.parent / gqi_file.name.replace(".gqi.fz", ".orig.tt.gz")
    tractography_dir = dwi_dir / "tractography"
    tractography_dir.mkdir(parents=True, exist_ok=True)
    mni_tractogram = tractography_dir / gqi_file.name.replace(".gqi.fz", ".mni.tt.gz")
    registered_tractogram = dti_dir / gqi_file.name.replace(".gqi.fz", ".orig.tt.gz.wp.tt.gz")
    mni_fa = dti_dir / f"{gqi_file.name}.dti_fa.mni.nii.gz"
    registered_fa = dti_dir / f"{gqi_file.name}.dti_fa.nii.gz.wp.nii.gz"
    run_command([
        str(DSI_STUDIO_BIN), "--action=reg", "--reg_type=0", f"--source={fa_file}",
        f"--to={MNI_TEMPLATE}", f"--s2t={original_tractogram},{fa_file}", f"--output={dti_dir}",
    ])
    if registered_tractogram.exists() and not mni_tractogram.exists():
        registered_tractogram.rename(mni_tractogram)
    if registered_fa.exists() and not mni_fa.exists():
        registered_fa.rename(mni_fa)
    return mni_tractogram


def link_mni_tractogram(gqi_file: Path, source: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    subject_id = gqi_file.name.replace(".gqi.fz", "").replace(".gqi", "").replace(".fz", "")
    destination = destination_dir / f"{subject_id}.mni.tt.gz"
    if not destination.exists():
        destination.symlink_to(source)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--tract-count", type=int, default=100_000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    gqi_files = sorted(args.input_dir.glob("**/*.gqi.fz"))
    for output_dir, start, end in DEFAULT_SPLITS:
        for gqi_file in gqi_files[start:end]:
            expected_output = gqi_file.parent.parent / "tractography" / gqi_file.name.replace(".gqi.fz", ".mni.tt.gz")
            if args.dry_run:
                print(f"{gqi_file} -> {output_dir}")
                continue
            fa_file = export_dti_metric(gqi_file)
            run_tractography(gqi_file, args.tract_count)
            mni_tractogram = register_to_mni(gqi_file, fa_file)
            link_mni_tractogram(gqi_file, mni_tractogram or expected_output, output_dir)


if __name__ == "__main__":
    main()
