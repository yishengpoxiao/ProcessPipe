"""Small, explicit wrappers around external command execution."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence


def run_command(
    command: Sequence[str] | str,
    *,
    check: bool = True,
    quiet: bool = False,
    shell: bool = False,
) -> subprocess.CompletedProcess:
    """Run an external command with consistent error and output handling."""
    return subprocess.run(
        command,
        check=check,
        shell=shell,
        stdout=subprocess.DEVNULL if quiet else None,
    )


def command_succeeds(command: Sequence[str] | str, *, shell: bool = False) -> bool:
    """Return whether a command completed successfully without raising."""
    try:
        run_command(command, check=True, shell=shell)
    except subprocess.CalledProcessError:
        return False
    return True
