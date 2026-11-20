"""Host tests for the freecad-mcp command line helpers (install-addon, doctor, print-config)."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from freecad_mcp import cli

REAL_FREECAD_RUNNING = cli.freecad_running


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(args))
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mod = Path(self.tmp.name) / "Mod"
        patcher = patch.object(cli, "freecad_running", return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_install_replace_and_hash(self):
        source = cli.bridge_hash(cli.addon_source())["sha256"]
        _, out, _ = run_cli("install-addon", "--target", str(self.mod), "--dry-run")
        self.assertEqual(json.loads(out)["action"], "would_install")
        self.assertFalse(self.mod.exists())
        _, out, _ = run_cli("install-addon", "--target", str(self.mod))
        report = json.loads(out)
        self.assertEqual(report["action"], "installed")
        self.assertTrue(report["verified"])
        dest = self.mod / cli.ADDON_DIR_NAME
        self.assertEqual(cli.bridge_hash(dest)["sha256"], source)
        self.assertTrue((dest / "Init.py").is_file() and (dest / "InitGui.py").is_file())
        self.assertFalse(list(dest.rglob("__pycache__")))
        self.assertEqual(json.loads(run_cli("install-addon", "--target", str(self.mod))[1])["action"], "up_to_date")
        # altered old copy is replaced and its previous hash reported
        (dest / "freecad_ai_bridge" / "security.py").write_text("# tampered\n", encoding="utf-8")
        report = json.loads(run_cli("install-addon", "--target", str(self.mod))[1])
        self.assertEqual(report["action"], "replaced")
        self.assertNotEqual(report["previous_sha256"], source)
        self.assertEqual(cli.bridge_hash(dest)["sha256"], source)
        self.assertEqual(sorted(p.name for p in self.mod.iterdir()), [cli.ADDON_DIR_NAME])
        self.assertEqual(json.loads(run_cli("install-addon", "--target", str(self.mod), "--force")[1])["action"], "replaced")

    def test_target_may_be_addon_folder_and_foreign_folder_refused(self):
        foreign = self.mod / cli.ADDON_DIR_NAME
        foreign.mkdir(parents=True)
        (foreign / "note.txt").write_text("mine", encoding="utf-8")
        with self.assertRaises(SystemExit):
            run_cli("install-addon", "--target", str(foreign))
        self.assertTrue((foreign / "note.txt").exists())
        run_cli("install-addon", "--target", str(foreign), "--force")
        self.assertTrue((foreign / "freecad_ai_bridge" / "__init__.py").is_file())

    def test_running_freecad_warns(self):
        with patch.object(cli, "freecad_running", return_value=["FreeCAD.exe"]):
            _, out, err = run_cli("install-addon", "--target", str(self.mod), "--dry-run")
        self.assertIn("running", err)
        self.assertTrue(json.loads(out)["warnings"])

    def test_bridge_api_matches_host_expectation(self):
        from freecad_mcp import server
        self.assertEqual(cli.bridge_api_version(cli.addon_source()), server.EXPECTED_BRIDGE_API_VERSION)

    def test_doctor_without_bridge(self):
        run_cli("install-addon", "--target", str(self.mod))
        code, out, _ = run_cli("doctor", "--target", str(self.mod), "--port", "9", "--json")
        self.assertEqual(code, 0, out)
        checks = {c["check"]: c for c in json.loads(out)["checks"]}
        self.assertEqual(checks["installed_addon"]["status"], "ok")
        self.assertEqual(checks["bridge"]["status"], "warning")

    def test_doctor_detects_missing_and_stale_addon(self):
        self.assertEqual(run_cli("doctor", "--target", str(self.mod), "--port", "9", "--json")[0], 1)
        run_cli("install-addon", "--target", str(self.mod))
        (self.mod / cli.ADDON_DIR_NAME / "freecad_ai_bridge" / "security.py").write_text("# old\n", encoding="utf-8")
        self.assertEqual(run_cli("doctor", "--target", str(self.mod), "--port", "9", "--json")[0], 1)

    def test_print_config(self):
        _, out, _ = run_cli("print-config", "--uvx")
        entry = json.loads(out)["mcpServers"]["freecad"]
        self.assertEqual(entry, {"command": "uvx", "args": ["--from", "freecad-mcp-server", "freecad-mcp"]})
        _, out, _ = run_cli("print-config", "--exe", "/opt/x/freecad-mcp")
        self.assertEqual(json.loads(out)["mcpServers"]["freecad"], {"command": "/opt/x/freecad-mcp", "args": []})

    def test_default_mod_dir_posix(self):
        home = Path(self.tmp.name) / "home"
        env = {"HOME": str(home), "USERPROFILE": str(home)}
        with patch.object(cli.sys, "platform", "linux"), patch.dict(cli.os.environ, env),                 patch.dict(cli.os.environ, {}, clear=False):
            for name in ("XDG_DATA_HOME", "FREECAD_USER_DATA"):
                cli.os.environ.pop(name, None)
            self.assertIsNone(cli.default_mod_dir())  # nothing exists yet
            native = home / ".local" / "share" / "FreeCAD" / "v1-1"
            native.mkdir(parents=True)
            self.assertEqual(cli.default_mod_dir(), native / "Mod")
            flatpak = home / ".var" / "app" / "org.freecad.FreeCAD" / "data" / "FreeCAD" / "v1-1"
            flatpak.mkdir(parents=True)
            self.assertIsNone(cli.default_mod_dir())  # ambiguous
            with self.assertRaises(SystemExit):
                cli.resolve_addon_target(None)
        with patch.object(cli.sys, "platform", "darwin"), patch.dict(cli.os.environ, env):
            mac = home / "Library" / "Application Support" / "FreeCAD" / "v1-1"
            mac.mkdir(parents=True)
            self.assertEqual(cli.default_mod_dir(), mac / "Mod")

    def test_freecad_running_posix(self):
        fake = type("R", (), {"stdout": "systemd\nfreecad\nbash\nFreeCAD\n"})()
        with patch.object(cli.sys, "platform", "linux"), patch.object(cli.subprocess, "run", return_value=fake):
            self.assertEqual(REAL_FREECAD_RUNNING(), ["FreeCAD", "freecad"])

    def test_no_arguments_starts_server(self):
        with patch.object(cli, "serve") as serve:
            self.assertEqual(cli.main([]), 0)
        serve.assert_called_once()


if __name__ == "__main__":
    unittest.main()
