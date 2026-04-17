"""
install/build.py — CI packaging script.
Run by GitHub Actions on every tagged release.
Builds .deb, .rpm, PKGBUILD, .exe (NSIS), .pkg (macOS) from one script.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT    = Path(__file__).parent.parent
VERSION = (ROOT / "version.txt").read_text().strip() if (ROOT / "version.txt").exists() else "1.0.0"
DIST    = ROOT / "dist"


def clean():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)


def build_binary():
    """PyInstaller → single self-contained binary (no Python needed on target)."""
    print("[build] Building binary with PyInstaller...")
    subprocess.run([
        "pyinstaller",
        "--onefile",
        "--name", "openclaw",
        "--add-data", f"{ROOT / 'config'}:config",
        "--add-data", f"{ROOT / 'interface' / 'web'}:interface/web",
        str(ROOT / "main.py"),
    ], check=True)
    print("[build] Binary built.")


def build_deb():
    """Build .deb package for Debian/Ubuntu."""
    print("[build] Building .deb...")
    pkg_dir = DIST / f"openclaw_{VERSION}_amd64"
    for sub in ["DEBIAN", "usr/local/bin", "lib/systemd/user",
                "usr/share/applications"]:
        (pkg_dir / sub).mkdir(parents=True, exist_ok=True)

    # Control file
    (pkg_dir / "DEBIAN" / "control").write_text(f"""Package: openclaw
Version: {VERSION}
Architecture: amd64
Maintainer: OpenClaw Team <hello@openclaw.io>
Depends: python3 (>= 3.11)
Description: OpenClaw — local AI assistant with self-learning modules
""")

    # Binary
    shutil.copy(ROOT / "dist" / "openclaw", pkg_dir / "usr/local/bin/openclaw")
    os.chmod(pkg_dir / "usr/local/bin/openclaw", 0o755)

    # Systemd user service
    (pkg_dir / "lib/systemd/user/openclaw.service").write_text(f"""[Unit]
Description=OpenClaw AI Assistant
After=network.target

[Service]
ExecStart=/usr/local/bin/openclaw
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
""")

    # Desktop entry
    (pkg_dir / "usr/share/applications/openclaw.desktop").write_text(f"""[Desktop Entry]
Name=OpenClaw
Exec=/usr/local/bin/openclaw
Icon=openclaw
Type=Application
Categories=Utility;
""")

    subprocess.run(["dpkg-deb", "--build", str(pkg_dir)], check=True)
    print(f"[build] .deb built: {pkg_dir}.deb")


def build_rpm_spec():
    """Generate .spec file for RPM build (Fedora/RHEL/COPR)."""
    print("[build] Generating .spec for RPM...")
    spec = DIST / "openclaw.spec"
    spec.write_text(f"""Name:    openclaw
Version: {VERSION}
Release: 1%{{?dist}}
Summary: Local AI assistant with self-learning modules
License: MIT
URL:     https://github.com/openclaw/openclaw

%description
OpenClaw is a local AI assistant with modular, self-learning expert models.

%install
mkdir -p %{{buildroot}}/usr/local/bin
install -m 755 openclaw %{{buildroot}}/usr/local/bin/openclaw

%files
/usr/local/bin/openclaw

%changelog
* $(date '+%a %b %d %Y') OpenClaw Team - {VERSION}-1
- Release {VERSION}
""")
    print(f"[build] .spec written: {spec}")


def build_pkgbuild():
    """Generate PKGBUILD for AUR (Arch Linux)."""
    print("[build] Generating PKGBUILD for AUR...")
    pb = DIST / "PKGBUILD"
    pb.write_text(f"""# Maintainer: OpenClaw Team <hello@openclaw.io>
pkgname=openclaw
pkgver={VERSION}
pkgrel=1
pkgdesc="Local AI assistant with self-learning expert modules"
arch=('x86_64')
url="https://github.com/openclaw/openclaw"
license=('MIT')
depends=('python>=3.11')
source=("https://github.com/openclaw/openclaw/releases/download/v{VERSION}/openclaw-linux-amd64")
sha256sums=('SKIP')

package() {{
  install -Dm755 "$srcdir/openclaw-linux-amd64" "$pkgdir/usr/local/bin/openclaw"
}}
""")
    print(f"[build] PKGBUILD written: {pb}")


def build_nsis():
    """Generate NSIS installer script for Windows."""
    print("[build] Generating NSIS script for Windows...")
    nsi = DIST / "openclaw_installer.nsi"
    nsi.write_text(f"""!define APP_NAME "OpenClaw"
!define APP_VERSION "{VERSION}"
!define INSTALL_DIR "$PROGRAMFILES64\\OpenClaw"

Name "${{APP_NAME}} ${{APP_VERSION}}"
OutFile "openclaw-{VERSION}-setup.exe"
InstallDir "${{INSTALL_DIR}}"
RequestExecutionLevel admin

Section "Install"
  SetOutPath "$INSTDIR"
  File "openclaw.exe"
  CreateShortCut "$DESKTOP\\OpenClaw.lnk" "$INSTDIR\\openclaw.exe"
  WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Run" "OpenClaw" "$INSTDIR\\openclaw.exe"
  WriteUninstaller "$INSTDIR\\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\\openclaw.exe"
  Delete "$DESKTOP\\OpenClaw.lnk"
  DeleteRegValue HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Run" "OpenClaw"
  RMDir "$INSTDIR"
SectionEnd
""")
    print(f"[build] NSIS script written: {nsi}")


def build_macos_pkg():
    """Generate macOS LaunchAgent plist + package structure."""
    print("[build] Generating macOS package structure...")
    pkg_dir = DIST / "openclaw-macos"
    la_dir  = pkg_dir / "Library" / "LaunchAgents"
    la_dir.mkdir(parents=True, exist_ok=True)

    (la_dir / "io.openclaw.plist").write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>             <string>io.openclaw</string>
  <key>ProgramArguments</key>  <array><string>/usr/local/bin/openclaw</string></array>
  <key>RunAtLoad</key>         <true/>
  <key>KeepAlive</key>         <true/>
  <key>StandardOutPath</key>   <string>/tmp/openclaw.log</string>
  <key>StandardErrorPath</key> <string>/tmp/openclaw.err</string>
</dict>
</plist>
""")
    print(f"[build] macOS LaunchAgent plist written.")


def build_homebrew_formula():
    """Update Homebrew tap formula."""
    print("[build] Generating Homebrew formula...")
    formula = DIST / "openclaw.rb"
    formula.write_text(f"""cask "openclaw" do
  version "{VERSION}"
  url "https://github.com/openclaw/openclaw/releases/download/v{VERSION}/openclaw-macos.pkg"
  name "OpenClaw"
  desc "Local AI assistant with self-learning expert modules"
  homepage "https://openclaw.io"
  app "OpenClaw.app"
end
""")
    print(f"[build] Homebrew formula written: {formula}")


if __name__ == "__main__":
    clean()
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    builders = {
        "binary":    build_binary,
        "deb":       build_deb,
        "rpm":       build_rpm_spec,
        "arch":      build_pkgbuild,
        "windows":   build_nsis,
        "macos":     build_macos_pkg,
        "homebrew":  build_homebrew_formula,
    }

    if target == "all":
        for name, fn in builders.items():
            try:
                fn()
            except Exception as e:
                print(f"[build] {name} failed: {e}")
    elif target in builders:
        builders[target]()
    else:
        print(f"Unknown target: {target}. Available: {list(builders.keys())}")
