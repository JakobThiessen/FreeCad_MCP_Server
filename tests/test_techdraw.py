import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "freecad_addon"))


class TechDrawTests(unittest.TestCase):
    def setUp(self):
        self.modules = patch.dict(sys.modules, {"FreeCAD": Mock(), "FreeCADGui": Mock(), "Part": Mock()})
        self.modules.start()
        for name in ("freecad_ai_bridge.techdraw_ops", "freecad_ai_bridge.document_ops"):
            sys.modules.pop(name, None)
        self.ops = importlib.import_module("freecad_ai_bridge.techdraw_ops")
        self.ops.FreeCAD.getResourceDir.return_value = str(ROOT / "missing-resource-root")

    def tearDown(self):
        for name in ("freecad_ai_bridge.techdraw_ops", "freecad_ai_bridge.document_ops"):
            sys.modules.pop(name, None)
        self.modules.stop()

    def test_missing_template_never_creates_page(self):
        document = Mock()
        with patch.object(self.ops, "_document", return_value=document):
            with self.assertRaisesRegex(ValueError, "not found"):
                self.ops.create_page("Doc", "MissingTemplate.svg")
        document.addObject.assert_not_called()

    def test_page_uses_native_template_and_paper_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Template.svg"
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm"/>')
            document = Mock(Name="Doc")
            page = types.SimpleNamespace(Document=document, Name="Page", Scale=1.0)
            template = types.SimpleNamespace(Document=document, Name="PageTemplate", EditableTexts={"Title": ""})
            document.addObject.side_effect = [page, template]
            with patch.object(self.ops, "_document", return_value=document):
                result = self.ops.create_page("Doc", str(path))
            self.assertEqual(result["paper_mm"], [297, 210])
            self.assertIs(page.Template, template)
            self.assertEqual(result["reference"], {"document": "Doc", "object": "Page"})