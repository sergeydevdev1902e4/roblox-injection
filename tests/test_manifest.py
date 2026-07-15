import json
import pytest
from pathlib import Path
from roblox_injection.manifest import (
    load_manifest,
    ManifestError,
    InjectionTarget,
)


def test_load_valid_manifest(tmp_path: Path):
    dummy_script = tmp_path / "entry.luau"
    dummy_script.write_text("print('injected')", encoding="utf-8")

    manifest_file = tmp_path / "manifest.json"
    data = {
        "version": 1,
        "entries": [
            {
                "target": "ServerScriptService/Core/Init",
                "file": str(dummy_script.relative_to(tmp_path)),
                "class_name": "Script",
            }
        ],
    }
    manifest_file.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_manifest(manifest_file)
    assert len(manifest.entries) == 1
    entry = manifest.entries[0]
    assert entry.target_path == ["ServerScriptService", "Core", "Init"]
    assert entry.source_file == dummy_script.resolve()
    assert entry.class_name == "Script"


def test_missing_manifest_file(tmp_path: Path):
    with pytest.raises(ManifestError, match="Manifest not found"):
        load_manifest(tmp_path / "non_existent.json")


def test_manifest_missing_source_file(tmp_path: Path):
    manifest_file = tmp_path / "manifest.json"
    data = {
        "entries": [
            {
                "target": "ReplicatedStorage/Config",
                "file": "missing.luau",
            }
        ]
    }
    manifest_file.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestError, match="Referenced file does not exist"):
        load_manifest(manifest_file)


def test_inline_payload_manifest(tmp_path: Path):
    manifest_file = tmp_path / "inline.json"
    data = {
        "entries": [
            {
                "target": "ReplicatedStorage/VersionInfo",
                "content": "return { build = 42, branch = 'main' }",
                "class_name": "ModuleScript",
            }
        ]
    }
    manifest_file.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_manifest(manifest_file)
    assert len(manifest.entries) == 1
    entry = manifest.entries[0]
    assert entry.content == "return { build = 42, branch = 'main' }"
    assert entry.source_file is None


def test_path_sanitization(tmp_path: Path):
    manifest_file = tmp_path / "slashes.json"
    data = {
        "entries": [
            {
                "target": "/Workspace//Folder/SubFolder/Script/",
                "content": "-- ok",
            }
        ]
    }
    manifest_file.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_manifest(manifest_file)
    assert manifest.entries[0].target_path == ["Workspace", "Folder", "SubFolder", "Script"]


def test_manifest_validation_failures(tmp_path: Path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{", encoding="utf-8")
    with pytest.raises(ManifestError, match="Invalid JSON"):
        load_manifest(bad_json)

    empty_target = tmp_path / "empty.json"
    empty_target.write_text(json.dumps({"entries": [{"target": "///"}]}), encoding="utf-8")
    with pytest.raises(ManifestError, match="Empty target path"):
        load_manifest(empty_target)
