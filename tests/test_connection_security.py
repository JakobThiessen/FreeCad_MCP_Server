from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "freecad_addon"))

from freecad_mcp.connection import FreeCADConnection, FreeCADRemoteError, _TimeoutTransport
from freecad_ai_bridge.security import raw_python_enabled, resolve_function


class ConnectionSecurityTests(unittest.TestCase):
    def test_developer_mode_requires_exact_process_opt_in(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(raw_python_enabled())
        for value in ["", "0", "true", "True", "yes", "01", " 1", "1 ", "1"]:
            with self.subTest(value=value), patch.dict("os.environ", {"FREECAD_MCP_ALLOW_RAW_PYTHON": value}, clear=True):
                self.assertEqual(raw_python_enabled(), value == "1")

    def test_transport_sets_socket_timeout(self):
        connection = _TimeoutTransport(1.25).make_connection("127.0.0.1:9875")
        self.assertEqual(connection.timeout, 1.25)

    def test_connect_uses_configured_transport(self):
        with patch("xmlrpc.client.ServerProxy") as proxy:
            proxy.return_value.ping.return_value = "pong"
            self.assertTrue(FreeCADConnection(timeout=2.5).connect())
            self.assertEqual(proxy.call_args.kwargs["transport"].timeout, 2.5)

    def test_response_errors_propagate(self):
        with self.assertRaisesRegex(RuntimeError, "bad shape"):
            FreeCADConnection()._parse_response('{"error": "bad shape"}')

    def test_structured_error_preserves_code_and_references(self):
        response = ('{"error": "Missing document", "error_details": {"code": "document_not_found", "message": "Missing document", '
                    '"references": [{"document": "Missing"}], "retryable": false}}')
        with self.assertRaises(FreeCADRemoteError) as caught:
            FreeCADConnection()._parse_response(response)
        self.assertIsInstance(caught.exception, RuntimeError)
        self.assertEqual(caught.exception.code, "document_not_found")
        self.assertEqual(caught.exception.details["references"], [{"document": "Missing"}])
        self.assertFalse(caught.exception.details["retryable"])

    def test_legacy_error_and_success_are_compatible(self):
        connection = FreeCADConnection()
        self.assertEqual(connection._parse_response('{"result": {"name": "Box"}}'), {"name": "Box"})
        with self.assertRaises(FreeCADRemoteError) as caught:
            connection._parse_response('{"error": "bad shape", "traceback": "legacy trace"}')
        self.assertEqual(caught.exception.code, "legacy_error")
        self.assertIn("legacy trace", str(caught.exception))

    def test_untrusted_modules_and_private_names_rejected(self):
        for module, function in [("os", "getcwd"), ("freecad_ai_bridge.operations", "_get_doc"),
                                 ("freecad_ai_bridge.operations", "FreeCAD.openDocument")]:
            with self.subTest(module=module, function=function), self.assertRaises(ValueError):
                resolve_function(module, function)

    def test_only_locally_defined_functions_are_rpc_targets(self):
        module_name = "freecad_ai_bridge.operations"
        module = types.ModuleType(module_name)
        exec("def allowed():\n    return 42\n", module.__dict__)
        module.imported = lambda: None
        module.constructor = dict
        with patch.dict(sys.modules, {module_name: module}):
            self.assertEqual(resolve_function(module_name, "allowed")(), 42)
            for name in ["imported", "constructor", "missing"]:
                with self.subTest(name=name), self.assertRaises(ValueError) as caught:
                    resolve_function(module_name, name)
                self.assertEqual(caught.exception.code, "rpc_not_allowed")


class Stage12cOperationTests(unittest.TestCase):
    def test_timeout_environment_is_bounded_and_default_unchanged(self):
        from freecad_mcp.connection import default_timeout
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(default_timeout(), 30.0)
            self.assertEqual(FreeCADConnection().timeout, 30.0)
        with patch.dict("os.environ", {"FREECAD_MCP_TIMEOUT_SECONDS": "2.5"}, clear=True):
            self.assertEqual(FreeCADConnection().timeout, 2.5)
            self.assertEqual(FreeCADConnection(timeout=7).timeout, 7)
        for bad in ["abc", "nan", "inf", "-1", "0", "0.05", "3601", "1e9"]:
            with self.subTest(value=bad), patch.dict("os.environ", {"FREECAD_MCP_TIMEOUT_SECONDS": bad}, clear=True):
                with self.assertRaises(ValueError):
                    default_timeout()

    def test_host_expected_bridge_version_matches_addon(self):
        from freecad_ai_bridge.contracts import BRIDGE_API_VERSION
        import freecad_mcp.server as server
        self.assertEqual(server.EXPECTED_BRIDGE_API_VERSION, BRIDGE_API_VERSION)

    def test_capabilities_report_mismatch_with_warning(self):
        import freecad_mcp.server as server
        stub = {"bridge_api_version": "0.10.0"}
        with patch.object(server, "_call", return_value=stub):
            response = server.get_capabilities()
        self.assertEqual(response.status, "success")
        self.assertEqual(response.data["compatibility"]["status"], "mismatch")
        self.assertTrue(response.warnings)
        with patch.object(server, "_call", return_value={"bridge_api_version": server.EXPECTED_BRIDGE_API_VERSION}):
            response = server.get_capabilities()
        self.assertEqual(response.data["compatibility"]["status"], "match")
        self.assertEqual(response.warnings, [])

    def test_rpc_not_allowed_from_structured_call_hints_old_addon(self):
        import freecad_mcp.server as server
        with patch.object(server._conn, "call_function", side_effect=FreeCADRemoteError("not allowed", code="rpc_not_allowed")):
            with self.assertRaises(FreeCADRemoteError) as raised:
                server._call("freecad_ai_bridge.operations", "some_new_tool")
        self.assertEqual(raised.exception.code, "rpc_not_allowed")
        self.assertIn("older than this host", str(raised.exception))
        self.assertIn(server.EXPECTED_BRIDGE_API_VERSION, str(raised.exception))
        with patch.object(server._conn, "call_function", side_effect=FreeCADRemoteError("x", code="other")):
            with self.assertRaises(FreeCADRemoteError) as raised:
                server._call("m", "f")
        self.assertNotIn("older than this host", str(raised.exception))


if __name__ == "__main__":
    unittest.main()