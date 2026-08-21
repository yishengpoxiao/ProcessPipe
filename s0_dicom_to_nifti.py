"""Compatibility entry point for ASD DICOM-to-NIfTI conversion."""

import sys

from processpipe.workflows.bids_organize import main_convert_asd


if __name__ == "__main__":
    main_convert_asd(sys.argv[1:])
