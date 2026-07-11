# comfy-angle

Redistributable [ANGLE](https://chromium.googlesource.com/angle/angle) libraries packaged as Python wheels. Windows and macOS libraries are extracted from [Electron](https://www.electronjs.org/) releases. Linux libraries are built from the corresponding ANGLE revision without X11, Wayland, or GBM dependencies.

Provides `libEGL` and `libGLESv2` for Windows (x64), Linux (x64, arm64), and macOS (arm64).

## Installation

```bash
pip install comfy-angle
```

## Usage

```python
import comfy_angle

# Directory containing the shared libraries
comfy_angle.get_lib_dir()

# Full paths to individual libraries
comfy_angle.get_egl_path()
comfy_angle.get_glesv2_path()
```

## Building wheels from source

```bash
# Install JS dependencies for the download script
cd scripts && npm install && cd ..

# Download the Windows and macOS libraries from Electron
node scripts/download.js [electron-version]

# Build the Linux libraries for the current architecture
# (run this in the matching manylinux_2_28 build image for release wheels)
python scripts/build_linux.py

# Build platform-specific wheels
pip install setuptools wheel build
python scripts/build.py
```

The Linux release build must run in a `manylinux_2_28` environment. Building on a newer distribution may link against a newer glibc and produce a wheel that does not match its platform tag. The publish workflows use pinned manylinux images for both supported architectures.

## License

The ANGLE libraries are licensed under the BSD 3-Clause license. Electron components are covered by the MIT license. See `electron-LICENSE` and `LICENSES.chromium.html` inside the wheel for full details.
