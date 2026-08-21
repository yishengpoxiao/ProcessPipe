"""BIDS-style filename, metadata, and sidecar helpers."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import json


SIDECAR_SUFFIXES = (".bval", ".bvec", ".json")


def nifti_stem(path: Path) -> Path:
    """Return a NIfTI path without its `.nii.gz` suffix."""
    return path.with_suffix("").with_suffix("")


def sidecar_paths(nifti_path: Path) -> dict[str, Path]:
    stem = nifti_stem(nifti_path)
    return {suffix: stem.with_suffix(suffix) for suffix in SIDECAR_SUFFIXES}


def read_bids_json(json_path: Path) -> dict[str, Any]:
    """Read JSON while repairing the malformed backslashes seen in source data."""
    content = json_path.read_text()
    content = re.sub(r'(?<!\\)\\(?![\\ntr"u])', r"\\\\", content)
    return json.loads(content, strict=False)


def bids_guess_stem(
    bids_guess: Any,
    subject_id: str,
    session_id: str = "",
) -> tuple[str, str]:
    """Return `(modality_directory, filename_stem)` for a BidsGuess value.

    Unrecognised or absent guesses are deliberately placed in `unknown`, matching
    the historical scripts rather than silently inventing a BIDS label.
    """
    prefix = "_".join(part for part in (subject_id, session_id) if part)
    if not isinstance(bids_guess, (list, tuple)) or len(bids_guess) < 2:
        return "unknown", f"{prefix}_unknown"

    modality_dir, description_text = bids_guess[0], bids_guess[1]
    if not isinstance(modality_dir, str) or not isinstance(description_text, str):
        return "unknown", f"{prefix}_unknown"

    description = description_text.split("_")
    if len(description) == 4:
        run_id, modality = description[2], description[3]
        modality = "dwi" if modality == "epi" else modality
        return modality_dir, f"{prefix}_{run_id}_{modality}"
    if len(description) == 5:
        direction, run_id, modality = description[2], description[3], description[4]
        modality = "dwi" if modality == "epi" else modality
        return modality_dir, f"{prefix}_{direction}_{run_id}_{modality}"
    return "unknown", f"{prefix}_unknown"


def move_nifti_bundle(source_nifti: Path, destination_nifti: Path) -> None:
    """Move a NIfTI file and any available BIDS sidecars together."""
    destination_nifti.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_nifti), str(destination_nifti))
    source_sidecars = sidecar_paths(source_nifti)
    destination_sidecars = sidecar_paths(destination_nifti)
    for suffix, source in source_sidecars.items():
        if source.exists():
            shutil.move(str(source), str(destination_sidecars[suffix]))


def phase_direction(file_path: Path) -> str | None:
    """Infer AP/PA/LR/RL/SI/IS from a filename, if present."""
    name = file_path.name.casefold()
    patterns = {
        "ap": r"(?:^|[\W_])a[\-_]?p(?=$|[\W_])",
        "pa": r"(?:^|[\W_])p[\-_]?a(?=$|[\W_])",
        "lr": r"(?:^|[\W_])l[\-_]?r(?=$|[\W_])",
        "rl": r"(?:^|[\W_])r[\-_]?l(?=$|[\W_])",
        "si": r"(?:^|[\W_])s[\-_]?i(?=$|[\W_])",
        "is": r"(?:^|[\W_])i[\-_]?s(?=$|[\W_])",
    }
    return next((key for key, pattern in patterns.items() if re.search(pattern, name)), None)
