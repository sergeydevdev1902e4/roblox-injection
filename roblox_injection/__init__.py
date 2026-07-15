"""CLI and library to patch Roblox place files during CI builds."""

from pathlib import Path
from typing import Union

from roblox_injection.manifest import load_manifest
from roblox_injection.xml_patcher import XmlPatcher

__version__ = "0.2.1"


def patch_place(place_path: Union[str, Path], manifest_path: Union[str, Path], output_path: Union[str, Path, None] = None, strict: bool = False) -> int:
    manifest = load_manifest(manifest_path)
    patcher = XmlPatcher(place_path)
    count = patcher.apply_all(manifest, strict=strict)
    
    dest = output_path or place_path
    patcher.save(dest)
    return count


__all__ = ["XmlPatcher", "load_manifest", "patch_place", "__version__"]
