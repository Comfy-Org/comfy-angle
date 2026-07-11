#!/usr/bin/env python3
"""
Build platform-specific wheels for comfy-angle.

Usage:
    1. First run the download script to populate platform_libs/:
         node scripts/download.js [electron-version]
    2. Then build all wheels:
         python scripts/build.py

Wheels are written to dist/.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
PLATFORM_LIBS = ROOT / "platform_libs"
DIST = ROOT / "dist"
PACKAGE_DIR = ROOT / "comfy_angle"
LIBS_DIR = PACKAGE_DIR / "libs"

PLATFORM_TAGS = [
    "macosx_11_0_arm64",
    "manylinux_2_28_aarch64",
    "manylinux_2_28_x86_64",
    "win_amd64",
]

LICENSE_FILES = ["electron-LICENSE", "LICENSES.chromium.html"]
FORBIDDEN_LINUX_LIBRARIES = {
    "libX11.so.6",
    "libXext.so.6",
    "libgbm.so.1",
    "libwayland-client.so.0",
    "libxcb.so.1",
}


def verify_linux_dependencies(library: Path) -> None:
    result = subprocess.run(
        ["readelf", "-d", library],
        env={**os.environ, "LC_ALL": "C"},
        text=True,
        capture_output=True,
        check=True,
    )
    needed = set(re.findall(r"\(NEEDED\).*\[(.+?)\]", result.stdout))
    forbidden = needed & FORBIDDEN_LINUX_LIBRARIES
    if forbidden:
        names = ", ".join(sorted(forbidden))
        raise RuntimeError(f"{library} depends on {names}")


def build_wheel(platform_tag: str) -> Optional[Path]:
    src_libs = PLATFORM_LIBS / platform_tag
    if not src_libs.is_dir():
        print(f"  SKIP {platform_tag}: no libs found at {src_libs}")
        return None

    lib_files = sorted(src_libs.iterdir())
    if not lib_files:
        print(f"  SKIP {platform_tag}: libs directory is empty")
        return None

    print(f"  Building wheel for {platform_tag} ...")

    if platform_tag.startswith("manylinux"):
        for lib_file in lib_files:
            verify_linux_dependencies(lib_file)

    # Clean stale build artifacts so setuptools doesn't carry over libs
    # from previous platform iterations.
    for d in [ROOT / "build", ROOT / "comfy_angle.egg-info"]:
        if d.exists():
            shutil.rmtree(d)

    # Populate comfy_angle/libs/ with this platform's binaries.
    if LIBS_DIR.exists():
        shutil.rmtree(LIBS_DIR)
    LIBS_DIR.mkdir()
    for lib_file in lib_files:
        shutil.copy2(lib_file, LIBS_DIR / lib_file.name)

    # Copy license files into the package directory.
    for name in LICENSE_FILES:
        src = PLATFORM_LIBS / name
        if src.exists():
            shutil.copy2(src, PACKAGE_DIR / name)

    # Build wheel using python -m build, overriding the platform tag via
    # config-settings for setuptools bdist_wheel.
    env = os.environ.copy()
    env["DIST_EXTRA_CONFIG"] = str(ROOT / "_bdist_wheel.cfg")

    # Write a temporary setup.cfg override for the platform tag.
    cfg = ROOT / "_bdist_wheel.cfg"
    cfg.write_text(f"[bdist_wheel]\nplat_name={platform_tag}\n")

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                str(DIST),
            ],
            cwd=str(ROOT),
            check=True,
            env=env,
        )
    finally:
        cfg.unlink(missing_ok=True)

    # Find the wheel that was just built.
    wheels = sorted(DIST.glob(f"*-{platform_tag}.whl"), key=lambda p: p.stat().st_mtime)
    if wheels:
        whl = wheels[-1]
        size_mb = whl.stat().st_size / 1024 / 1024
        print(f"    -> {whl}  ({size_mb:.1f} MB)")
        return whl
    return None


def cleanup():
    """Remove temporary files from the package directory."""
    if LIBS_DIR.exists():
        shutil.rmtree(LIBS_DIR)
    for name in LICENSE_FILES:
        f = PACKAGE_DIR / name
        if f.exists():
            f.unlink()
    # Clean up build artifacts.
    for d in [ROOT / "build", ROOT / "comfy_angle.egg-info"]:
        if d.exists():
            shutil.rmtree(d)
    cfg = ROOT / "_bdist_wheel.cfg"
    if cfg.exists():
        cfg.unlink()


def main():
    # Verify that platform libs have been downloaded.
    if not PLATFORM_LIBS.is_dir() or not any(PLATFORM_LIBS.iterdir()):
        print(
            f"ERROR: {PLATFORM_LIBS} is missing or empty.\n"
            f"Run  node scripts/download.js  first."
        )
        sys.exit(1)

    DIST.mkdir(exist_ok=True)

    print("Building comfy-angle wheels\n")

    try:
        built = []
        for tag in PLATFORM_TAGS:
            result = build_wheel(tag)
            if result:
                built.append(result)
        print(f"\nBuilt {len(built)} wheel(s) in {DIST}/")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
