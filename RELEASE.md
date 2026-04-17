# 🚀 Release Guide — OpenClaw Brain

This document describes how to build and release OpenClaw Brain to multiple platforms and package repositories.

## Version 2.0.0 Release

**Release Platforms:**
- 🐧 **Linux** (x86_64): Standalone executable + source tarball
- 🪟 **Windows** (x86_64): Standalone executable + wheel
- 🍎 **macOS** (universal2 M1/M2): Standalone executable + wheel
- 📦 **PyPI**: Python package for `pip install openclaw-brain`

---

## Quick Start: One-Command Release

```bash
bash build/release.sh
```

This will:
1. Create a git tag (v2.0.0)
2. Push the tag to GitHub
3. Trigger GitHub Actions workflows
4. Build on all three platforms simultaneously
5. Create GitHub Release with artifacts
6. Publish to PyPI automatically

---

## Manual Build Process

### 1. Build locally (all platforms)

```bash
bash build/build.sh
```

Produces in `dist/`:
- `openclaw-brain-2.0.0-linux-x86_64.tar.gz`
- `openclaw-brain-2.0.0-windows-x86_64.zip`
- `openclaw-brain-2.0.0-macos-universal2.zip`
- `openclaw_brain-2.0.0-py3-none-any.whl` (wheel)
- `openclaw-brain-2.0.0.tar.gz` (sdist)

### 2. Create GitHub Release manually

```bash
gh release create v2.0.0 \
  --title "OpenClaw Brain 2.0.0" \
  --notes "Release notes here" \
  dist/*
```

### 3. Publish to PyPI manually

```bash
python -m twine upload dist/openclaw_brain-2.0.0*
```

---

## Platform-Specific Details

### Linux
- Built on `ubuntu-latest` (GitHub-hosted runner)
- Architecture: x86_64
- Output: Standalone executable + wheel
- Command: `./openclaw-brain`

### Windows
- Built on `windows-latest`
- Architecture: x86_64
- Output: Standalone executable (.exe) + wheel
- Command: `openclaw-brain.exe`

### macOS
- Built on `macos-latest`
- Architecture: universal2 (handles both Intel and M1/M2)
- Output: Standalone executable + wheel
- Command: `./openclaw-brain`

---

## Artifacts Generated

### Per-Platform
```
dist/
├── openclaw-brain-2.0.0-linux-x86_64.tar.gz
├── openclaw-brain-2.0.0-windows-x86_64.zip
├── openclaw-brain-2.0.0-macos-universal2.zip
```

### Universal (Python)
```
dist/
├── openclaw_brain-2.0.0-py3-none-any.whl
├── openclaw-brain-2.0.0.tar.gz
```

### Wheel (platform-specific)
```
dist/
├── openclaw_brain-2.0.0-cp311-cp311-linux_x86_64.whl
├── openclaw_brain-2.0.0-cp311-cp311-win_amd64.whl
├── openclaw_brain-2.0.0-cp311-cp311-macosx_11_0_universal2.whl
```

---

## GitHub Actions Workflow

The `.github/workflows/release.yml` workflow:

1. **Triggers on**: `git push` with tag matching `v*`
2. **Matrix build**: Runs on Linux, Windows, and macOS simultaneously
3. **Steps per platform**:
   - Set up Python 3.11
   - Install dependencies (including training & voice extras)
   - Build with PyInstaller
   - Create executables
   - Upload artifacts
4. **PyPI publish** job (runs after all builds):
   - Builds source distribution
   - Publishes to PyPI with `${{ secrets.PYPI_API_TOKEN }}`

---

## Prerequisites for Automated Release

### 1. GitHub Repository Secrets

Add these secrets to your GitHub repository settings:

**`PYPI_API_TOKEN`**
- Get from: https://pypi.org/manage/account/tokens/
- Scope: "Entire account"
- Store in: Repo Settings → Secrets and variables → Actions → New repository secret

### 2. Git Configuration

Ensure your local git is configured:
```bash
git config --global user.email "you@example.com"
git config --global user.name "Your Name"
```

### 3. GitHub CLI (for manual release creation)

```bash
brew install gh  # macOS
sudo apt install gh  # Linux
choco install gh  # Windows
gh auth login
```

---

## Updating Version

To create a new release version:

1. Update `version.txt`:
```bash
echo "2.1.0" > version.txt
```

2. Update `pyproject.toml`:
```bash
# Change: version = "2.0.0" → version = "2.1.0"
```

3. Commit and tag:
```bash
git add version.txt pyproject.toml
git commit -m "Release 2.1.0"
bash build/release.sh
```

---

## Troubleshooting

### Release workflow stuck
- Check GitHub Actions: https://github.com/1h0lde4/OpenClaw-Brain/actions
- View logs for specific platform failures
- Rebuild with: `git tag -d v2.0.0 && git push origin :v2.0.0 && bash build/release.sh`

### PyPI upload fails
- Verify `PYPI_API_TOKEN` secret exists and is valid
- Check PyPI account hasn't reached project limits
- Try: `twine upload dist/* --verbose`

### Standalone executable won't run
- Missing dependencies: Check hidden imports in `build/openclaw.spec`
- Platform mismatch: Ensure you're running the correct platform executable
- Permissions: `chmod +x openclaw-brain` on Linux/macOS

### Wheel installation fails
- Verify Python 3.11+ installed
- Try: `pip install -e . --no-binary :all:`

---

## Release Channels

### GitHub Releases
- Automatically created by workflow
- URL: https://github.com/1h0lde4/OpenClaw-Brain/releases

### PyPI Package
- Installable via: `pip install openclaw-brain`
- Repository: https://pypi.org/project/openclaw-brain/

### Standalone Executables
- Download from GitHub Releases
- No Python installation required
- OS-specific binaries

---

## Checklist Before Releasing

- [ ] All tests passing: `pytest tests/`
- [ ] All code changes committed: `git status`
- [ ] Version numbers updated consistently
- [ ] CHANGELOG.md updated with release notes
- [ ] GitHub Actions workflow checked: `.github/workflows/release.yml`
- [ ] `PYPI_API_TOKEN` secret configured
- [ ] Build scripts are executable: `chmod +x build/*.sh`

---

## Support & Issues

- 📋 Bug reports: https://github.com/1h0lde4/OpenClaw-Brain/issues
- 💬 Discussions: https://github.com/1h0lde4/OpenClaw-Brain/discussions
- 📦 Package issues: https://pypi.org/project/openclaw-brain/
