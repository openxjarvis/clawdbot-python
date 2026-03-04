"""ACP secret-file reader — mirrors src/acp/secret-file.ts

Reads a token or password from a file on disk, supporting ~ home-directory paths.
"""
from __future__ import annotations

import os


def read_secret_from_file(file_path: str, label: str) -> str:
    """
    Read a secret (token/password) from a file.

    Resolves ~ to the user's home directory.  Leading/trailing whitespace is
    stripped from both the path and the secret value.

    Raises ValueError if the path is empty or the file is empty.
    Raises OSError if the file cannot be read.
    """
    resolved = os.path.expanduser(file_path.strip())
    if not resolved:
        raise ValueError(f"{label} file path is empty.")
    try:
        with open(resolved, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise OSError(f"Failed to read {label} file at {resolved}: {exc}") from exc
    secret = raw.strip()
    if not secret:
        raise ValueError(f"{label} file at {resolved} is empty.")
    return secret
