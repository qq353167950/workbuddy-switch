#!/usr/bin/env python3
"""Choose and synchronise the next stable release version (stdlib only)."""
import json
import re
import subprocess
from pathlib import Path


def next_version(current, tags):
    versions = []
    for value in [current, *tags]:
        match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value or "")
        if match:
            versions.append(tuple(map(int, match.groups())))
    if not versions:
        return "1.0.0"
    major, minor, patch = max(versions)
    return f"{major}.{minor}.{patch + 1}"


def sync_version(root, version):
    paths = [root / "package.json", root / "src-tauri/tauri.conf.json",
             root / "npm/package.json", *sorted((root / "npm/platform").glob("*/package.json"))]
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["version"] = version
        if path == root / "npm/package.json":
            for name in data.get("optionalDependencies", {}):
                data["optionalDependencies"][name] = version
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    names = set()
    for relative in ["src-tauri/Cargo.toml", "crates/wb-switch-core/Cargo.toml",
                     "crates/wb-switch-server/Cargo.toml"]:
        import tomllib
        path = root / relative
        text = path.read_text(encoding="utf-8")
        names.add(tomllib.loads(text)["package"]["name"])
        text, count = re.subn(r'(?m)^version = "[^"]+"', f'version = "{version}"', text, count=1)
        if count != 1:
            raise ValueError(f"Missing package version: {relative}")
        path.write_text(text, encoding="utf-8")
    lock = root / "Cargo.lock"
    if lock.exists():
        blocks = lock.read_text(encoding="utf-8").split("[[package]]")
        for index, block in enumerate(blocks):
            match = re.search(r'(?m)^name = "([^"]+)"', block)
            if match and match[1] in names and '\nsource = ' not in block:
                blocks[index] = re.sub(r'(?m)^version = "[^"]+"', f'version = "{version}"', block, count=1)
        lock.write_text("[[package]]".join(blocks), encoding="utf-8")
    lock = root / "package-lock.json"
    if lock.exists():
        data = json.loads(lock.read_text(encoding="utf-8"))
        data["version"] = version
        if "" in data.get("packages", {}):
            data["packages"][""]["version"] = version
        lock.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    current = json.loads((root / "package.json").read_text(encoding="utf-8")).get("version", "")
    tags = subprocess.check_output(["git", "tag", "--list"], cwd=root, text=True).splitlines()
    version = next_version(current, tags)
    sync_version(root, version)
    print(version)
