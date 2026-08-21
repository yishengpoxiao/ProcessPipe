"""Compatibility entry point for T1w/FreeSurfer preprocessing."""

import sys

from processpipe.workflows.t1w import main


if __name__ == "__main__":
    main(sys.argv[1:])
