# roblox-injection

I built this to swap Luau scripts and configuration tables directly into `.rbxlx` files inside GitHub Actions without spinning up Roblox Studio or Rojo when we only need quick build-time injections.

Right now XML place files (`.rbxlx`) are fully supported. Experimental binary parser (`.rbxl`) chunk inspection is in progress under `binary_chunk.py`.

## Installation

```bash
pip install .
```

Or in editable mode:

```bash
pip install -e ".[dev]"
```

## Manifest Format

Create a `manifest.yaml` specifying target paths and replacement source:

```yaml
injections:
  - target: "ServerScriptService/Core/GameConfig"
    type: "ModuleScript"
    source: "src/config/production.luau"
  - target: "ReplicatedStorage/Shared/Constants"
    type: "ModuleScript"
    raw: |
      return {
          BUILD_VERSION = "1.4.2",
          ENVIRONMENT = "ci"
      }
  - target: "ServerScriptService/Handlers/Analytics"
    type: "Script"
    properties:
      Disabled: false
```

## CLI Commands

Apply changes to a place file:

```bash
# Write to a separate target
rbxinject patch place.rbxlx -m manifest.yaml -o dist/place_prod.rbxlx

# Fail if a targeted path doesn't exist instead of creating it
rbxinject patch place.rbxlx -m manifest.yaml --strict

# Inspect changes before writing
rbxinject dry-run place.rbxlx -m manifest.yaml
```

## Tests

```bash
pytest
```

<!-- refreshed: 2026-09-08 -->
