"""Cross-platform compatibility shims for loading the YOLOv5 checkpoints.

The trained ``.pt`` checkpoints in ``models/`` were pickled on a Linux machine
running Python 3.13. They embed serialized ``pathlib`` objects, which makes them
fail to unpickle on other platforms in two ways:

1. **Linux -> Windows:** a pickled ``PosixPath`` cannot be instantiated on
   Windows ("cannot instantiate 'PosixPath' on your system"). Re-pointing
   ``pathlib.PosixPath`` at ``WindowsPath`` lets the unpickler build a usable
   path object. (On Windows you can never instantiate a real ``PosixPath``
   anyway, so this alias is safe.)

2. **Python 3.13 -> <= 3.12:** in 3.13 the concrete path classes moved into a
   private ``pathlib._local`` submodule, so a 3.13 pickle references
   ``pathlib._local.PosixPath``. On 3.12 and earlier ``pathlib`` is a single
   module with no ``_local`` submodule, so we register a small shim module that
   re-exports the path classes.

``install_pathlib_compat()`` is idempotent and a no-op once the running
interpreter already matches the checkpoint's environment, so it is safe to call
unconditionally (and on Linux/3.13 it does nothing).
"""

from __future__ import annotations

import pathlib
import sys
import types

_INSTALLED = False


def install_pathlib_compat() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    # 1. Linux-pickled PosixPath -> usable path on Windows.
    if sys.platform == "win32":
        pathlib.PosixPath = pathlib.WindowsPath  # type: ignore[misc]

    # 2. Provide pathlib._local for checkpoints pickled on Python 3.13+.
    if not hasattr(pathlib, "_local"):
        shim = types.ModuleType("pathlib._local")
        for name in ("Path", "PurePath", "PurePosixPath", "PureWindowsPath", "WindowsPath"):
            setattr(shim, name, getattr(pathlib, name))
        # Map PosixPath to the platform-instantiable class.
        shim.PosixPath = (
            pathlib.WindowsPath if sys.platform == "win32" else pathlib.PosixPath
        )
        sys.modules["pathlib._local"] = shim

    _INSTALLED = True
