"""Compatibility entry point for PPMI BidsGuess renaming."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processpipe.workflows.bids_organize import main_rename_ppmi


if __name__ == "__main__":
    main_rename_ppmi(sys.argv[1:])
