"""Compatibility entry point for DSI Studio output organization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processpipe.workflows.bids_organize import main_organize_dsi


if __name__ == "__main__":
    main_organize_dsi(sys.argv[1:])
