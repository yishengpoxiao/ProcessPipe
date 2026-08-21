"""Compatibility entry point for the ABIDE II tractography benchmark profile."""

import sys

from processpipe.workflows.benchmark_tractography import main


if __name__ == "__main__":
    main(["--profile", "abideii", *sys.argv[1:]])
