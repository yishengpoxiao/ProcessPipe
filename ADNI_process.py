"""Compatibility entry point for the ADNI tractography benchmark profile."""

import sys

from processpipe.workflows.benchmark_tractography import main


if __name__ == "__main__":
    main(["--profile", "adni", *sys.argv[1:]])
