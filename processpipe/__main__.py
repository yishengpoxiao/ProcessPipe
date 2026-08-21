"""Unified command dispatcher for ProcessPipe workflows."""

from __future__ import annotations

import argparse
from importlib import import_module
import sys

COMMANDS = {
    "benchmark": ("processpipe.workflows.benchmark_tractography", "main"),
    "bids-asd": ("processpipe.workflows.bids_organize", "main_convert_asd"),
    "bids-abvib-convert": ("processpipe.workflows.bids_organize", "main_convert_abvib"),
    "bids-rename": ("processpipe.workflows.bids_organize", "main_rename_ppmi"),
    "bids-reorganize": ("processpipe.workflows.bids_organize", "main_reorganize_abvib"),
    "bids-dsi-output": ("processpipe.workflows.bids_organize", "main_organize_dsi"),
    "dsi-mni": ("processpipe.workflows.dsi_mni", "main"),
    "t1w": ("processpipe.workflows.t1w", "main"),
    "ukf-wma": ("processpipe.workflows.ukf_wma", "main"),
    "tract-mni": ("processpipe.tractography.mni", "main"),
    "tract-downsample": ("processpipe.tractography.downsample", "main"),
    "tract-split": ("processpipe.tractography.split", "main"),
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS), help="Workflow to run.")
    remaining = list(sys.argv[1:] if argv is None else argv)
    if not remaining or remaining[0] in {"-h", "--help"}:
        parser.print_help()
        return
    command = remaining.pop(0)
    if command not in COMMANDS:
        parser.error(f"unknown command: {command}")
    module_name, function_name = COMMANDS[command]
    getattr(import_module(module_name), function_name)(remaining)


if __name__ == "__main__":
    main()
