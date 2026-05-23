#!/usr/bin/env python3
"""
Squelch version bump utility.
Usage:
  python bump_version.py patch    # 0.10.0 → 0.10.1
  python bump_version.py minor    # 0.10.1 → 0.11.0
  python bump_version.py major    # 0.11.0 → 1.0.0
  python bump_version.py release  # strip alpha/beta suffix

SemVer rules for Squelch:
  PATCH  — bug fixes, security, housekeeping (no new features)
  MINOR  — new features, backwards compatible (new tab, new API)
  MAJOR  — breaking changes or stable 1.0 release
"""
import sys, re
from pathlib import Path

def parse_version(v):
    m = re.match(r"(\d+)\.(\d+)\.(\d+)(-\w+)?", v)
    if not m:
        raise ValueError(f"Invalid version: {v}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4) or ""

def bump(current, part):
    major, minor, patch, suffix = parse_version(current)
    if part == "patch":
        return f"{major}.{minor}.{patch+1}{suffix}"
    elif part == "minor":
        return f"{major}.{minor+1}.0{suffix}"
    elif part == "major":
        return f"{major+1}.0.0{suffix}"
    elif part == "release":
        return f"{major}.{minor}.{patch}"
    raise ValueError(f"Unknown part: {part}")

def update_all(old, new):
    files_updated = []
    # constants.py — primary source
    c = Path("core/constants.py").read_text()
    if old in c:
        Path("core/constants.py").write_text(c.replace(old, new))
        files_updated.append("core/constants.py")
    # VERSION file
    Path("VERSION").write_text(new + "\n")
    files_updated.append("VERSION")
    # squelch.iss
    iss = Path("squelch.iss")
    if iss.exists():
        c = iss.read_text()
        if old in c:
            iss.write_text(c.replace(f'"{old}"', f'"{new}"'))
            files_updated.append("squelch.iss")
    # README badge
    readme = Path("README.md")
    if readme.exists():
        c = readme.read_text()
        old_num = re.sub(r'-\w+$', '', old)
        new_num = re.sub(r'-\w+$', '', new)
        c = re.sub(re.escape(old_num), new_num, c)
        readme.write_text(c)
        files_updated.append("README.md")
    return files_updated

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    part = sys.argv[1]
    current = Path("core/constants.py").read_text()
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', current)
    if not m:
        print("ERROR: APP_VERSION not found in core/constants.py")
        sys.exit(1)
    old_ver = m.group(1)
    new_ver = bump(old_ver, part)
    print(f"Bumping: {old_ver} → {new_ver}")
    updated = update_all(old_ver, new_ver)
    print(f"Updated: {', '.join(updated)}")
    print(f"\nNext steps:")
    print(f"  1. Add CHANGELOG.md entry for [{new_ver}]")
    print(f"  2. git commit -am 'chore: bump version to {new_ver}'")
    print(f"  3. git tag v{new_ver}")
