"""Regression tests for file-system-only helpers; no imaging tools are required."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from processpipe.core.bids import bids_guess_stem, move_nifti_bundle, phase_direction, sidecar_paths


class BidsHelperTests(unittest.TestCase):
    def test_bids_guess_stem_normalizes_epi(self) -> None:
        modality, stem = bids_guess_stem(["func", "x_y_run-01_epi"], "sub-01", "ses-02")
        self.assertEqual(modality, "func")
        self.assertEqual(stem, "sub-01_ses-02_run-01_dwi")

    def test_unknown_bids_guess_is_explicit(self) -> None:
        self.assertEqual(bids_guess_stem(None, "sub-01"), ("unknown", "sub-01_unknown"))

    def test_move_nifti_bundle_moves_available_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.nii.gz"
            source.write_text("nifti")
            for sidecar in sidecar_paths(source).values():
                sidecar.write_text(sidecar.suffix)
            destination = root / "dwi" / "sub-01_dwi.nii.gz"
            move_nifti_bundle(source, destination)
            self.assertTrue(destination.exists())
            self.assertFalse(source.exists())
            self.assertTrue(all(path.exists() for path in sidecar_paths(destination).values()))

    def test_phase_direction_recognizes_delimited_tokens_only(self) -> None:
        self.assertEqual(phase_direction(Path("sub-01_dir-AP_dwi.nii.gz")), "ap")
        self.assertIsNone(phase_direction(Path("sub-01_shape_dwi.nii.gz")))


if __name__ == "__main__":
    unittest.main()
