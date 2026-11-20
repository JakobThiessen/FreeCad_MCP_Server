"""Command line entry point: ``freecad-mcp`` (stdio server) plus install-addon, doctor and print-config.

Without arguments (or with ``serve``) the stdio MCP server starts exactly as before. The other
sub-commands never import the server module, so they stay fast and need no FreeCAD connection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ADDON_DIR_NAME = "FreecadAIBridge"
BRIDGE_PACKAGE = "freecad_ai_bridge"


def package_version() -> str:
    try:
        return version("freecad-mcp-server")
    except PackageNotFoundError:
        return "unknown"


def addon_source() -> Path:
    """Addon payload: bundled in the wheel (freecad_mcp/_addon) or the repo's freecad_addon (editable/source)."""
    here = Path(__file__).resolve().parent
    for candidate in (here / "_addon", here.parent.parent / "freecad_addon"):
        if (candidate / BRIDGE_PACKAGE / "__init__.py").is_file():
            return candidate
    raise FileNotFoundError("FreeCAD addon payload not found (neither bundled nor repository freecad_addon)")


def bridge_hash(addon_root: Path) -> dict:
    """Identical to freecad_ai_bridge.operations._bridge_install_identity: SHA-256 over sorted *.py names and bytes."""
    root = addon_root / BRIDGE_PACKAGE
    digest = hashlib.sha256()
    files = sorted(root.glob("*.py"))
    for path in files:
        digest.update(path.name.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return {"package_path": str(root), "file_count": len(files), "sha256": digest.hexdigest()}


def bridge_api_version(addon_root: Path) -> str | None:
    text = (addon_root / BRIDGE_PACKAGE / "contracts.py").read_text(encoding="utf-8")
    match = re.search(r'^BRIDGE_API_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def default_mod_dir() -> Path | None:
    """FreeCAD 1.1 user Mod folder. Only Windows is verified; elsewhere --target is required."""
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "FreeCAD" / "v1-1" / "Mod"
    return None


def resolve_addon_target(target: str | None) -> Path:
    """--target is the Mod folder (the addon goes to <target>/FreecadAIBridge) or the addon folder itself."""
    if target:
        path = Path(target).expanduser()
        return path if path.name == ADDON_DIR_NAME else path / ADDON_DIR_NAME
    mod = default_mod_dir()
    if mod is None:
        raise SystemExit("No verified default FreeCAD Mod folder on this platform; pass --target <Mod folder>.")
    return mod / ADDON_DIR_NAME


def freecad_running() -> list[str]:
    """Names of running FreeCAD processes (best effort; empty list if undetectable)."""
    try:
        if sys.platform == "win32":
            out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=20).stdout
            names = {line.split('","')[0].strip('"') for line in out.splitlines() if line}
        else:
            out = subprocess.run(["ps", "-A", "-o", "comm="], capture_output=True, text=True, timeout=20).stdout
            names = {line.strip() for line in out.splitlines()}
    except (OSError, subprocess.SubprocessError):
        return []
    return sorted(n for n in names if n.lower() in {"freecad.exe", "freecad", "freecad-bin", "freecad.bin"})


def _ignore(_dir, names):
    return [n for n in names if n == "__pycache__" or n.endswith((".pyc", ".pyo"))]


def install_addon(target: str | None, dry_run: bool, force: bool) -> dict:
    src = addon_source()
    dest = resolve_addon_target(target)
    src_id = bridge_hash(src)
    report = {"source": str(src), "target": str(dest), "source_sha256": src_id["sha256"],
              "source_file_count": src_id["file_count"], "bridge_api_version": bridge_api_version(src),
              "package_version": package_version(), "warnings": [], "dry_run": dry_run}
    running = freecad_running()
    if running:
        report["warnings"].append(
            f"FreeCAD appears to be running ({', '.join(running)}); close it before updating and restart it afterwards, "
            "otherwise the old addon stays loaded.")
    existing = dest.exists()
    old_id = None
    if existing:
        if (dest / BRIDGE_PACKAGE / "__init__.py").is_file():
            old_id = bridge_hash(dest)
            report["previous_sha256"] = old_id["sha256"]
            report["previous_bridge_api_version"] = bridge_api_version(dest)
        elif not force:
            raise SystemExit(f"{dest} exists but is not a FreeCAD AI Bridge addon; refusing to replace it (use --force).")
    if old_id and old_id["sha256"] == src_id["sha256"] and not force:
        report["action"] = "up_to_date"
        return report
    report["action"] = ("would_replace" if existing else "would_install") if dry_run else ("replaced" if existing else "installed")
    if dry_run:
        return report

    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.parent / (ADDON_DIR_NAME + ".new")
    backup = dest.parent / (ADDON_DIR_NAME + ".old")
    for leftover in (staging, backup):
        if leftover.exists():
            shutil.rmtree(leftover)
    shutil.copytree(src, staging, ignore=_ignore)
    if bridge_hash(staging)["sha256"] != src_id["sha256"]:
        shutil.rmtree(staging)
        raise SystemExit("Copy verification failed (hash mismatch); target not modified.")
    try:
        if existing:
            dest.rename(backup)
        staging.rename(dest)
    except OSError as error:
        if backup.exists() and not dest.exists():
            backup.rename(dest)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise SystemExit(f"Install failed, previous addon restored where possible: {error}")
    shutil.rmtree(backup, ignore_errors=True)
    final = bridge_hash(dest)["sha256"]
    report["installed_sha256"] = final
    report["verified"] = final == src_id["sha256"]
    return report


def doctor(target: str | None, host: str, port: int) -> tuple[dict, int]:
    checks: list[dict] = []
    code = 0

    def add(name: str, status: str, detail: str, **extra):
        nonlocal code
        checks.append({"check": name, "status": status, "detail": detail, **extra})
        if status == "error":
            code = 1

    add("package", "ok", f"freecad-mcp-server {package_version()}")
    try:
        from importlib.metadata import version as _v
        add("mcp_sdk", "ok", f"mcp {_v('mcp')}")
    except PackageNotFoundError:
        add("mcp_sdk", "error", "mcp SDK not installed")
    expected = None
    try:
        text = (Path(__file__).resolve().parent / "server.py").read_text(encoding="utf-8")
        found = re.search(r'^EXPECTED_BRIDGE_API_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
        expected = found.group(1) if found else None
    except OSError:
        pass
    add("expected_bridge_api", "ok" if expected else "error", str(expected))
    src_hash = None
    try:
        src = addon_source()
        src_hash = bridge_hash(src)["sha256"]
        api = bridge_api_version(src)
        add("packaged_addon", "ok" if api == expected else "error",
            f"bridge API {api}, sha256 {src_hash[:16]}", sha256=src_hash)
    except (OSError, FileNotFoundError) as error:
        add("packaged_addon", "error", str(error))

    try:
        dest = resolve_addon_target(target)
    except SystemExit as error:
        dest = None
        add("installed_addon", "warning", str(error))
    if dest is not None:
        if (dest / BRIDGE_PACKAGE / "__init__.py").is_file():
            inst = bridge_hash(dest)["sha256"]
            same = inst == src_hash
            add("installed_addon", "ok" if same else "error",
                f"{dest}: sha256 {inst[:16]} ({'matches packaged addon' if same else 'differs; run: freecad-mcp install-addon'})",
                sha256=inst)
        else:
            add("installed_addon", "error", f"not installed at {dest}; run: freecad-mcp install-addon")

    running = freecad_running()
    add("freecad_process", "ok" if running else "warning",
        "running: " + ", ".join(running) if running else "no FreeCAD process detected (start FreeCAD with the addon to test the bridge)")

    from freecad_mcp.connection import FreeCADConnection
    conn = FreeCADConnection(host=host, port=port, timeout=10)
    if not conn.connect():
        add("bridge", "warning", f"no bridge reachable at {conn.url}")
    else:
        try:
            caps = conn.call_function("freecad_ai_bridge.operations", "get_capabilities")
            api = caps.get("bridge_api_version")
            add("bridge", "ok" if api == expected else "error",
                f"{conn.url}: bridge API {api} (host expects {expected})")
            add("freecad_version", "ok", ".".join(str(p) for p in caps.get("freecad_version", [])[:4]))
            loaded = caps.get("bridge_install", {}).get("sha256")
            add("loaded_addon", "ok" if loaded == src_hash else "error",
                f"loaded sha256 {str(loaded)[:16]} at {caps.get('bridge_install', {}).get('package_path')}"
                + ("" if loaded == src_hash else " differs from packaged addon; update and restart FreeCAD"))
            raw = caps.get("features", {}).get("raw_python_enabled")
            add("raw_python", "ok" if not raw else "warning", f"raw_python_enabled={raw}")
        except Exception as error:  # noqa: BLE001 - report any bridge failure
            add("bridge", "error", f"{conn.url}: {type(error).__name__}: {error}")
    return {"ok": code == 0, "checks": checks}, code


def _own_executable() -> str:
    """The freecad-mcp launcher next to the running interpreter (the environment that holds this package)."""
    scripts = Path(sys.executable).resolve().parent
    for folder in (scripts, scripts / "Scripts", scripts / "bin"):
        for name in ("freecad-mcp.exe", "freecad-mcp"):
            if (folder / name).is_file():
                return str(folder / name)
    return ""


def print_config(uvx: bool, command: str | None) -> dict:
    if uvx:
        entry = {"command": "uvx", "args": ["--from", "freecad-mcp-server", "freecad-mcp"]}
    else:
        exe = command or _own_executable() or shutil.which("freecad-mcp") or ""
        if exe:
            entry = {"command": exe, "args": []}
        else:
            entry = {"command": sys.executable, "args": ["-m", "freecad_mcp.server"]}
    return {"mcpServers": {"freecad": entry}}


def serve() -> None:
    from freecad_mcp.server import main as server_main
    server_main()


def main(argv: list[str] | None = None) -> int:
    args_in = sys.argv[1:] if argv is None else argv
    if not args_in:
        serve()
        return 0
    parser = argparse.ArgumentParser(prog="freecad-mcp", description="FreeCAD MCP server and helper commands.")
    parser.add_argument("--version", action="version", version=f"freecad-mcp-server {package_version()}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the stdio MCP server (default without arguments)")
    p_inst = sub.add_parser("install-addon", help="copy the bundled FreeCAD addon into the FreeCAD Mod folder")
    p_inst.add_argument("--target", help="FreeCAD Mod folder (default: %%APPDATA%%\\FreeCAD\\v1-1\\Mod on Windows)")
    p_inst.add_argument("--dry-run", action="store_true", help="report what would happen, change nothing")
    p_inst.add_argument("--force", action="store_true", help="reinstall even if identical or replace a foreign folder")
    p_doc = sub.add_parser("doctor", help="check addon, versions and bridge connection")
    p_doc.add_argument("--target", help="FreeCAD Mod folder to inspect")
    p_doc.add_argument("--host", default="127.0.0.1")
    p_doc.add_argument("--port", type=int, default=9875)
    p_doc.add_argument("--json", action="store_true", help="machine-readable output")
    p_cfg = sub.add_parser("print-config", help="print an mcpServers entry for claude_desktop_config.json")
    p_cfg.add_argument("--uvx", action="store_true", help="use uvx instead of the installed executable")
    p_cfg.add_argument("--exe", help="explicit executable path")
    args = parser.parse_args(args_in)

    if args.command == "serve":
        serve()
        return 0
    if args.command == "install-addon":
        report = install_addon(args.target, args.dry_run, args.force)
        print(json.dumps(report, indent=2))
        for warning in report["warnings"]:
            print("WARNING: " + warning, file=sys.stderr)
        return 0
    if args.command == "doctor":
        result, code = doctor(args.target, args.host, args.port)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for item in result["checks"]:
                print(f"[{item['status'].upper():7}] {item['check']}: {item['detail']}")
        return code
    if args.command == "print-config":
        print(json.dumps(print_config(args.uvx, args.exe), indent=2))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
