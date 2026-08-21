"""Compatibility entry point for the UKF tractography dataset split."""

import sys

from processpipe.tractography.split import main


if __name__ == "__main__":
    main(sys.argv[1:])
