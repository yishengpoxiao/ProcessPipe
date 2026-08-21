"""Compatibility entry point for MNI-space DSI Studio tractography."""

import sys

from processpipe.tractography.mni import main


if __name__ == "__main__":
    main(sys.argv[1:])
