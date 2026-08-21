"""Compatibility entry point for ABVIB DWI filtering and organization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processpipe.workflows.bids_organize import main_reorganize_abvib


if __name__ == "__main__":
    main_reorganize_abvib(sys.argv[1:])
