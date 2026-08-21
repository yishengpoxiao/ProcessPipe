"""Compatibility entry point for ABVIB DICOM-to-NIfTI conversion."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processpipe.workflows.bids_organize import main_convert_abvib


if __name__ == "__main__":
    main_convert_abvib(sys.argv[1:])
