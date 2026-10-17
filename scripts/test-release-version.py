#!/usr/bin/env python3
import importlib.util
import json
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("release_version", ROOT / "scripts/release-version.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseVersionTests(unittest.TestCase):
    def test_missing_version_starts_at_one(self):
        self.assertEqual(release.next_version("", []), "1.0.0")

    def test_current_version_increments_patch(self):
        self.assertEqual(release.next_version("0.1.62", []), "0.1.63")

    def test_highest_stable_version_wins(self):
        self.assertEqual(release.next_version("1.0.9", ["v1.0.10", "v2.0.0-beta", "other"]), "2.0.1")
        self.assertEqual(release.next_version("1.2.0-beta.1", []), "1.2.1")
        self.assertEqual(release.next_version("2.0.0", ["v1.9.99"]), "2.0.1")

    def test_sync_real_project_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = ["package.json", "package-lock.json", "Cargo.lock", "src-tauri/tauri.conf.json",
                     "src-tauri/Cargo.toml", "crates/wb-switch-core/Cargo.toml",
                     "crates/wb-switch-server/Cargo.toml", "npm/package.json"]
            files += [str(p.relative_to(ROOT)) for p in (ROOT / "npm/platform").glob("*/package.json")]
            for relative in files:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            release.sync_version(root, "1.2.3")
            names = set()
            for relative in files:
                path = root / relative
                if path.suffix == ".json":
                    data = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(data["version"], "1.2.3", relative)
                    if relative == "npm/package.json":
                        self.assertTrue(all(v == "1.2.3" for v in data["optionalDependencies"].values()))
                    if relative == "package-lock.json":
                        self.assertEqual(data["packages"][""]["version"], "1.2.3")
                elif path.suffix == ".toml":
                    data = tomllib.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(data["package"]["version"], "1.2.3")
                    names.add(data["package"]["name"])
            packages = tomllib.loads((root / "Cargo.lock").read_text(encoding="utf-8"))["package"]
            for package in packages:
                if package["name"] in names and "source" not in package:
                    self.assertEqual(package["version"], "1.2.3")
            self.assertEqual(len([p for p in packages if p["name"] in names and "source" not in p]), 3)


if __name__ == "__main__":
    unittest.main()
