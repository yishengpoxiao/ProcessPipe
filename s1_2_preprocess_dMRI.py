"""Compatibility entry point for the legacy UKF/WMA dMRI workflow."""

import sys

from processpipe.workflows.ukf_wma import main


if __name__ == "__main__":
    main(sys.argv[1:])
