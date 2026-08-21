"""Compatibility entry point for the PPMI tractography benchmark profile."""

import sys

from processpipe.workflows.benchmark_tractography import main


if __name__ == "__main__":
    main(["--profile", "ppmi", *sys.argv[1:]])
