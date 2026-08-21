"""Dataset discovery tests for the shared benchmark workflow."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from processpipe.workflows.benchmark_tractography import collect_tasks


class BenchmarkProfileTests(unittest.TestCase):
    def test_flat_profile_discovers_subject_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "sub-01").mkdir()
            tasks, workers = collect_tasks("adni", root)
            self.assertEqual(workers, 6)
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].dwi_file.name, "sub-01_dwi.nii.gz")

    def test_nested_profile_discovers_dwi_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "site-a" / "control" / "sub-01" / "dwi").mkdir(parents=True)
            tasks, workers = collect_tasks("cnp", root)
            self.assertEqual(workers, 6)
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].dwi_file.parent.name, "dwi")


if __name__ == "__main__":
    unittest.main()
