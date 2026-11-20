"""Stage 12c: isolated install/update cycle and operating behaviour over the real MCP transport.

Everything happens below one new TEMP directory: wheels, installed host packages, addon copies,
FreeCAD user/system configs and test documents. Only GUI processes started here are ever
terminated (by their own PID). The user's FreeCAD profile and regular Mod folder are read only
(hash before/after) and never written. Raw Python stays disabled.

Usage (host venv, Windows paths):
    .venv\\Scripts\\python.exe -B tests\\stage12c_operations.py [--phase all|install|loss|timeout]

The old addon/host pair is exported with `git archive` from FREECAD_12C_OLD_REF (default 730aa0f,
bridge API 0.10.0); the new pair is the current working tree.
"""

import argparse
import asyncio
import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import xmlrpc.client
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from socketserver import ThreadingMixIn
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
FREECAD = Path(os.environ.get("FREECAD_TEST_EXE", r"C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe"))
OLD_REF = os.environ.get("FREECAD_12C_OLD_REF", "730aa0f")
OLD_BRIDGE = "0.10.0"
NEW_BRIDGE = "0.11.0"
USER_MOD = Path(os.environ.get("APPDATA", "")) / "FreeCAD" / "v1-1" / "Mod" / "FreecadAIBridge"


# --------------------------------------------------------------------------- build / install

def tree_hash(directory):
    """SHA-256 over sorted relative *.py names and bytes, identical to operations._bridge_install_identity."""
    digest = hashlib.sha256()
    for path in sorted(Path(directory).glob("*.py")):
        digest.update(path.name.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def user_mod_fingerprint():
    if not USER_MOD.is_dir():
        return None
    return {str(p.relative_to(USER_MOD)): sha256_file(p) for p in sorted(USER_MOD.rglob("*")) if p.is_file()}


def export_old_tree(destination):
    archive = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", OLD_REF, "src", "freecad_addon", "pyproject.toml"],
                             capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(destination, filter="data") if sys.version_info >= (3, 12) else tar.extractall(destination)


def export_current_tree(destination):
    destination.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(ROOT / "src", destination / "src", ignore=ignore)
    shutil.copytree(ROOT / "freecad_addon", destination / "freecad_addon", ignore=ignore)
    shutil.copy2(ROOT / "pyproject.toml", destination / "pyproject.toml")


def run(command, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{command} failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
    return result


class Pair:
    """An installed host package (pip --target) plus an addon copy in a private Mod folder."""

    def __init__(self, name, tree, base):
        self.name = name
        self.tree = tree
        self.wheel_dir = base / "wheels"
        self.host = base / "host"
        self.mod = base / "mod"
        self.addon = self.mod / "FreecadAIBridge"
        self.wheel = None

    def build_wheel(self):
        self.wheel_dir.mkdir(parents=True, exist_ok=True)
        run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-cache-dir", "--wheel-dir", str(self.wheel_dir), str(self.tree)])
        wheels = sorted(self.wheel_dir.glob("freecad_mcp_server-*.whl"))
        assert wheels, list(self.wheel_dir.iterdir())
        self.wheel = wheels[-1]
        with zipfile.ZipFile(self.wheel) as archive:
            names = archive.namelist()
        assert any(name.endswith("freecad_mcp/server.py") for name in names), names
        # Since 1.1.0 the wheel also carries the addon payload, but only as data below freecad_mcp/_addon (never importable as top-level freecad_ai_bridge).
        assert not any(name.startswith("freecad_ai_bridge/") for name in names), "no top-level freecad_ai_bridge package in the wheel"
        if "force-include" in (self.tree / "pyproject.toml").read_text(encoding="utf-8"):  # older trees (OLD_REF) predate bundling
            assert any(name.endswith("freecad_mcp/_addon/freecad_ai_bridge/operations.py") for name in names), "wheel must bundle the addon payload"
        assert not any("__pycache__" in name for name in names), "no bytecode in the wheel"
        return {"wheel": self.wheel.name, "bytes": self.wheel.stat().st_size, "sha256": sha256_file(self.wheel)}

    def install_host(self):
        run([sys.executable, "-m", "pip", "install", "--no-deps", "--no-compile", "--upgrade", "--target", str(self.host), str(self.wheel)])
        server = self.host / "freecad_mcp" / "server.py"
        assert server.is_file() and sha256_file(server) == sha256_file(self.tree / "src" / "freecad_mcp" / "server.py")
        return str(server)

    def install_addon(self):
        """Replace the addon folder as documented for an update: remove the old copy, copy the new one."""
        self.mod.mkdir(parents=True, exist_ok=True)
        if self.addon.exists():
            shutil.rmtree(self.addon)
        shutil.copytree(self.tree / "freecad_addon", self.addon, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        assert tree_hash(self.addon / "freecad_ai_bridge") == tree_hash(self.tree / "freecad_addon" / "freecad_ai_bridge")
        return tree_hash(self.addon / "freecad_ai_bridge")


# --------------------------------------------------------------------------- GUI process

def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def rpc_ping(port, timeout=2.0):
    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        return xmlrpc.client.ServerProxy(f"http://127.0.0.1:{port}/RPC2").ping() == "pong"
    except Exception:
        return False
    finally:
        socket.setdefaulttimeout(previous)


def user_cfg(port, autostart):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<FCParameters><FCParamGroup Name="Root">'
            '<FCParamGroup Name="BaseApp"><FCParamGroup Name="Preferences"><FCParamGroup Name="Mod">'
            '<FCParamGroup Name="FreecadAIBridge">'
            f'<FCInt Name="Port" Value="{port}"/><FCBool Name="AutoStart" Value="{1 if autostart else 0}"/>'
            '</FCParamGroup></FCParamGroup></FCParamGroup></FCParamGroup></FCParamGroup></FCParameters>\n')


GUIS = []


class Gui:
    """One own FreeCAD GUI process loading the addon natively (InitGui autostart, no macro)."""

    def __init__(self, label, pair, port, base, autostart=True):
        self.label = label
        self.pair = pair
        self.port = port
        self.base = base
        self.autostart = autostart
        self.process = None
        self.starts = 0

    def start(self):
        self.starts += 1
        if self not in GUIS:
            GUIS.append(self)
        config = self.base / f"{self.label}-{self.starts}"
        config.mkdir(parents=True)
        (config / "user.cfg").write_text(user_cfg(self.port, self.autostart), encoding="utf-8")
        environment = dict(os.environ, FREECAD_MCP_ALLOW_RAW_PYTHON="0")
        environment.pop("FREECAD_TEST_PORT", None)
        self.log = (config / "freecad.log").open("wb")
        self.process = subprocess.Popen(
            [str(FREECAD), "-u", str(config / "user.cfg"), "-s", str(config / "system.cfg"), "-M", str(self.pair.addon)],
            cwd=str(config), env=environment, stdout=self.log, stderr=subprocess.STDOUT)
        return self.process.pid

    def wait_ready(self, timeout=150):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"{self.label}: FreeCAD exited with {self.process.returncode}")
            if rpc_ping(self.port):
                return
            time.sleep(0.5)
        raise TimeoutError(f"{self.label}: bridge on port {self.port} did not answer")

    def alive(self):
        return self.process is not None and self.process.poll() is None

    def kill(self):
        """Hard process loss of exactly this GUI (own PID only)."""
        if self.alive():
            self.process.kill()
            self.process.wait(30)
        if not self.log.closed:
            self.log.close()


# --------------------------------------------------------------------------- MCP client

class Mcp:
    def __init__(self, session):
        self.session = session

    async def call(self, tool, /, **arguments):
        return await self.session.call_tool(tool, arguments)

    async def ok(self, tool, /, **arguments):
        response = await self.call(tool, **arguments)
        assert not response.is_error, f"{tool}: {response.content}"
        return response

    async def data(self, tool, /, **arguments):
        response = await self.ok(tool, **arguments)
        payload = response.structured_content
        assert payload["status"] == "success", (tool, payload)
        return payload["data"], payload

    async def text(self, tool, /, **arguments):
        return (await self.ok(tool, **arguments)).content[0].text

    async def failure(self, tool, /, **arguments):
        """Structured contract error (status=error) without a protocol-level isError."""
        response = await self.call(tool, **arguments)
        assert not response.is_error, f"{tool}: {response.content}"
        payload = response.structured_content
        assert payload["status"] == "error", (tool, payload)
        return payload["error"]


@asynccontextmanager
async def mcp_session(host_dir, **extra_environment):
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"FREECAD_MCP_TIMEOUT_SECONDS", "FREECAD_TEST_PORT"}}
    environment.update(PYTHONPATH=str(host_dir), PYTHONDONTWRITEBYTECODE="1", FREECAD_MCP_ALLOW_RAW_PYTHON="0")
    environment.update(extra_environment)
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "freecad_mcp.server"], env=environment)
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            yield Mcp(session)


def batch_boxes(document, count, prefix):
    return [{"id": f"{prefix}{index}", "operation": "part_box", "doc_name": document,
             "arguments": {"length": 10, "width": 10, "height": 10, "name": f"{prefix}{index}"}} for index in range(count)]


async def wait_job(mcp, job_id, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job, _ = await mcp.data("get_job", job_id=job_id)
        if job["status"] not in {"queued", "running"}:
            return job
        await asyncio.sleep(0.1)
    raise TimeoutError(job_id)


async def object_names(mcp, document):
    data, _ = await mcp.data("inspect_document", doc_name=document)
    return sorted(item["reference"]["object"] for item in data["objects"])


# --------------------------------------------------------------------------- phases

async def phase_install_update(context):
    """12c-I1..I6 and 12c-U1..U6: install, autoload, update, mixed state, rollback."""
    base, results = context["base"], {}
    old = Pair("old", context["old_tree"], base / "old-pair")
    new = Pair("new", context["new_tree"], base / "new-pair")
    results["wheel_old"], results["wheel_new"] = old.build_wheel(), new.build_wheel()
    assert results["wheel_old"]["sha256"] != results["wheel_new"]["sha256"]
    results["host_old_server"], results["host_new_server"] = old.install_host(), new.install_host()
    old_hash, new_hash = old.install_addon(), new.install_addon()
    assert old_hash != new_hash
    data_dir = base / "documents"
    data_dir.mkdir()
    port = free_port()
    assert not rpc_ping(port)

    # U1: old pair autoloads and produces a document saved by the old version.
    gui = Gui("old", old, port, base / "gui")
    gui.start()
    gui.wait_ready()
    old_file = data_dir / "old_version.FCStd"
    async with mcp_session(old.host) as mcp:
        assert "Connected" in await mcp.text("connect", port=port)
        caps, _ = await mcp.data("get_capabilities")
        assert caps["bridge_api_version"] == OLD_BRIDGE, caps  # the old pair predates normal mode (raw Python on)
        await mcp.text("create_document", name="OldDoc")
        await mcp.text("part_box", length=20, width=10, height=5, name="OldBox", doc_name="OldDoc")
        await mcp.text("save_document", name="OldDoc", path=str(old_file))
    assert old_file.is_file()
    results["old_pair"] = {"bridge_api_version": caps["bridge_api_version"], "raw_python_enabled": caps["features"]["raw_python_enabled"], "tools_file": str(old_file), "addon_sha256": old_hash}
    gui.kill()

    # U2: update in place (new addon replaces old copy, new host replaces old host), restart both sides.
    update = Pair("update", context["new_tree"], base / "old-pair")  # same install locations as the old pair
    update.wheel_dir, update.host, update.mod, update.addon = new.wheel_dir, old.host, old.mod, old.addon
    update.wheel = new.wheel
    update.install_host()
    assert update.install_addon() == new_hash
    gui = Gui("updated", update, port, base / "gui")
    gui.start()
    gui.wait_ready()
    async with mcp_session(update.host) as mcp:
        assert "Connected" in await mcp.text("connect", port=port)
        caps, payload = await mcp.data("get_capabilities")
        assert caps["bridge_api_version"] == NEW_BRIDGE and caps["compatibility"]["status"] == "match", caps
        assert payload["warnings"] == [], payload
        assert caps["bridge_install"]["sha256"] == new_hash, caps["bridge_install"]
        assert Path(caps["bridge_install"]["package_path"]).resolve() == (update.addon / "freecad_ai_bridge").resolve(), caps["bridge_install"]
        assert caps["mcp_server_version"] != "unknown"
        assert not caps["features"]["raw_python_enabled"]
        results["updated_pair"] = {"bridge_install": caps["bridge_install"], "compatibility": caps["compatibility"],
                                   "freecad_version": caps["freecad_version"]}
        # U3: document written by the old pair still opens, edits and recomputes in the updated pair.
        opened = json.loads(await mcp.text("open_document", path=str(old_file)))
        old_doc = opened["name"]
        measured = json.loads(await mcp.text("measure", obj_name="OldBox", doc_name=old_doc))
        assert abs(measured["volume"] - 1000.0) < 1e-6, measured
        await mcp.data("set_properties", doc_name=old_doc, obj_name="OldBox", values={"Height": {"value": 10, "unit": "mm"}})
        measured = json.loads(await mcp.text("measure", obj_name="OldBox", doc_name=old_doc))
        assert abs(measured["volume"] - 2000.0) < 1e-6, measured
        # a tool that only exists in the new pair works end to end
        await mcp.data("draft_create_element", doc_name=old_doc, spec={"kind": "rectangle", "length": 10, "width": 5}, name="UpdateRect")
        results["updated_pair"]["old_file_volume_after_edit"] = measured["volume"]
    shadow = USER_MOD.exists() and Path(caps["bridge_install"]["package_path"]).resolve() != (USER_MOD / "freecad_ai_bridge").resolve()
    assert shadow or not USER_MOD.exists(), "the user's regular Mod copy must not be the loaded one"
    gui.kill()

    # U4: mixed state, new host with the old addon: visible mismatch + structured error for a new-only tool.
    mixed = Pair("mixed", old.tree, base / "old-pair-copy")
    mixed.install_addon()
    gui = Gui("mixed", mixed, port, base / "gui")
    gui.start()
    gui.wait_ready()
    async with mcp_session(update.host) as mcp:
        assert "Connected" in await mcp.text("connect", port=port)
        caps, payload = await mcp.data("get_capabilities")
        assert caps["compatibility"]["status"] == "mismatch" and payload["warnings"], caps
        assert caps["bridge_api_version"] == OLD_BRIDGE
        start = time.monotonic()
        await mcp.text("create_document", name="MixedDoc")
        error = await mcp.failure("draft_inspect", doc_name="MixedDoc", obj_name="Nothing")
        assert time.monotonic() - start < 30 and error["code"] and error["message"], error
        results["mixed_pair"] = {"compatibility": caps["compatibility"], "warnings": payload["warnings"],
                                 "new_tool_on_old_addon": {"code": error["code"], "message": error["message"][:200]}}
    gui.kill()

    # U5: rollback to the old pair restores the old behaviour (hash and version).
    gui = Gui("rollback", mixed, port, base / "gui")
    gui.start()
    gui.wait_ready()
    async with mcp_session(old.host) as mcp:
        assert "Connected" in await mcp.text("connect", port=port)
        caps, _ = await mcp.data("get_capabilities")
        assert caps["bridge_api_version"] == OLD_BRIDGE, caps
    gui.kill()
    results["rollback"] = {"bridge_api_version": OLD_BRIDGE}

    # I3/I4: AutoStart off and an occupied port must not break FreeCAD or open a listener.
    off_port, busy_port = free_port(), free_port()
    off = Gui("autostart-off", update, off_port, base / "gui", autostart=False)
    busy = Gui("port-busy", update, busy_port, base / "gui")
    with socket.socket() as blocker:
        blocker.bind(("127.0.0.1", busy_port))
        blocker.listen(1)
        off.start()
        busy.start()
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            assert off.alive() and busy.alive(), "FreeCAD must survive disabled autostart and an occupied port"
            time.sleep(1)
        assert not rpc_ping(off_port), "AutoStart=false must not open the bridge port"
        assert not rpc_ping(busy_port, 1.0), "occupied port must stay occupied by the foreign listener"
    off.kill()
    busy.kill()
    results["autostart_negative"] = {"autostart_off_port_closed": True, "busy_port_gui_alive": True}
    context["new_pair"] = update
    context["old_pair"] = old
    return results


async def phase_loss(context):
    """12c-P1..P5: MCP restart, GUI start order, kill of the GUI process, job unknown after loss."""
    base, results = context["base"], {}
    pair = context["new_pair"]
    port = free_port()
    data_dir = base / "documents"
    data_dir.mkdir(exist_ok=True)
    gui = Gui("loss", pair, port, base / "gui")
    saved = data_dir / "saved_before_loss.FCStd"

    # P5: MCP started before any GUI exists -> clear connection failure, no hang; recovers after GUI start.
    async with mcp_session(pair.host) as mcp:
        start = time.monotonic()
        message = await mcp.text("connect", port=port)
        assert message.startswith("Failed to connect") and time.monotonic() - start < 20, message
        error = await mcp.failure("get_job", job_id="00000000-0000-4000-8000-000000000000")
        assert error["code"] == "transport_error", error
        status = await mcp.text("get_status")
        assert status.startswith("Not connected"), status
        gui.start()
        gui.wait_ready()
        assert "Connected" in await mcp.text("connect", port=port)
        results["start_order"] = {"connect_before_gui": message[:60], "transport_error": error["code"]}

        # Prepare: saved document, unsaved document, finished job.
        await mcp.text("create_document", name="Saved")
        await mcp.text("part_box", length=10, width=10, height=10, name="SavedBox", doc_name="Saved")
        await mcp.text("save_document", name="Saved", path=str(saved))
        await mcp.text("create_document", name="Unsaved")
        job, _ = await mcp.data("start_batch_job", steps=batch_boxes("Unsaved", 5, "U"), atomic=True, preview=False)
        done = await wait_job(mcp, job["job_id"])
        assert done["status"] == "succeeded", done
        finished_id = job["job_id"]
        before = await object_names(mcp, "Unsaved")
        assert len(before) == 5, before
        # a second job whose completion is racing the kill
        racing, _ = await mcp.data("start_batch_job", steps=batch_boxes("Unsaved", 100, "R"), atomic=True, preview=False)
        racing_id = racing["job_id"]

        # P3: hard loss of the GUI process mid-session.
        gui.kill()
        start = time.monotonic()
        error = await mcp.failure("get_job", job_id=finished_id)
        assert error["code"] == "transport_error" and time.monotonic() - start < 20, error
        failed = await mcp.call("create_document", name="AfterLoss")
        assert failed.is_error, "legacy tool must report the lost connection as an MCP error"
        status = await mcp.text("get_status")
        assert status.startswith("Not connected"), status
        error_start = await mcp.failure("start_batch_job", steps=batch_boxes("Unsaved", 1, "X"), atomic=True, preview=False)
        assert error_start["code"] == "transport_error", error_start
        tools = await mcp.session.list_tools()
        assert len(tools.tools) > 100  # MCP process itself survived
        results["gui_loss"] = {"get_job": error["code"], "start_job": error_start["code"], "legacy_is_error": True,
                               "mcp_process_alive": True}

        # P4: restart of the GUI on the same port; same MCP process reconnects; old IDs are explicitly unknown.
        gui.start()
        gui.wait_ready()
        assert "Connected" in await mcp.text("connect", port=port)
        for identifier in (finished_id, racing_id):
            lost, payload = await mcp.data("get_job", job_id=identifier)
            assert lost["status"] == "unknown" and lost["result"] is None and payload["warnings"], lost
        state = json.loads(await mcp.text("get_status"))
        assert state.get("documents") in ({}, [], None) or "Unsaved" not in json.dumps(state), state
        error = await mcp.failure("inspect_document", doc_name="Unsaved")
        assert error["code"] == "document_not_found", error
        results["after_restart"] = {"finished_job": "unknown", "racing_job": "unknown", "unsaved_document": error["code"]}
        # saved file is intact and editable; no replayed objects appeared anywhere
        opened = json.loads(await mcp.text("open_document", path=str(saved)))
        measured = json.loads(await mcp.text("measure", obj_name="SavedBox", doc_name=opened["name"]))
        assert abs(measured["volume"] - 1000.0) < 1e-6, measured
        assert await object_names(mcp, opened["name"]) == ["SavedBox"]
        results["saved_file_after_loss"] = {"volume": measured["volume"]}
        fresh, _ = await mcp.data("start_batch_job", steps=batch_boxes(opened["name"], 2, "N"), atomic=True, preview=False)
        assert (await wait_job(mcp, fresh["job_id"]))["status"] == "succeeded"
        assert await object_names(mcp, opened["name"]) == ["N0", "N1", "SavedBox"]
        # P1 (same GUI): end this MCP process, new MCP process reads the job; no duplicate mutation.
        keep_id = fresh["job_id"]
        document = opened["name"]
    async with mcp_session(pair.host) as mcp:
        assert "Connected" in await mcp.text("connect", port=port)
        first, _ = await mcp.data("get_job", job_id=keep_id)
        second, _ = await mcp.data("get_job", job_id=keep_id)
        assert first["status"] == second["status"] == "succeeded" and first["result"] == second["result"], (first, second)
        cancel, _ = await mcp.data("cancel_job", job_id=keep_id)
        assert cancel["cancellation"] == "already_finished", cancel
        assert await object_names(mcp, document) == ["N0", "N1", "SavedBox"]
    results["mcp_restart_same_gui"] = {"job_status": "succeeded", "duplicate_objects": 0, "cancel": "already_finished"}
    gui.kill()
    return results


class _Threaded(ThreadingMixIn, SimpleXMLRPCServer):
    daemon_threads = True


class FakeBridge:
    """Answers ping and get_version immediately but stalls job calls; counts every non-ping request."""

    def __init__(self, port, stall):
        self.stall = stall
        self.slow = True
        self.counts = {}
        self.lock = threading.Lock()
        outer = self

        class Handler(SimpleXMLRPCRequestHandler):
            rpc_paths = ("/RPC2",)

        self.server = _Threaded(("127.0.0.1", port), requestHandler=Handler, allow_none=True, logRequests=False)
        self.server.register_function(lambda: "pong", "ping")
        self.server.register_function(lambda: "1.1.4", "get_version")

        def counted(name):
            def handler(*args):
                with outer.lock:
                    outer.counts[name] = outer.counts.get(name, 0) + 1
                if outer.slow:
                    time.sleep(outer.stall)
                return json.dumps({"result": {"job_id": "fake", "status": "queued", "progress": None, "result": None,
                                              "error": None, "submitted_at": None, "warnings": []}})
            return handler

        for name in ("start_job", "get_job", "execute_function"):
            self.server.register_function(counted(name), name)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


async def phase_timeout(context):
    """12c-T1..T4: transport timeout through the real MCP process, no blind retry, recovery, invalid setting."""
    base, results = context["base"], {}
    pair = context["new_pair"]
    port = free_port()
    stall, limit = 4.0, 1.0
    bridge = FakeBridge(port, stall)
    try:
        async with mcp_session(pair.host, FREECAD_MCP_TIMEOUT_SECONDS=str(limit)) as mcp:
            assert "Connected" in await mcp.text("connect", port=port)
            start = time.monotonic()
            error = await mcp.failure("start_batch_job", steps=batch_boxes("Whatever", 1, "T"), atomic=True, preview=False)
            elapsed = time.monotonic() - start
            assert error["code"] == "transport_error" and limit <= elapsed < stall, (error, elapsed)
            await asyncio.sleep(stall + 1.0)  # a hidden retry would have arrived by now
            assert bridge.counts.get("start_job") == 1, bridge.counts
            start = time.monotonic()
            failed = await mcp.call("create_document", name="Slow")
            assert failed.is_error and time.monotonic() - start < stall, failed
            error_read = await mcp.failure("get_job", job_id="11111111-1111-4111-8111-111111111111")
            assert error_read["code"] == "transport_error"
            await asyncio.sleep(stall + 1.0)
            counts_after_failures = dict(bridge.counts)
            assert counts_after_failures.get("get_job") == 1 and counts_after_failures.get("start_job") == 1, counts_after_failures
            bridge.slow = False  # bridge answers again: same MCP process recovers without reconnecting
            job, _ = await mcp.data("get_job", job_id="11111111-1111-4111-8111-111111111111")
            assert job["status"] == "queued" and bridge.counts["get_job"] == 2, (job, bridge.counts)
            results["timeout"] = {"configured_seconds": limit, "elapsed_seconds": round(elapsed, 2), "code": error["code"],
                                  "bridge_start_job_requests": 1, "recovered_without_reconnect": True}
    finally:
        bridge.close()
    # T4: an invalid setting is rejected at MCP startup instead of silently using the default.
    for bad in ("abc", "0", "inf", "99999"):
        environment = dict(os.environ, PYTHONPATH=str(pair.host), PYTHONDONTWRITEBYTECODE="1", FREECAD_MCP_TIMEOUT_SECONDS=bad)
        result = subprocess.run([sys.executable, "-c", "import freecad_mcp.server"], env=environment, capture_output=True, text=True)
        assert result.returncode != 0 and "FREECAD_MCP_TIMEOUT_SECONDS" in result.stderr, (bad, result)
    results["invalid_timeout_rejected"] = True
    return results


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["all", "install", "loss", "timeout"], default="all",
                        help="install = install/autoload/update/mixed/rollback; loss = MCP restart and GUI process loss; timeout = transport timeout")
    arguments = parser.parse_args()
    assert FREECAD.is_file(), FREECAD
    base = Path(tempfile.mkdtemp(prefix="freecad-12c-"))
    old_tree = base / "old-tree"
    old_tree.mkdir()
    export_old_tree(old_tree)
    new_tree = base / "new-tree"
    export_current_tree(new_tree)
    fingerprint = user_mod_fingerprint()
    context = {"base": base, "old_tree": old_tree, "new_tree": new_tree}
    report = {"success": False, "base": str(base), "old_ref": OLD_REF, "python": sys.version, "freecad": str(FREECAD), "phases": {}}
    report_path = base / "report.json"
    try:
        if arguments.phase in {"all", "install"}:
            report["phases"]["install_update"] = await phase_install_update(context)
            print("PASS phase=install_update", flush=True)
        else:
            new = Pair("new", new_tree, base / "new-pair")
            report["phases"]["build"] = {"wheel": new.build_wheel(), "server": new.install_host(), "addon_sha256": new.install_addon()}
            context["new_pair"] = new
        if arguments.phase in {"all", "loss"}:
            report["phases"]["loss"] = await phase_loss(context)
            print("PASS phase=loss", flush=True)
        if arguments.phase in {"all", "timeout"}:
            report["phases"]["timeout"] = await phase_timeout(context)
            print("PASS phase=timeout", flush=True)
        assert user_mod_fingerprint() == fingerprint, "regular user Mod folder changed"
        report["user_mod_unchanged"] = True
        report["success"] = True
    finally:
        for gui in GUIS:
            gui.kill()
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"Stage12c report: {report_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
