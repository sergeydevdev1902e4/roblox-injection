from dataclasses import dataclass, field
import glob
import json
import os
from pathlib import Path
import re
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from typing import Any


@dataclass
class InjectionRule:
    target_path: str
    source_file: Path
    class_name: str = "ModuleScript"
    create_missing: bool = True
    env_vars: dict[str, str] = field(default_factory=dict)


class ManifestError(Exception):
    pass


_ENV_PATTERN = re.compile(r"\{\{\s*env\.([A-Za-z0-9_]+)\s*\}\}")


def resolve_source_content(rule: InjectionRule) -> str:
    if not rule.source_file.exists():
        raise FileNotFoundError(f"Source script not found: {rule.source_file}")

    raw_text = rule.source_file.read_text(encoding="utf-8")
    if not rule.env_vars and "{{" not in raw_text:
        return raw_text

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in rule.env_vars:
            return str(rule.env_vars[var_name])
        val = os.getenv(var_name)
        if val is not None:
            return val
        # leave placeholder intact if not provided
        return match.group(0)

    return _ENV_PATTERN.sub(_replace, raw_text)


def _parse_rule(raw: dict[str, Any], base_dir: Path) -> list[InjectionRule]:
    if "target" not in raw:
        raise ManifestError("Rule missing required 'target' field")
    if "file" not in raw:
        raise ManifestError(f"Rule for '{raw['target']}' missing 'file' path")

    file_pattern = raw["file"]
    target_str = raw["target"]
    cls_name = raw.get("class", "ModuleScript")
    create_missing = bool(raw.get("create_missing", True))
    env = raw.get("env", {})

    # Check if target is a glob wildcard matching multiple scripts into a folder
    if "*" in file_pattern:
        search_path = str(base_dir / file_pattern) if not Path(file_pattern).is_absolute() else file_pattern
        matches = glob.glob(search_path, recursive=True)
        if not matches:
            return []
        rules = []
        for match in sorted(matches):
            p = Path(match)
            # workspace.Common.* -> workspace.Common.<filename_without_ext>
            stem = p.stem.split(".")[0]
            actual_target = f"{target_str}.{stem}" if not target_str.endswith(".") else f"{target_str}{stem}"
            rules.append(
                InjectionRule(
                    target_path=actual_target,
                    source_file=p,
                    class_name=cls_name,
                    create_missing=create_missing,
                    env_vars=env,
                )
            )
        return rules

    src = Path(file_pattern)
    if not src.is_absolute():
        src = (base_dir / src).resolve()

    return [
        InjectionRule(
            target_path=target_str,
            source_file=src,
            class_name=cls_name,
            create_missing=create_missing,
            env_vars=env,
        )
    ]


def load_manifest(path: Path | str) -> list[InjectionRule]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Manifest file not found: {p}")

    content = p.read_text(encoding="utf-8")
    base_dir = p.parent

    if p.suffix in (".toml", ".tml"):
        data = tomllib.loads(content)
    elif p.suffix in (".json", ".rbxmanifest"):
        data = json.loads(content)
    else:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = tomllib.loads(content)

    entries = data.get("inject", data.get("rules", []))
    if not isinstance(entries, list):
        raise ManifestError("Manifest rules must be a list under 'inject' or 'rules'")

    result: list[InjectionRule] = []
    for item in entries:
        result.extend(_parse_rule(item, base_dir))
    return result
