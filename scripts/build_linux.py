#!/usr/bin/env python3
"""Build Linux ANGLE libraries without window-system dependencies."""

import argparse
import ctypes
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional


ROOT = Path(__file__).resolve().parent.parent
ANGLE_URL = "https://chromium.googlesource.com/angle/angle"
DEPOT_TOOLS_URL = "https://chromium.googlesource.com/chromium/tools/depot_tools.git"

PLATFORM_TAGS = {
    "x86_64": ("x64", "manylinux_2_28_x86_64"),
    "aarch64": ("arm64", "manylinux_2_28_aarch64"),
}

FORBIDDEN_LIBRARIES = {
    "libX11.so.6",
    "libXext.so.6",
    "libgbm.so.1",
    "libwayland-client.so.0",
    "libxcb.so.1",
}


def run(*args: str, cwd: Path, env: Optional[Dict[str, str]] = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def checkout(url: str, path: Path, revision: str) -> None:
    if not (path / ".git").is_dir():
        path.mkdir(parents=True, exist_ok=True)
        run("git", "init", "--quiet", cwd=path)
        run("git", "remote", "add", "origin", url, cwd=path)
    elif (
        subprocess.run(["git", "diff", "--quiet"], cwd=path, check=False).returncode
        or subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=path, check=False
        ).returncode
    ):
        raise RuntimeError(f"Refusing to overwrite changes in {path}")

    run("git", "fetch", "--depth=1", "origin", revision, cwd=path)
    run("git", "checkout", "--detach", "FETCH_HEAD", cwd=path)


def verify_dependencies(library: Path) -> None:
    result = subprocess.run(
        ["readelf", "-d", library],
        env={**os.environ, "LC_ALL": "C"},
        text=True,
        capture_output=True,
        check=True,
    )
    needed = set(re.findall(r"\(NEEDED\).*\[(.+?)\]", result.stdout))
    forbidden = needed & FORBIDDEN_LIBRARIES
    if forbidden:
        names = ", ".join(sorted(forbidden))
        raise RuntimeError(f"{library.name} still depends on {names}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", type=Path, default=ROOT / ".angle-build")
    args = parser.parse_args()

    machine = platform.machine().lower()
    if machine == "amd64":
        machine = "x86_64"
    if machine == "arm64":
        machine = "aarch64"
    if machine not in PLATFORM_TAGS:
        raise RuntimeError(f"Unsupported Linux architecture: {machine}")

    target_cpu, platform_tag = PLATFORM_TAGS[machine]
    angle_revision = (ROOT / "scripts" / "angle-revision.txt").read_text().strip()
    depot_tools_revision = (
        ROOT / "scripts" / "depot-tools-revision.txt"
    ).read_text().strip()

    work_dir = args.work_dir.resolve()
    depot_tools = work_dir / "depot_tools"
    angle = work_dir / "angle"
    checkout(DEPOT_TOOLS_URL, depot_tools, depot_tools_revision)
    checkout(ANGLE_URL, angle, angle_revision)

    (angle / ".gclient").write_text(
        "solutions = [{\n"
        "  'name': '.',\n"
        f"  'url': '{ANGLE_URL}',\n"
        "  'deps_file': 'DEPS',\n"
        "  'managed': False,\n"
        "  'custom_deps': {\n"
        "    'third_party/SwiftShader': None,\n"
        "    'third_party/VK-GL-CTS/src': None,\n"
        "    'third_party/catapult': None,\n"
        "  },\n"
        "  'custom_vars': {\n"
        "    'checkout_angle_cl_deps': False,\n"
        "    'checkout_angle_dawn_deps': False,\n"
        "    'checkout_x86': False,\n"
        "  },\n"
        "}]\n"
        "target_os = []\n"
    )

    env = os.environ.copy()
    env["PATH"] = str(depot_tools) + os.pathsep + env["PATH"]
    env["DEPOT_TOOLS_UPDATE"] = "0"
    run(str(depot_tools / "ensure_bootstrap"), cwd=depot_tools, env=env)
    run("gclient", "sync", "--no-history", "--shallow", cwd=angle, env=env)

    out_dir = angle / "out" / "Release"
    gn_args = " ".join(
        [
            "is_debug=false",
            "is_component_build=false",
            "dcheck_always_on=false",
            "symbol_level=0",
            "use_sysroot=false",
            "use_ozone=false",
            f'target_cpu="{target_cpu}"',
            "angle_build_tests=false",
            "angle_enable_gl=false",
            "angle_enable_vulkan=true",
            "angle_shared_libvulkan=false",
            "angle_enable_swiftshader=false",
            "angle_enable_null=false",
            "angle_enable_wgpu=false",
            "angle_use_x11=false",
            "angle_use_wayland=false",
            "angle_use_gbm=false",
            "angle_use_vulkan_display=false",
            'angle_vulkan_display_mode="headless"',
            "angle_enable_vulkan_validation_layers=false",
            "angle_enable_vulkan_api_dump_layer=false",
            "angle_enable_overlay=false",
            "angle_has_frame_capture=false",
        ]
    )
    run("gn", "gen", str(out_dir), f"--args={gn_args}", cwd=angle, env=env)
    run(
        "autoninja",
        "-C",
        str(out_dir),
        "libEGL",
        "libGLESv2",
        cwd=angle,
        env=env,
    )

    destination = ROOT / "platform_libs" / platform_tag
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    libraries = []
    for name in ("libEGL.so", "libGLESv2.so"):
        source = out_dir / name
        if not source.is_file():
            raise RuntimeError(f"ANGLE did not produce {source}")
        target = destination / name
        shutil.copy2(source, target)
        verify_dependencies(target)
        libraries.append(target)

    mode = getattr(ctypes, "RTLD_GLOBAL", 0)
    for library in libraries:
        ctypes.CDLL(str(library), mode=mode)

    print(f"Built headless ANGLE libraries in {destination}")


if __name__ == "__main__":
    main()
