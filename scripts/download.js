#!/usr/bin/env node
/**
 * Download Electron releases and extract only the ANGLE libraries for each platform.
 *
 * Usage:
 *   npm install
 *   node download.js [electron-version]
 *
 */

const { downloadArtifact } = require("@electron/get");
const yauzl = require("yauzl");
const fs = require("fs");
const path = require("path");
const { pipeline } = require("stream/promises");

// Map of our wheel platform tags to Electron download parameters and the
// library filenames we need to extract.
const PLATFORMS = {
  macosx_11_0_arm64: {
    electronPlatform: "darwin",
    electronArch: "arm64",
    libs: ["libEGL.dylib", "libGLESv2.dylib"],
  },
  manylinux_2_28_aarch64: {
    electronPlatform: "linux",
    electronArch: "arm64",
    libs: ["libEGL.so", "libGLESv2.so"],
  },
  manylinux_2_28_x86_64: {
    electronPlatform: "linux",
    electronArch: "x64",
    libs: ["libEGL.so", "libGLESv2.so"],
  },
  win_amd64: {
    electronPlatform: "win32",
    electronArch: "x64",
    libs: ["libEGL.dll", "libGLESv2.dll"],
  },
};

// Files to extract from each zip: the ANGLE libs plus license files.
// License files are renamed on extraction via the renames map.
const LICENSE_FILES = {
  "LICENSE": "electron-LICENSE",
  "LICENSES.chromium.html": "LICENSES.chromium.html",
};

/**
 * Open a zip and extract files whose basename is in `fileNames`.
 * `renames` maps original basename -> destination basename.
 * Returns a map of destBasename -> extracted file path.
 */
function extractFromZip(zipPath, destDir, fileNames, renames = {}) {
  return new Promise((resolve, reject) => {
    const needed = new Set(fileNames);
    const extracted = {};

    yauzl.open(zipPath, { lazyEntries: true }, (err, zipfile) => {
      if (err) return reject(err);

      zipfile.readEntry();
      zipfile.on("entry", (entry) => {
        const basename = path.basename(entry.fileName);
        if (needed.has(basename) && !entry.fileName.endsWith("/")) {
          zipfile.openReadStream(entry, (err, readStream) => {
            if (err) return reject(err);

            const destName = renames[basename] || basename;
            const destPath = path.join(destDir, destName);
            const writeStream = fs.createWriteStream(destPath);
            pipeline(readStream, writeStream).then(() => {
              extracted[destName] = destPath;
              needed.delete(basename);
              zipfile.readEntry();
            }).catch(reject);
          });
        } else {
          zipfile.readEntry();
        }
      });

      zipfile.on("end", () => resolve(extracted));
      zipfile.on("error", reject);
    });
  });
}

async function main() {
  const versionFile = path.join(__dirname, "electron-version.txt");
  const defaultVersion = fs.readFileSync(versionFile, "utf-8").trim();
  const electronVersion = process.argv[2] || defaultVersion;
  const outBase = path.resolve(__dirname, "..", "platform_libs");

  console.log(`Downloading ANGLE libs from Electron v${electronVersion}\n`);

  fs.mkdirSync(outBase, { recursive: true });

  // De-duplicate downloads: darwin/arm64 is used for both macOS tags.
  // Cache maps "platform-arch" -> { libName: extractedPath }
  const downloadCache = {};
  let licensesExtracted = false;

  for (const [platTag, cfg] of Object.entries(PLATFORMS)) {
    const cacheKey = `${cfg.electronPlatform}-${cfg.electronArch}`;
    const platOutDir = path.join(outBase, platTag);
    fs.mkdirSync(platOutDir, { recursive: true });

    let extracted = downloadCache[cacheKey];

    if (!extracted) {
      console.log(
        `Downloading electron-v${electronVersion}-${cfg.electronPlatform}-${cfg.electronArch}.zip ...`,
      );

      const zipPath = await downloadArtifact({
        version: electronVersion,
        platform: cfg.electronPlatform,
        arch: cfg.electronArch,
        artifactName: "electron",
      });

      console.log(`Extracting ANGLE libs from zip ...`);
      extracted = await extractFromZip(zipPath, platOutDir, cfg.libs);
      downloadCache[cacheKey] = extracted;

      // Extract license files once (they're identical across platforms).
      if (!licensesExtracted) {
        const licenseFiles = Object.keys(LICENSE_FILES);
        await extractFromZip(zipPath, outBase, licenseFiles, LICENSE_FILES);
        console.log(`  Extracted license files to ${outBase}/`);
        licensesExtracted = true;
      }
    } else {
      console.log(`Using cached download for ${cacheKey}`);
      // Copy previously extracted files into this platform's output dir.
      for (const lib of cfg.libs) {
        if (!extracted[lib]) {
          throw new Error(`Cached extraction missing ${lib} for ${cacheKey}`);
        }
        const dest = path.join(platOutDir, lib);
        fs.copyFileSync(extracted[lib], dest);
      }
    }

    for (const lib of cfg.libs) {
      const libPath = path.join(platOutDir, lib);
      if (fs.existsSync(libPath)) {
        const sizeMB = (fs.statSync(libPath).size / 1024 / 1024).toFixed(1);
        console.log(`  ${platTag}/${lib}  (${sizeMB} MB)`);
      } else {
        throw new Error(`${lib} not found in zip for ${platTag}`);
      }
    }
    console.log();
  }

  console.log("Done. Libraries saved to platform_libs/");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
