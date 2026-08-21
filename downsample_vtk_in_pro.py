"""Compatibility entry point for tractography downsampling."""

import sys

from processpipe.tractography.downsample import main


if __name__ == "__main__":
    main(sys.argv[1:])
