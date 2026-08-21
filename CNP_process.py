"""Compatibility entry point for the CNP tractography benchmark profile."""

import sys

from processpipe.workflows.benchmark_tractography import main


if __name__ == "__main__":
    main(["--profile", "cnp", *sys.argv[1:]])
