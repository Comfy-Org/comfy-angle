"""Redistributable Google ANGLE libraries."""

import os
import sys
from importlib.metadata import version as _version, PackageNotFoundError

try:
    __version__ = _version("comfy-angle")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["get_lib_dir", "get_egl_path", "get_glesv2_path"]

_LIB_DIR = os.path.join(os.path.dirname(__file__), "libs")


def get_lib_dir() -> str:
    """Return the path to the directory containing ANGLE shared libraries."""
    return _LIB_DIR


def get_egl_path() -> str:
    """Return the path to the EGL library."""
    if sys.platform == "win32":
        return os.path.join(_LIB_DIR, "libEGL.dll")
    elif sys.platform == "darwin":
        return os.path.join(_LIB_DIR, "libEGL.dylib")
    else:
        return os.path.join(_LIB_DIR, "libEGL.so")


def get_glesv2_path() -> str:
    """Return the path to the GLESv2 library."""
    if sys.platform == "win32":
        return os.path.join(_LIB_DIR, "libGLESv2.dll")
    elif sys.platform == "darwin":
        return os.path.join(_LIB_DIR, "libGLESv2.dylib")
    else:
        return os.path.join(_LIB_DIR, "libGLESv2.so")
