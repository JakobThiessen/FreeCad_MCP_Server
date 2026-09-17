from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "freecad_addon"))

from freecad_mcp.connection import FreeCADConnection, FreeCADRemoteError, _TimeoutTransport
from freecad_ai_bridge.security import resolve_function


class ConnectionSecurityTests(unittest.TestCase):
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
                with self.subTest(name=name), self.assertRaises(ValueError):
                    resolve_function(module_name, name)


if __name__ == "__main__":
    unittest.main()