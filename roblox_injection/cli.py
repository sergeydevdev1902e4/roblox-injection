import os
from pathlib import Path
import shutil
import sys
import click
from roblox_injection.manifest import load_manifest, resolve_source_content, ManifestError
from roblox_injection.xml_patcher import RbxlxPatcher, RbxlxPatchError


@click.group()
@click.version_option(version="0.2.1")
def main():
    """Headless Luau and asset injection for Roblox place files."""
    pass


@main.command(name="patch")
@click.argument("place_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-m", "--manifest", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path), help="Path to injection rules (json/toml)")
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Output path. Overwrites place_file if omitted")
@click.option("--dry-run", is_flag=True, help="Simulate injection without writing to disk")
@click.option("--backup", is_flag=True, help="Create a .bak backup before overwriting place_file")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed injection logs")
def patch_cmd(place_file: Path, manifest: Path, output: Path | None, dry_run: bool, backup: bool, verbose: bool):
    if place_file.suffix.lower() == ".rbxl":
        # TODO(jack): binary .rbxl files need chunk recompression via binary_chunk.py once lz4 framing is sorted
        click.secho("Error: Binary .rbxl patching is currently experimental. Convert to .rbxlx or check back soon.", fg="red", err=True)
        sys.exit(2)

    try:
        rules = load_manifest(manifest)
    except (ManifestError, FileNotFoundError) as e:
        click.secho(f"Manifest error: {e}", fg="red", err=True)
        sys.exit(1)

    if not rules:
        click.secho("No injection rules found in manifest.", fg="yellow")
        return

    try:
        patcher = RbxlxPatcher(place_file)
    except (RbxlxPatchError, FileNotFoundError) as e:
        click.secho(f"Place parse error: {e}", fg="red", err=True)
        sys.exit(1)

    success_count = 0
    failed_count = 0

    for rule in rules:
        try:
            content = resolve_source_content(rule)
        except FileNotFoundError as e:
            click.secho(f"[SKIP] {e}", fg="yellow")
            failed_count += 1
            continue

        ok = patcher.patch_script(
            path_str=rule.target_path,
            source=content,
            class_name=rule.class_name,
            create_missing=rule.create_missing,
        )

        if ok:
            success_count += 1
            if verbose:
                click.echo(f"[OK] {rule.target_path} ({rule.class_name}) <- {rule.source_file.name}")
        else:
            failed_count += 1
            click.secho(f"[FAIL] Could not locate or create path: {rule.target_path}", fg="red", err=True)

    if dry_run:
        click.secho(f"Dry run complete. {success_count} succeeded, {failed_count} failed.", fg="cyan")
        return

    dest = output or place_file
    if backup and dest == place_file:
        bak_target = place_file.with_suffix(place_file.suffix + ".bak")
        shutil.copyfile(place_file, bak_target)
        if verbose:
            click.echo(f"Created backup at {bak_target}")

    patcher.save(dest)
    click.secho(f"Finished. Injected {success_count} script(s) into {dest}", fg="green")
    if failed_count > 0:
        sys.exit(1)


@main.command(name="inspect")
@click.argument("place_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("target_path", type=str)
def inspect_cmd(place_file: Path, target_path: str):
    try:
        patcher = RbxlxPatcher(place_file)
    except Exception as e:
        click.secho(f"Error opening place: {e}", fg="red", err=True)
        sys.exit(1)

    src = patcher.get_script_source(target_path)
    if src is None:
        click.secho(f"Node '{target_path}' not found or contains no source code.", fg="red", err=True)
        sys.exit(1)

    click.echo(src)
