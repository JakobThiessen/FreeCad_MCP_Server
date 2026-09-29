"""Run run_tests() inside the FreeCAD GUI Python environment."""

import io
import json
import fnmatch
import math
from pathlib import Path
import tempfile
import unittest

import FreeCAD
import Part

from freecad_ai_bridge import partdesign_ops as design
from freecad_ai_bridge import sketcher_ops as sketcher
from freecad_ai_bridge import view_ops as view
from freecad_ai_bridge import part_ops as part


class FreeCADIntegrationTests(unittest.TestCase):
    def test_stage4b_view_document_isolation(self):
        from freecad_ai_bridge import geometry_ops as geometry
        import FreeCADGui
        import base64
        try:
            from PySide6.QtGui import QImage
        except ImportError:
            from PySide2.QtGui import QImage

        other = FreeCAD.newDocument("Stage4_View_Other")
        try:
            selections = []
            for doc in (self.doc, other):
                box = doc.addObject("Part::Box", "Box")
                doc.recompute()
                selected = geometry.select_subelement(doc.Name, box.Name, "face", {"normal": [0, 0, 1]})["selection"]
                selections.append(selected)
                geometry.highlight_subelements(doc.Name, [selected])
            FreeCAD.setActiveDocument(other.Name)
            before = geometry.get_view_state(other.Name, ["Box"])
            self.assertTrue(before["selection"])
            for preset in ["isometric", "front", "back", "top", "bottom", "left", "right"]:
                captured = geometry.capture_view(self.doc.Name, 320, 240, preset, [selections[0]])
                image = QImage.fromData(base64.b64decode(captured["image_base64"]))
                self.assertFalse(image.isNull())
                pixels = sum(image.pixel(column, row) != image.pixel(2, row)
                             for row in range(8, 232, 8) for column in range(8, 312, 8))
                self.assertGreater(pixels, 20, preset)
                directions = {"top": [0, 0, -1], "bottom": [0, 0, 1], "front": [0, 1, 0],
                              "back": [0, -1, 0], "left": [1, 0, 0], "right": [-1, 0, 0]}
                if preset in directions:
                    direction = FreeCAD.Rotation(*captured["camera_quaternion"]).multVec(FreeCAD.Vector(0, 0, -1))
                    for actual, expected in zip(direction, directions[preset]):
                        self.assertAlmostEqual(actual, expected, places=6, msg=preset)
                self.assertEqual(geometry.get_view_state(other.Name, ["Box"]), before)
                self.assertEqual(FreeCAD.ActiveDocument.Name, other.Name)
                self.assertTrue(FreeCADGui.Selection.getSelectionEx(self.doc.Name))
        finally:
            FreeCAD.closeDocument(other.Name)

    def test_stage4a_geometry_variants_and_invalid_inputs(self):
        from freecad_ai_bridge import geometry_ops as geometry

        box = self.doc.addObject("Part::Box", "Box")
        box.Length, box.Width, box.Height = 10, 20, 30
        shapes = [("Sphere", Part.makeSphere(5), "sphere"), ("Cone", Part.makeCone(5, 2, 10), "cone"),
                  ("Torus", Part.makeTorus(10, 2), "torus"), ("Cylinder", Part.makeCylinder(5, 20), "cylinder")]
        for name, shape, expected_type in shapes:
            obj = self.doc.addObject("Part::Feature", name)
            obj.Shape = shape
            self.doc.recompute()
            result = geometry.list_subelements(self.doc.Name, name, "face", {"geometry_type": expected_type})
            self.assertGreater(result["total"], 0, result)
        ellipse = Part.Ellipse(FreeCAD.Vector(0, 0, 0), 5, 2).toShape()
        spline = Part.BSplineCurve()
        spline.interpolate([FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(5, 5, 0), FreeCAD.Vector(10, 0, 0)])
        for name, shape, expected_type in [("Ellipse", ellipse, "ellipse"), ("Spline", spline.toShape(), "bspline_curve")]:
            obj = self.doc.addObject("Part::Feature", name)
            obj.Shape = shape
            self.doc.recompute()
            result = geometry.select_subelement(self.doc.Name, name, "edge", {"geometry_type": expected_type})
            with self.assertRaises(ValueError) as caught:
                geometry.measure_angle(result["selection"], result["selection"])
            self.assertEqual(caught.exception.code, "unsupported_geometry")
        for filters in [{"unknown": 1}, {"position": [1, 2]}, {"position": [0, 0, float("nan")]},
                        {"axis": [0, 0, 0]}, {"area": {}}, {"length": {"min": -1}},
                        {"bbox": {"min": [1, 0, 0], "max": [0, 0, 0]}}, {"geometry_type": "invented"}]:
            with self.subTest(filters=filters), self.assertRaises(ValueError) as caught:
                geometry.list_subelements(self.doc.Name, box.Name, "face", filters)
            self.assertEqual(caught.exception.code, "invalid_arguments")
        for options in [{"limit": 0}, {"limit": 257}, {"offset": -1}, {"tolerance": -1}, {"angular_tolerance": 181}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                geometry.list_subelements(self.doc.Name, box.Name, "face", **options)
        parent = self.doc.addObject("App::Part", "Parent")
        parent.addObject(box)
        parent.Placement = FreeCAD.Placement(FreeCAD.Vector(100, 0, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90))
        self.doc.recompute()
        side = geometry.select_subelement(self.doc.Name, box.Name, "face", {"normal": [0, 1, 0]})
        for actual, expected in zip(side["position"], [90, 10, 15]):
            self.assertAlmostEqual(actual, expected)
        linked = self.doc.addObject("App::Link", "LinkedBox")
        linked.setLink(box)
        linked.Placement.Base = FreeCAD.Vector(50, 0, 0)
        self.doc.recompute()
        linked_top = geometry.select_subelement(self.doc.Name, linked.Name, "face", {"normal": [0, 0, 1]})
        for actual, expected in zip(linked_top["position"], [55, 10, 30]):
            self.assertAlmostEqual(actual, expected)
        parent.addObject(linked)
        self.doc.recompute()
        linked_top = geometry.select_subelement(self.doc.Name, linked.Name, "face", {"normal": [0, 0, 1]})
        for actual, expected in zip(linked_top["position"], [90, 55, 30]):
            self.assertAlmostEqual(actual, expected)
        probe = self.doc.addObject("Part::Feature", "Probe")
        probe.Shape = Part.makeBox(10, 20, 30)
        self.doc.recompute()
        old = geometry.select_subelement(self.doc.Name, probe.Name, "face", {"normal": [0, 0, 1]})["selection"]
        probe.Shape = probe.Shape.cut(Part.makeCylinder(2, 30, FreeCAD.Vector(5, 10, 0)))
        with self.assertRaises(ValueError) as caught:
            geometry.resolve_subelement(old)
        self.assertEqual(caught.exception.code, "stale_selection")
        self.doc.recompute()
        self.assertGreater(geometry.list_subelements(self.doc.Name, probe.Name, "face")["total"], 6)
        current = geometry.select_subelement(self.doc.Name, probe.Name, "face", {"normal": [0, 0, 1]})["selection"]
        self.doc.removeObject(probe.Name)
        replacement = self.doc.addObject("Part::Box", "Probe")
        self.doc.recompute()
        self.assertEqual(replacement.Name, current["object"])
        with self.assertRaises(ValueError) as caught:
            geometry.resolve_subelement(current)
        self.assertEqual(caught.exception.code, "stale_selection")
        empty = self.doc.addObject("App::FeaturePython", "NoShape")
        self.doc.recompute()
        with self.assertRaises(ValueError) as caught:
            geometry.list_subelements(self.doc.Name, empty.Name, "face")
        self.assertEqual(caught.exception.code, "invalid_geometry")

    def test_stage4a_selection_consumers(self):
        from freecad_ai_bridge import geometry_ops as geometry
        from freecad_ai_bridge.gui_executor import GuiExecutor

        executor = GuiExecutor()
        first = self.doc.addObject("Part::Box", "First")
        first.Length = first.Width = first.Height = 20
        self.doc.recompute()
        if self.doc.HasPendingTransaction:
            self.doc.commitTransaction()
        selection = geometry.select_subelement(self.doc.Name, first.Name, "edge", {"position": [0, 0, 10]})["selection"]
        result = executor._execute_function("freecad_ai_bridge.part_ops", "part_fillet", json.dumps(
            {"doc_name": self.doc.Name, "obj_name": first.Name, "edges": [selection], "radius": 1}))
        self.assertTrue(result["shape_valid"])
        before = set(obj.Name for obj in self.doc.Objects)
        with self.assertRaises(ValueError) as caught:
            executor._execute_function("freecad_ai_bridge.part_ops", "part_chamfer", json.dumps(
                {"doc_name": self.doc.Name, "obj_name": first.Name, "edges": [selection], "size": 1}))
        self.assertEqual(caught.exception.code, "stale_selection")
        self.assertEqual(before, set(obj.Name for obj in self.doc.Objects))
        self.assertFalse(self.doc.HasPendingTransaction)
        self.doc.undo()
        self.doc.recompute()
        selection = geometry.select_subelement(self.doc.Name, first.Name, "edge", {"position": [0, 0, 10]})["selection"]
        result = executor._execute_function("freecad_ai_bridge.part_ops", "part_chamfer", json.dumps(
            {"doc_name": self.doc.Name, "obj_name": first.Name, "edges": [selection], "size": 1}))
        self.assertTrue(result["shape_valid"])
        for operation in ["fillet", "chamfer", "thickness", "draft"]:
            with self.subTest(operation=operation):
                body = self.doc.addObject("PartDesign::Body", "ConsumerBody")
                base = body.newObject("PartDesign::Feature", "ConsumerBase")
                base.Shape = Part.makeBox(20, 20, 20)
                self.doc.recompute()
                if self.doc.HasPendingTransaction:
                    self.doc.commitTransaction()
                arguments = {"doc_name": self.doc.Name, "base_name": base.Name}
                if operation in {"fillet", "chamfer"}:
                    arguments["edges"] = [geometry.select_subelement(self.doc.Name, base.Name, "edge", {"position": [0, 0, 10]})["selection"]]
                    arguments["radius" if operation == "fillet" else "size"] = 1
                else:
                    normal = [0, 0, 1] if operation == "thickness" else [1, 0, 0]
                    arguments["faces"] = [geometry.select_subelement(self.doc.Name, base.Name, "face", {"normal": normal})["selection"]]
                    if operation == "thickness":
                        arguments["value"] = 1
                    else:
                        bottom = geometry.select_subelement(self.doc.Name, base.Name, "face", {"normal": [0, 0, -1]})["selection"]
                        arguments.update(angle=5, plane_name=base.Name + "." + bottom["subelement"])
                result = executor._execute_function("freecad_ai_bridge.partdesign_ops", operation, json.dumps(arguments))
                self.assertTrue(result["shape_valid"])
                before = {obj.Name for obj in self.doc.Objects}
                with self.assertRaises(ValueError) as caught:
                    executor._execute_function("freecad_ai_bridge.partdesign_ops", operation, json.dumps(arguments))
                self.assertEqual(caught.exception.code, "stale_selection")
                self.assertEqual(before, {obj.Name for obj in self.doc.Objects})
                self.assertFalse(self.doc.HasPendingTransaction)

    def test_stage4b_measurements_and_view(self):
        from freecad_ai_bridge import geometry_ops as geometry
        import base64
        import FreeCADGui

        first = self.doc.addObject("Part::Box", "First")
        first.Length, first.Width, first.Height = 10, 20, 30
        second = self.doc.addObject("Part::Box", "Second")
        second.Length, second.Width, second.Height = 10, 20, 30
        self.doc.recompute()
        references = [{"document": self.doc.Name, "object": obj.Name} for obj in (first, second)]
        for position, expected_distance, expected_volume, classification in [(15, 5, 0, "separated"), (10, 0, 0, "contact"), (5, 0, 3000, "interference")]:
            second.Placement.Base.x = position
            self.doc.recompute()
            result = geometry.check_interference(*references)
            self.assertAlmostEqual(result["distance"], expected_distance)
            self.assertAlmostEqual(result["intersection_volume"], expected_volume)
            self.assertEqual(result["classification"], classification)
            self.assertAlmostEqual(geometry.measure_distance(*references)["distance"], expected_distance)
        top = geometry.select_subelement(self.doc.Name, first.Name, "face", {"normal": [0, 0, 1]})["selection"]
        side = geometry.select_subelement(self.doc.Name, first.Name, "face", {"normal": [1, 0, 0]})["selection"]
        edge = geometry.select_subelement(self.doc.Name, first.Name, "edge", {"position": [0, 0, 15]})["selection"]
        horizontal = geometry.select_subelement(self.doc.Name, first.Name, "edge", {"position": [5, 0, 0]})["selection"]
        for pair, expected in [((top, side), 90), ((edge, horizontal), 90), ((edge, top), 90), ((horizontal, top), 0), ((top, top), 0)]:
            self.assertAlmostEqual(geometry.measure_angle(*pair)["angle"], expected)
        with self.assertRaises(ValueError):
            geometry.measure_angle(*references)
        geometry.highlight_subelements(self.doc.Name, [top])
        state = geometry.get_view_state(self.doc.Name, [first.Name])
        self.assertEqual(state["selection"][0]["subelements"], [top["subelement"]])
        for preset in ["isometric", "front", "back", "top", "bottom", "left", "right"]:
            image = geometry.capture_view(self.doc.Name, 320, 240, preset)
            self.assertTrue(base64.b64decode(image["image_base64"]).startswith(b"\x89PNG\r\n\x1a\n"))
        geometry.resolve_subelement(top)
        before = geometry.get_view_state(self.doc.Name, [first.Name])
        with self.assertRaises(ValueError):
            geometry.highlight_subelements(self.doc.Name, [dict(top, revision="stale")])
        self.assertEqual(before, geometry.get_view_state(self.doc.Name, [first.Name]))
        geometry.highlight_subelements(self.doc.Name, [])
        self.assertFalse(FreeCADGui.Selection.getSelectionEx(self.doc.Name))
        original = geometry.get_view_state(self.doc.Name, [first.Name])["objects"][0]
        view.set_color(first.Name, 0.2, 0.7, 0.3, self.doc.Name)
        for value, expected in [(-1, 0), (25, 25), (101, 100)]:
            self.assertEqual(view.set_transparency(first.Name, value, self.doc.Name)["transparency"], expected)
            self.assertEqual(first.ViewObject.Transparency, expected)
        view.set_visibility(first.Name, False, self.doc.Name)
        self.assertFalse(geometry.get_view_state(self.doc.Name, [first.Name])["objects"][0]["visible"])
        with self.assertRaises(ValueError):
            view.set_color(first.Name, 1.1, 0, 0, self.doc.Name)
        view.set_color(first.Name, *original["color"][:3], doc_name=self.doc.Name)
        view.set_transparency(first.Name, original["transparency"], self.doc.Name)
        view.set_visibility(first.Name, original["visible"], self.doc.Name)
        self.assertEqual(geometry.get_view_state(self.doc.Name, [first.Name])["objects"][0], original)

    def test_stage4a_selection_revision(self):
        from freecad_ai_bridge import geometry_ops as geometry

        box = self.doc.addObject("Part::Box", "SelectionBox")
        box.Length, box.Width, box.Height = 10, 20, 30
        self.doc.recompute()
        faces = geometry.list_subelements(self.doc.Name, box.Name, "face")
        self.assertEqual(faces["total"], 6)
        top = geometry.select_subelement(self.doc.Name, box.Name, "face",
                                         {"geometry_type": "plane", "normal": [0, 0, 1], "area": {"min": 200, "max": 200}})
        self.assertEqual(top["position"], [5, 10, 30])
        self.assertEqual(geometry.resolve_subelement(top["selection"])["position"], [5, 10, 30])
        for filters, code in [({}, "selection_ambiguous"), ({"radius": {"min": 1}}, "selection_empty")]:
            with self.assertRaises(ValueError) as caught:
                geometry.select_subelement(self.doc.Name, box.Name, "face", filters)
            self.assertEqual(caught.exception.code, code)
        box.Height = 40
        self.doc.recompute()
        with self.assertRaises(ValueError) as caught:
            geometry.resolve_subelement(top["selection"])
        self.assertEqual(caught.exception.code, "stale_selection")
        parent = self.doc.addObject("App::Part", "Parent")
        parent.addObject(box)
        parent.Placement.Base = FreeCAD.Vector(100, 0, 0)
        self.doc.recompute()
        top = geometry.select_subelement(self.doc.Name, box.Name, "face", {"normal": [0, 0, 1]})
        self.assertEqual(top["position"], [105, 10, 40])

    def test_stage3_containers_copy_delete_and_transforms(self):
        from freecad_ai_bridge.gui_executor import GuiExecutor

        executor = GuiExecutor()
        if self.doc.HasPendingTransaction:
            self.doc.commitTransaction()

        def call(function, **arguments):
            return executor._execute_function("freecad_ai_bridge.document_ops", function,
                                              json.dumps(dict(doc_name=self.doc.Name, **arguments)))

        def part_call(function, **arguments):
            return executor._execute_function("freecad_ai_bridge.part_ops", function,
                                              json.dumps(dict(doc_name=self.doc.Name, **arguments)))

        box = part_call("make_box", length=10, width=10, height=10, name="Base")["name"]
        cutter = part_call("make_box", length=5, width=5, height=10, name="Cutter")["name"]
        cut = part_call("boolean_cut", base_name=box, tool_name=cutter)["name"]
        copied = call("copy_object", obj_name=cut)["name"]
        call("set_properties", obj_name=box, values={"Length": {"value": 20, "unit": "mm"}})
        self.assertAlmostEqual(self.doc.getObject(cut).Shape.Volume, 1750)
        self.assertAlmostEqual(self.doc.getObject(copied).Shape.Volume, 750)
        preview = call("preview_delete", obj_names=[box])
        self.assertEqual(set(preview["confirmation"]), {box, cut})
        with self.assertRaises(ValueError):
            call("delete_objects", obj_names=[box], confirmed_objects=[box])
        call("delete_objects", obj_names=[box], confirmed_objects=preview["confirmation"])
        self.doc.undo()
        self.doc.recompute()
        self.assertAlmostEqual(self.doc.getObject(cut).Shape.Volume, 1750)
        group = call("create_container", name="Group")["name"]
        child_group = call("create_container", name="ChildGroup")["name"]
        call("set_container_members", obj_name=group, members=[child_group, copied])
        with self.assertRaises(ValueError):
            call("set_container_members", obj_name=child_group, members=[group])
        preview = call("preview_delete", obj_names=[group])
        self.assertEqual(set(preview["confirmation"]), {group, child_group, copied})
        call("delete_objects", obj_names=[group], confirmed_objects=preview["confirmation"])
        self.doc.undo()
        self.doc.recompute()
        self.assertEqual({obj.Name for obj in self.doc.getObject(group).Group}, {child_group, copied})
        body = call("create_container", name="EmptyBody", kind="body")["name"]
        preview = call("preview_delete", obj_names=[body])
        self.assertGreater(len(preview["confirmation"]), 1)
        call("delete_objects", obj_names=[body], confirmed_objects=preview["confirmation"])
        self.doc.undo()
        self.doc.recompute()
        self.assertIsNotNone(self.doc.getObject(body).Origin)
        for angles, expected in [({"rx": 90}, (0, 0, 1)), ({"ry": 90}, (0, 1, 0)),
                                  ({"rz": 90}, (-1, 0, 0)), ({"rx": 90, "ry": 90, "rz": 90}, (0, 1, 0))]:
            with self.subTest(angles=angles):
                part_call("set_placement", obj_name=box, **angles)
                transformed = self.doc.getObject(box).Placement.multVec(FreeCAD.Vector(0, 1, 0))
                for actual, target_value in zip(transformed, expected):
                    self.assertAlmostEqual(actual, target_value, places=6)
                before = self.doc.getObject(box).Placement.copy()
                part_call("move_object", obj_name=box, dx=4, dy=5, dz=6)
                part_call("move_object", obj_name=box, dx=-4, dy=-5, dz=-6)
                self.assertTrue(self.doc.getObject(box).Placement.isSame(before, 1e-9))

    def test_stage3_property_type_roundtrips(self):
        from freecad_ai_bridge.gui_executor import GuiExecutor
        from freecad_ai_bridge import document_ops

        executor = GuiExecutor()
        holder = self.doc.addObject("App::FeaturePython", "TypedProperties")
        target = self.doc.addObject("Part::Box", "Target")
        self.doc.recompute()
        reference = {"document": self.doc.Name, "object": target.Name}
        placement = {"position": [1, 2, 3], "quaternion": [0, 0, 0, 1]}
        cases = {"App::PropertyBool": True, "App::PropertyInteger": 7,
                 "App::PropertyIntegerConstraint": 2, "App::PropertyFloat": 2.5,
                 "App::PropertyFloatConstraint": 0.5, "App::PropertyString": "hello",
                 "App::PropertyEnumeration": "Second", "App::PropertyQuantity": {"value": 4, "unit": ""},
                 "App::PropertyLength": {"value": 2, "unit": "cm"},
                 "App::PropertyVector": [1, 2, 3], "App::PropertyPlacement": placement,
                 "App::PropertyLink": reference,
                 "App::PropertyLinkSub": {"reference": reference, "subelements": ["Face1"]},
                 "App::PropertyBoolList": [True, False], "App::PropertyIntegerList": [1, 2],
                 "App::PropertyFloatList": [1.5, 2.5], "App::PropertyStringList": ["a", "b"],
                 "App::PropertyVectorList": [[1, 2, 3]], "App::PropertyPlacementList": [placement],
                 "App::PropertyLinkList": [reference],
                 "App::PropertyLinkSubList": [{"reference": reference, "subelements": ["Edge1"]}]}
        for kind in sorted(document_ops._QUANTITIES - {"App::PropertyQuantity", "App::PropertyLength"}):
            units = {"Distance": "mm", "Angle": "deg", "Area": "mm^2", "Volume": "mm^3",
                     "Speed": "mm/s", "Acceleration": "mm/s^2", "Pressure": "kg/mm/s^2", "Force": "kg*mm/s^2"}
            cases[kind] = {"value": 3, "unit": units[kind.removeprefix("App::Property")]}
        names = {}
        for index, (kind, value) in enumerate(cases.items()):
            name = f"Value{index}"
            holder.addProperty(kind, name)
            names[kind] = name
            if kind == "App::PropertyEnumeration":
                setattr(holder, name, ["First", "Second"])
            if kind.endswith("Constraint"):
                setattr(holder, name, (0, 0, 10, 1))
        holder.addProperty("App::PropertyString", "ReadOnly")
        holder.setEditorMode("ReadOnly", 1)
        self.doc.recompute()
        if self.doc.HasPendingTransaction:
            self.doc.commitTransaction()

        def call(function, **arguments):
            return executor._execute_function("freecad_ai_bridge.document_ops", function,
                                              json.dumps(dict(doc_name=self.doc.Name, obj_name=holder.Name, **arguments)))

        for kind, value in cases.items():
            with self.subTest(kind=kind):
                name = names[kind]
                result = call("set_properties", values={name: value})["properties"][0]
                expected = {"value": 20, "unit": "mm"} if kind == "App::PropertyLength" else value
                if kind in document_ops._QUANTITIES:
                    self.assertEqual(result["value"]["value"], expected["value"])
                else:
                    self.assertEqual(result["value"], expected)
                self.assertTrue(result["writable"])
                call("set_properties", values={name: result["value"]})
                before = call("get_properties", properties=[name])
                with self.assertRaises(Exception):
                    call("set_properties", values={name: {"invalid": True}})
                self.assertEqual(call("get_properties", properties=[name]), before)
                self.assertFalse(self.doc.HasPendingTransaction)
        for values in [{"ReadOnly": "x"}, {names["App::PropertyEnumeration"]: "Missing"},
                       {names["App::PropertyLink"]: {"document": self.doc.Name, "object": "Missing"}},
                       {names["App::PropertyLink"]: {"document": self.doc.Name, "object": holder.Name}},
                       {names["App::PropertyLinkSub"]: {"reference": reference, "subelements": ["Face999"]}}]:
            with self.assertRaises(ValueError):
                call("set_properties", values=values)
            self.assertFalse(self.doc.HasPendingTransaction)
        for kind in ("App::PropertyLink", "App::PropertyLinkSub"):
            result = call("set_properties", values={names[kind]: None})
            self.assertIsNone(result["properties"][0]["value"])
        for kind in ("App::PropertyIntegerConstraint", "App::PropertyFloatConstraint"):
            before = call("get_properties", properties=[names[kind]])
            with self.assertRaises(ValueError):
                call("set_properties", values={names[kind]: 100})
            self.assertEqual(call("get_properties", properties=[names[kind]]), before)

    def test_stage3_spreadsheet_expressions_and_rollback(self):
        from freecad_ai_bridge.gui_executor import GuiExecutor

        executor = GuiExecutor()
        if self.doc.HasPendingTransaction:
            self.doc.commitTransaction()

        def call(function, **arguments):
            return executor._execute_function("freecad_ai_bridge.document_ops", function,
                                              json.dumps(dict(doc_name=self.doc.Name, **arguments)))

        sheet_name = call("create_spreadsheet")["name"]
        call("set_spreadsheet_cells", obj_name=sheet_name, cells={"A1": "10 mm", "A2": "=A1 * 2", "B1": "text"})
        call("set_spreadsheet_alias", obj_name=sheet_name, cell="A1", alias="LengthParam")
        box = executor._execute_function("freecad_ai_bridge.part_ops", "make_box", json.dumps(
            dict(doc_name=self.doc.Name, length=1, width=2, height=3, name="DrivenBox")))["name"]
        call("set_expression", obj_name=box, property_name="Length", expression=f"{sheet_name}.LengthParam")
        self.assertAlmostEqual(self.doc.getObject(box).Shape.Volume, 60)
        copied = call("copy_object", obj_name=box)["name"]
        before = call("read_spreadsheet", obj_name=sheet_name, cell_range="A1:B2")
        for function, arguments in [
            ("set_spreadsheet_cells", {"obj_name": sheet_name, "cells": {"A1": "=A2"}}),
            ("set_spreadsheet_cells", {"obj_name": sheet_name, "cells": {"A1": "=Missing.Value"}}),
            ("set_spreadsheet_alias", {"obj_name": sheet_name, "cell": "A2", "alias": "LengthParam"}),
            ("set_expression", {"obj_name": box, "property_name": "Width", "expression": f"{box}.Width"}),
            ("set_expression", {"obj_name": box, "property_name": "Width", "expression": "Missing.Length"}),
            ("set_expression", {"obj_name": box, "property_name": "Length", "expression": "-1 mm"}),
        ]:
            with self.subTest(function=function, arguments=arguments), self.assertRaises(ValueError):
                call(function, **arguments)
            self.assertEqual(call("read_spreadsheet", obj_name=sheet_name, cell_range="A1:B2"), before)
            self.assertAlmostEqual(self.doc.getObject(box).Shape.Volume, 60)
            self.assertFalse(self.doc.HasPendingTransaction)
        call("set_spreadsheet_cells", obj_name=sheet_name, cells={"A1": "20 mm", "B1": None})
        self.assertAlmostEqual(self.doc.getObject(box).Shape.Volume, 120)
        self.assertAlmostEqual(self.doc.getObject(copied).Shape.Volume, 60)
        call("set_expression", obj_name=box, property_name="Length", expression=None)
        call("set_spreadsheet_alias", obj_name=sheet_name, cell="A1", alias=None)
        self.assertFalse(call("get_expressions", obj_name=box)["expressions"])
        self.assertIsNone(call("read_spreadsheet", obj_name=sheet_name, cell_range="A1")["cells"][0]["alias"])

    def test_stage3_document_properties_and_files(self):
        from freecad_ai_bridge.gui_executor import GuiExecutor

        executor = GuiExecutor()

        def call(function, **arguments):
            return executor._execute_function("freecad_ai_bridge.document_ops", function,
                                              json.dumps(dict(doc_name=self.doc.Name, **arguments)))

        box = part.make_box(10, 20, 30, name="TypedBox", doc_name=self.doc.Name)
        self.doc.recompute()
        if self.doc.HasPendingTransaction:
            self.doc.commitTransaction()
        info = call("inspect_document")
        self.assertTrue(info["modified"])
        properties = call("get_properties", obj_name=box["name"], properties=["Length", "Placement", "Shape"])
        self.assertEqual(properties["properties"][0]["unit"], "mm")
        self.assertFalse(properties["properties"][2]["writable"])
        changed = call("set_properties", obj_name=box["name"], values={"Length": {"value": 25, "unit": "mm"}})
        self.assertEqual(changed["properties"][0]["value"]["value"], 25)
        self.assertAlmostEqual(self.doc.getObject(box["name"]).Shape.Volume, 15000)
        self.doc.undo()
        self.doc.recompute()
        self.assertAlmostEqual(self.doc.getObject(box["name"]).Shape.Volume, 6000)
        self.doc.redo()
        self.doc.recompute()
        for values in [{"Shape": "forbidden"}, {"Length": {"value": 1, "unit": "deg"}}, {"Length": True}]:
            with self.assertRaises(ValueError):
                call("set_properties", obj_name=box["name"], values=values)
            self.assertFalse(self.doc.HasPendingTransaction)
            self.assertAlmostEqual(self.doc.getObject(box["name"]).Shape.Volume, 15000)
        with self.assertRaises(ValueError) as caught:
            call("close_document_safe")
        self.assertEqual(caught.exception.code, "unsaved_changes")
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "typed.FCStd")
            call("save_document_safe", path=path)
            self.assertFalse(call("inspect_document")["modified"])
            before = Path(path).read_bytes()
            with self.assertRaises(ValueError) as caught:
                call("save_document_safe", path=path)
            self.assertEqual(caught.exception.code, "file_exists")
            self.assertEqual(Path(path).read_bytes(), before)
            call("save_document_safe", overwrite=True)
            before = Path(path).read_bytes()
            blocked_path = Path(directory) / "directory.FCStd"
            blocked_path.mkdir()
            with self.assertRaises(ValueError) as caught:
                call("save_document_safe", path=str(blocked_path), overwrite=True)
            self.assertEqual(caught.exception.code, "invalid_arguments")
            self.assertTrue(blocked_path.is_dir())
            self.assertEqual(Path(path).read_bytes(), before)
            with self.assertRaises(ValueError):
                call("save_document_safe", path=str(Path(directory) / "missing" / "model.FCStd"))

    def test_stage2_foreign_transactions_and_batch_rollback(self):
        from freecad_ai_bridge.gui_executor import GuiExecutor
        from freecad_ai_bridge.batch import run_batch

        executor = GuiExecutor()
        second = FreeCAD.newDocument("MCP_Transaction_Second")
        try:
            for doc in [self.doc, second]:
                executor._execute_function("freecad_ai_bridge.part_ops", "make_box", json.dumps({
                    "length": 10, "width": 10, "height": 10, "name": "SameBox", "doc_name": doc.Name}))
            before = [doc.getObject("SameBox").Shape.Volume for doc in [self.doc, second]]
            second.openTransaction("Foreign transaction")
            second.getObject("SameBox").Label = "Foreign unsaved label"
            self.assertTrue(second.HasPendingTransaction)
            steps = [{"id": "move", "operation": "move_object", "doc_name": self.doc.Name,
                      "arguments": {"obj_name": "SameBox", "dx": 10}},
                     {"id": "other", "operation": "move_object", "doc_name": second.Name,
                      "arguments": {"obj_name": "SameBox", "dx": 10}}]
            with self.assertRaises(ValueError) as caught:
                run_batch(steps, atomic=False)
            self.assertEqual(caught.exception.code, "transaction_conflict")
            self.assertTrue(second.HasPendingTransaction)
            self.assertEqual(second.getObject("SameBox").Label, "Foreign unsaved label")
            self.assertEqual(self.doc.getObject("SameBox").Placement.Base.x, 0)
            for function, arguments in [("move_object", {"obj_name": "SameBox", "dx": 10}),
                                        ("undo", {}), ("redo", {})]:
                module = "part_ops" if function == "move_object" else "view_ops"
                with self.assertRaises(ValueError) as caught:
                    executor._execute_function("freecad_ai_bridge." + module, function,
                                               json.dumps(dict(arguments, doc_name=second.Name)))
                self.assertEqual(caught.exception.code, "transaction_conflict")
                self.assertTrue(second.HasPendingTransaction)
            second.abortTransaction()
            self.assertEqual(before, [doc.getObject("SameBox").Shape.Volume for doc in [self.doc, second]])
            self.assertFalse(self.doc.HasPendingTransaction)
            self.assertFalse(second.HasPendingTransaction)
        finally:
            if second.HasPendingTransaction:
                second.abortTransaction()
            FreeCAD.closeDocument(second.Name)

    def setUp(self):
        self.previous = FreeCAD.ActiveDocument
        self.doc = FreeCAD.newDocument("MCP_Integration_Test")
        self.body = self.doc.addObject("PartDesign::Body", "Body")

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)
        if self.previous:
            FreeCAD.setActiveDocument(self.previous.Name)

    def rectangle(self, name, bounds, offset=0):
        sketcher.create_sketch(name, offset=offset, body_name=self.body.Name)
        sketcher.add_rectangle(name, *bounds)
        return self.doc.getObject(name)

    def circle(self, name, radius, offset=0, center=(0, 0)):
        sketcher.create_sketch(name, offset=offset, body_name=self.body.Name)
        sketcher.add_circle(name, *center, radius)
        return self.doc.getObject(name)

    def plate_with_hole(self):
        self.rectangle("BaseProfile", (-30, -30, 30, 30))
        design.pad("BaseProfile", 10)
        self.circle("HoleProfile", 2, offset=10, center=(10, 10))
        design.pocket("HoleProfile", 10)

    def test_symmetric_pad(self):
        self.rectangle("Profile", (-5, -5, 5, 5))
        design.pad("Profile", 12, symmetric=True)
        shape = self.body.Tip.Shape
        self.assertAlmostEqual(shape.BoundBox.ZMin, -6)
        self.assertAlmostEqual(shape.BoundBox.ZMax, 6)
        self.assertAlmostEqual(shape.Volume, 1200)

    def test_stage6a_datums_and_pad_end_conditions(self):
        plane = design.create_datum(self.body.Name, "plane", z=3, rotation_z=15)
        axis = design.create_datum(self.body.Name, "axis", x=2)
        point = design.create_datum(self.body.Name, "point", y=4)
        self.assertEqual(self.doc.getObject(plane["name"]).TypeId, "PartDesign::Plane")
        self.assertEqual(self.doc.getObject(axis["name"]).TypeId, "PartDesign::Line")
        self.assertEqual(self.doc.getObject(point["name"]).TypeId, "PartDesign::Point")
        self.assertEqual(tuple(self.doc.getObject(plane["name"]).AttachmentOffset.Base), (0, 0, 3))
        self.assertEqual(tuple(self.doc.getObject(plane["name"]).Placement.Base), (0, 0, 3))

        self.rectangle("TwoSidedProfile", (-5, -5, 5, 5))
        result = design.pad("TwoSidedProfile", 10, end_condition="two_lengths", second_length=4)
        self.assertTrue(result["shape_valid"])
        self.assertAlmostEqual(self.body.Tip.Shape.BoundBox.ZMin, -4)
        self.assertAlmostEqual(self.body.Tip.Shape.BoundBox.ZMax, 10)
        self.assertAlmostEqual(self.body.Tip.Shape.Volume, 1400)

    def test_stage6a_datum_supports_and_pocket_targets(self):
        from freecad_ai_bridge import geometry_ops as geometry

        support = self.doc.addObject("Part::Feature", "DatumSupport")
        support.Shape = Part.makeCylinder(5, 20)
        self.doc.recompute()
        planar = geometry.list_subelements(self.doc.Name, support.Name, "face",
                           {"geometry_type": "plane"}, limit=1)["items"][0]["selection"]
        cylindrical = geometry.select_subelement(self.doc.Name, support.Name, "face", {"geometry_type": "cylinder"})["selection"]
        vertex = geometry.list_subelements(self.doc.Name, support.Name, "vertex", limit=1)["items"][0]["selection"]
        self.assertEqual(self.doc.getObject(design.create_datum(self.body.Name, "plane", support_selection=planar)["name"]).MapMode, "FlatFace")
        cylindrical = geometry.select_subelement(self.doc.Name, support.Name, "face", {"geometry_type": "cylinder"})["selection"]
        self.assertEqual(self.doc.getObject(design.create_datum(self.body.Name, "axis", support_selection=cylindrical)["name"]).MapMode, "Concentric")
        vertex = geometry.list_subelements(self.doc.Name, support.Name, "vertex", limit=1)["items"][0]["selection"]
        self.assertEqual(self.doc.getObject(design.create_datum(self.body.Name, "point", support_selection=vertex)["name"]).MapMode, "Translate")

        target_body = self.doc.addObject("PartDesign::Body", "TargetBody")
        sketcher.create_sketch("TargetBase", body_name=target_body.Name)
        sketcher.add_rectangle("TargetBase", -20, -20, 20, 20)
        design.pad("TargetBase", 20, name="TargetPad")
        sketcher.create_sketch("FirstPocketProfile", offset=20, body_name=target_body.Name)
        sketcher.add_circle("FirstPocketProfile", 0, 0, 2)
        first = design.pocket("FirstPocketProfile", 1, name="FirstPocket", end_condition="up_to_first")
        self.assertAlmostEqual(first["volume"], 32000 - math.pi * 4 * 20, places=5)

        face_body = self.doc.addObject("PartDesign::Body", "FaceTargetBody")
        sketcher.create_sketch("FaceTargetBase", body_name=face_body.Name)
        sketcher.add_rectangle("FaceTargetBase", -20, -20, 20, 20)
        design.pad("FaceTargetBase", 20, name="FaceTargetPad")
        sketcher.create_sketch("FacePocketProfile", offset=20, body_name=face_body.Name)
        sketcher.add_circle("FacePocketProfile", 0, 0, 2)
        bottom = geometry.select_subelement(self.doc.Name, "FaceTargetPad", "face",
                                            {"geometry_type": "plane", "position": [0, 0, 0]})["selection"]
        face = design.pocket("FacePocketProfile", 1, name="FacePocket",
                             end_condition="up_to_face", target_selection=bottom)
        self.assertAlmostEqual(face["volume"], 32000 - math.pi * 4 * 20, places=5)

    def test_stage6b_two_angle_revolution(self):
        sketcher.create_sketch("RevolutionProfile", body_name=self.body.Name)
        sketcher.add_rectangle("RevolutionProfile", 5, -5, 10, 5)
        result = design.revolution("RevolutionProfile", 90, second_angle=90)
        self.assertTrue(result["shape_valid"])
        self.assertEqual(self.body.Tip.Type, "TwoAngles")
        self.assertAlmostEqual(self.body.Tip.Angle2.Value, 90)
        self.assertAlmostEqual(result["volume"], 375 * math.pi, places=5)

    def test_stage6b_pipe_edge_orientation_and_transition(self):
        self.rectangle("PipeBase", (-20, -20, 20, 20))
        design.pad("PipeBase", 20)
        self.circle("PipeProfile", 3)
        path = self.body.newObject("Sketcher::SketchObject", "PipePath")
        path.Placement = FreeCAD.Placement(FreeCAD.Vector(), FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90))
        path.addGeometry(Part.LineSegment(FreeCAD.Vector(), FreeCAD.Vector(0, 20, 0)), False)
        result = design.subtractive_pipe("PipeProfile", "PipePath", path_edges=["Edge1"],
                                         orientation="frenet", transition="round")
        self.assertTrue(result["shape_valid"])
        self.assertEqual(self.body.Tip.Mode, "Frenet")
        self.assertEqual(self.body.Tip.Transition, "Round corner")
        self.assertAlmostEqual(result["volume"], 32000 - math.pi * 9 * 20, places=5)

    def test_stage6c_hole_chamfer_thickness_and_edit(self):
        self.rectangle("HoleBase", (-20, -20, 20, 20))
        design.pad("HoleBase", 20)
        self.circle("CounterboreProfile", 3, offset=20)
        result = design.hole("CounterboreProfile", 6, 12, cut_type="counterbore",
                             cut_diameter=10, cut_depth=3)
        self.assertTrue(result["shape_valid"])
        self.assertEqual(self.body.Tip.HoleCutType, "Counterbore")
        self.assertAlmostEqual(self.body.Tip.HoleCutDiameter.Value, 10)
        edited = design.edit_feature(self.body.Tip.Name, parameters={"depth": 15})
        self.assertEqual(edited["tip"], self.body.Tip.Name)
        self.assertAlmostEqual(self.body.Tip.Depth.Value, 15)

        second_body = self.doc.addObject("PartDesign::Body", "DressupBody")
        sketcher.create_sketch("DressupProfile", body_name=second_body.Name)
        sketcher.add_rectangle("DressupProfile", -10, -10, 10, 10)
        design.pad("DressupProfile", 20, name="DressupPad")
        chamfered = design.chamfer("DressupPad", ["Edge1"], 1, second_size=0.5)
        self.assertTrue(chamfered["shape_valid"])
        self.assertEqual(second_body.Tip.ChamferType, "Two distances")

        third_body = self.doc.addObject("PartDesign::Body", "ThicknessBody")
        sketcher.create_sketch("ThicknessProfile", body_name=third_body.Name)
        sketcher.add_rectangle("ThicknessProfile", -10, -10, 10, 10)
        design.pad("ThicknessProfile", 20, name="ThicknessPad")
        top = max(range(1, len(self.doc.ThicknessPad.Shape.Faces) + 1),
                  key=lambda index: self.doc.ThicknessPad.Shape.Faces[index - 1].CenterOfMass.z)
        thickened = design.thickness("ThicknessPad", [f"Face{top}"], 1,
                                     direction="outside", join="intersection")
        self.assertTrue(thickened["shape_valid"])
        self.assertTrue(third_body.Tip.Reversed)
        self.assertEqual(third_body.Tip.Join, "Intersection")

    def test_stage6c_multi_transform_chain(self):
        self.rectangle("PatternBase", (-20, -10, 20, 10))
        design.pad("PatternBase", 10)
        self.circle("PatternHole", 1, offset=10, center=(-15, 5))
        design.pocket("PatternHole", 10, through_all=True)
        result = design.multi_transform(
            [self.body.Tip.Name],
            [{"type": "mirrored", "plane": "XZ"},
             {"type": "linear", "direction": "X", "length": 30, "occurrences": 4}],
        )
        self.assertTrue(result["shape_valid"])
        self.assertEqual(self.body.Tip.TypeId, "PartDesign::MultiTransform")
        self.assertEqual(len(self.body.Tip.Transformations), 2)
        self.assertEqual(len(self.body.Tip.Shape.Solids), 1)
        self.assertAlmostEqual(result["volume"], 8000 - 8 * math.pi * 10, places=4)

    def test_sketch_degrees_of_freedom_and_lock(self):
        sketcher.create_sketch("FreeLine")
        result = sketcher.add_line("FreeLine", 2, 3, 10, 8)
        self.assertEqual(result["degrees_of_freedom"], 4)
        self.assertFalse(result["fully_constrained"])
        result = sketcher.add_constraint_lock("FreeLine", 0, 1)
        self.assertEqual(result["degrees_of_freedom"], 2)
        result = sketcher.add_constraint_lock("FreeLine", 0, 2)
        self.assertEqual(result["degrees_of_freedom"], 0)
        self.assertTrue(result["fully_constrained"])

    def test_lock_point_at_origin(self):
        sketcher.create_sketch("OriginLine")
        sketcher.add_line("OriginLine", 0, 0, 10, 8)
        result = sketcher.add_constraint_lock("OriginLine", 0, 1)
        self.assertEqual(result["degrees_of_freedom"], 2)

    def test_sketch_plane_offsets(self):
        for plane, expected in [("XY", (0, 0, 7)), ("XZ", (0, 7, 0)), ("YZ", (7, 0, 0))]:
            result = sketcher.create_sketch("Offset" + plane, plane=plane, offset=7)
            self.assertEqual(tuple(self.doc.getObject(result["name"]).Placement.Base), expected)

    def test_slot_is_closed_and_constrained(self):
        sketcher.create_sketch("Slot", body_name=self.body.Name)
        result = sketcher.add_slot("Slot", 0, 0, 20, 10, 3)
        self.assertEqual(result["degrees_of_freedom"], 5)
        result = design.pad("Slot", 5)
        self.assertAlmostEqual(result["volume"], (math.sqrt(500) * 6 + math.pi * 9) * 5, places=5)

    def test_stage5_reference_profiles_are_fully_constrained_and_editable(self):
        sketcher.create_sketch("HousingProfile")
        result = sketcher.add_rectangle("HousingProfile", -40, -25, 40, 25)
        self.assertEqual(result["degrees_of_freedom"], 4)
        sketcher.add_constraint_lock("HousingProfile", 0, 1)
        width = sketcher.add_constraint_length("HousingProfile", 0, 80)["constraint_index"]
        result = sketcher.add_constraint_length("HousingProfile", 1, 50)
        self.assertTrue(result["fully_constrained"])
        self.assertFalse(any(item["type"] == "Block" for item in sketcher.get_sketch_info("HousingProfile")["constraints"]))
        sketcher.set_constraint_value("HousingProfile", width, 100)
        housing_line = self.doc.HousingProfile.Geometry[0]
        self.assertAlmostEqual((housing_line.EndPoint - housing_line.StartPoint).Length, 100)

        sketcher.create_sketch("FlangeProfile")
        points = [[0, 0], [30, 0], [30, 8], [10, 8], [10, 48], [0, 48]]
        sketcher.add_polygon("FlangeProfile", points, True)
        for index in [0, 2, 4]:
            sketcher.add_constraint_horizontal("FlangeProfile", index)
        for index in [1, 3, 5]:
            sketcher.add_constraint_vertical("FlangeProfile", index)
        sketcher.add_constraint_lock("FlangeProfile", 0, 1)
        sketcher.add_constraint_length("FlangeProfile", 0, 30)
        sketcher.add_constraint_length("FlangeProfile", 1, 8)
        sketcher.add_constraint_length("FlangeProfile", 2, 20)
        shaft_length = sketcher.add_constraint_length("FlangeProfile", 3, 40)["constraint_index"]
        info = sketcher.get_sketch_info("FlangeProfile")
        self.assertTrue(info["fully_constrained"])
        self.assertFalse(any(item["type"] == "Block" for item in info["constraints"]))
        sketcher.set_constraint_value("FlangeProfile", shaft_length, 50)
        shaft_line = self.doc.FlangeProfile.Geometry[3]
        self.assertAlmostEqual((shaft_line.EndPoint - shaft_line.StartPoint).Length, 50)

    def test_stage5_crud_modes_and_conflict_rollback(self):
        import json
        from freecad_ai_bridge.gui_executor import GuiExecutor

        sketcher.create_sketch("Editable")
        sketcher.add_line("Editable", 0, 0, 10, 2)
        sketcher.move_geometry_point("Editable", 0, 2, 12, 4)
        self.assertEqual(tuple(self.doc.Editable.Geometry[0].EndPoint)[:2], (12, 4))
        sketcher.set_geometry_construction("Editable", 0, True)
        constraint = sketcher.add_constraint_distance_x("Editable", 0, 2, 12)["constraint_index"]
        self.assertFalse(sketcher.set_constraint_mode("Editable", constraint, driving=False)["driving"])
        self.assertFalse(sketcher.set_constraint_mode("Editable", constraint, active=False)["active"])
        sketcher.delete_constraint("Editable", constraint)
        sketcher.delete_geometry("Editable", 0)
        self.assertEqual(self.doc.Editable.GeometryCount, 0)

        sketcher.create_sketch("Rollback")
        sketcher.add_line("Rollback", 0, 0, 10, 0)
        sketcher.add_constraint_horizontal("Rollback", 0)
        before = sketcher.get_sketch_info("Rollback")
        executor = GuiExecutor()
        with self.assertRaises(ValueError):
            executor._execute_function("freecad_ai_bridge.sketcher_ops", "add_constraint_horizontal",
                                       json.dumps({"doc_name": self.doc.Name, "sketch_name": "Rollback", "geo_idx": 0}))
        after = sketcher.get_sketch_info("Rollback")
        self.assertEqual(after, before)
        self.assertFalse(self.doc.HasPendingTransaction)

    def test_stage5_references_attachment_and_drawing_operations(self):
        from freecad_ai_bridge import geometry_ops as geometry

        box = self.doc.addObject("Part::Feature", "ReferenceBox")
        box.Shape = Part.makeBox(10, 10, 10)
        sketcher.create_sketch("ReferenceSketch")
        edge = geometry.list_subelements(self.doc.Name, box.Name, "edge")["items"][0]["selection"]
        result = sketcher.add_external_geometry("ReferenceSketch", edge)
        self.assertEqual((result["external_index"], result["geometry_index"]), (0, -3))
        sketcher.delete_external_geometry("ReferenceSketch", 0)
        face = geometry.list_subelements(self.doc.Name, box.Name, "face",
                                         {"geometry_type": "plane"})["items"][0]["selection"]
        result = sketcher.set_sketch_attachment("ReferenceSketch", support_selection=face,
                                                offset_z=2, rotation_z=15)
        self.assertEqual(result["map_mode"], "FlatFace")
        attachment = sketcher.get_sketch_info("ReferenceSketch")["attachment"]
        self.assertEqual(attachment["offset"]["position"], [0, 0, 2])
        self.assertAlmostEqual(attachment["offset"]["rotation_xyzw"][2], math.sin(math.radians(7.5)))
        sketcher.set_sketch_attachment("ReferenceSketch")

        sketcher.create_sketch("EditSketch")
        sketcher.add_line("EditSketch", 0, 0, 5, 0)
        sketcher.extend_geometry("EditSketch", 0, 3, 2)
        self.assertAlmostEqual(self.doc.EditSketch.Geometry[0].EndPoint.x, 8)
        copied = sketcher.copy_geometry("EditSketch", [0], 10, 2)
        mirrored = sketcher.mirror_geometry("EditSketch", [0], -2)
        self.assertEqual(copied["geometry_indices"], [1])
        self.assertEqual(mirrored["geometry_indices"], [2])

        sketcher.create_sketch("FilletSketch")
        sketcher.add_line("FilletSketch", 0, 0, 10, 0)
        sketcher.add_line("FilletSketch", 10, 0, 10, 10)
        result = sketcher.fillet_geometry("FilletSketch", 0, 1, 9, 0, 10, 1, 2)
        self.assertEqual(result["geometry_indices"], [2])
        sketcher.create_sketch("TrimSketch")
        sketcher.add_line("TrimSketch", 0, 0, 10, 0)
        sketcher.add_line("TrimSketch", 5, -5, 5, 5)
        result = sketcher.trim_geometry("TrimSketch", 0, 5, 0)
        self.assertEqual(result["geometry_count"], 1)

    def test_additive_loft(self):
        self.circle("Lower", 10)
        self.circle("Upper", 5, offset=20)
        result = design.loft(["Lower", "Upper"])
        self.assertTrue(result["shape_valid"])
        self.assertAlmostEqual(result["volume"], math.pi * 20 * 175 / 3, places=5)

    def test_completed_part_dressups_remain_parametric(self):
        for operation in [part.part_fillet, part.part_chamfer]:
            box = part.make_box(20, 20, 20, name="Box")
            result = operation(box["name"], ["Edge1"], 1)
            feature = self.doc.getObject(result["name"])
            self.assertTrue(feature.Shape.isValid())
            self.assertGreater(len(feature.Edges), 0)
            volume = feature.Shape.Volume
            self.doc.getObject(box["name"]).Height = 30
            self.doc.recompute()
            self.assertGreater(feature.Shape.Volume, volume)
            self.assertNotIn("Invalid", feature.State)

    def test_completed_rotation_axes(self):
        part.make_box(10, 20, 30)
        part.set_placement("Box", rx=90)
        rotated = self.doc.Box.Placement.Rotation.multVec(FreeCAD.Vector(0, 1, 0))
        self.assertAlmostEqual(rotated.z, 1)
        self.assertAlmostEqual(rotated.x, 0)

    def test_completed_threaded_hole(self):
        self.rectangle("Profile", (-20, -20, 20, 20))
        design.pad("Profile", 20)
        self.circle("HoleProfile", 3, offset=20)
        result = design.hole("HoleProfile", 6, 12, threaded=True)
        self.assertTrue(result["shape_valid"])
        self.assertEqual(self.body.Tip.ThreadType, "ISOMetricProfile")
        self.assertEqual(self.body.Tip.ThreadSize, "M6x1.0")

    def test_completed_subtractive_loft(self):
        self.rectangle("Profile", (-20, -20, 20, 20))
        design.pad("Profile", 20)
        self.circle("Lower", 3)
        self.circle("Upper", 5, offset=20)
        result = design.subtractive_loft(["Lower", "Upper"])
        self.assertAlmostEqual(result["volume"], 32000 - math.pi * 20 * 49 / 3, places=5)

    def test_completed_subtractive_pipe(self):
        self.rectangle("Profile", (-20, -20, 20, 20))
        design.pad("Profile", 20)
        self.circle("CutProfile", 3)
        path = self.body.newObject("Sketcher::SketchObject", "Path")
        path.Placement = FreeCAD.Placement(FreeCAD.Vector(), FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90))
        path.addGeometry(Part.LineSegment(FreeCAD.Vector(), FreeCAD.Vector(0, 20, 0)), False)
        result = design.subtractive_pipe("CutProfile", "Path")
        self.assertAlmostEqual(result["volume"], 32000 - math.pi * 9 * 20, places=5)

    def test_completed_draft(self):
        self.rectangle("Profile", (-10, -10, 10, 10))
        design.pad("Profile", 20)
        faces = self.doc.Pad.Shape.Faces
        bottom = next(index for index, face in enumerate(faces, 1) if abs(face.CenterOfMass.z) < 1e-7)
        side = next(index for index, face in enumerate(faces, 1) if abs(face.CenterOfMass.z - 10) < 1e-7)
        result = design.draft("Pad", [f"Face{side}"], 3, plane_name=f"Pad.Face{bottom}")
        self.assertTrue(result["shape_valid"])
        self.assertNotAlmostEqual(result["volume"], 8000)

    def test_rpc_undo_redo_and_rollback(self):
        from freecad_ai_bridge.gui_executor import GuiExecutor

        executor = GuiExecutor()
        executor._execute_function("freecad_ai_bridge.part_ops", "make_box",
                                   json.dumps({"length": 10, "width": 20, "height": 30, "name": "UndoBox"}))
        self.assertIsNotNone(self.doc.getObject("UndoBox"))
        view.undo()
        self.assertIsNone(self.doc.getObject("UndoBox"))
        view.redo()
        self.assertAlmostEqual(self.doc.UndoBox.Shape.Volume, 6000)
        rollback_doc = FreeCAD.newDocument("MCP_Rollback_Test")
        try:
            rollback_body = rollback_doc.addObject("PartDesign::Body", "Body")
            sketcher.create_sketch("Profile", body_name=rollback_body.Name, doc_name=rollback_doc.Name)
            sketcher.add_line("Profile", 0, 0, 10, 0, doc_name=rollback_doc.Name)
            count = len(rollback_doc.Objects)
            with self.assertRaises(Exception):
                executor._execute_function("freecad_ai_bridge.partdesign_ops", "pad",
                                           json.dumps({"doc_name": rollback_doc.Name,
                                                       "sketch_name": "Profile", "length": 10,
                                                       "name": "InvalidPad"}))
            self.assertEqual(len(rollback_doc.Objects), count)
            self.assertFalse(rollback_doc.HasPendingTransaction)
        finally:
            FreeCAD.closeDocument(rollback_doc.Name)
            FreeCAD.setActiveDocument(self.doc.Name)

    def test_rpc_close_document(self):
        from freecad_ai_bridge.gui_executor import GuiExecutor

        temporary = FreeCAD.newDocument("MCP_Close_Test")
        name = temporary.Name
        result = GuiExecutor()._execute_function("freecad_ai_bridge.operations", "close_document",
                                                json.dumps({"name": name}))
        self.assertEqual(result["closed"], name)
        self.assertNotIn(name, FreeCAD.listDocuments())
        FreeCAD.setActiveDocument(self.doc.Name)

    def test_export_stl_and_obj_roundtrip(self):
        import Mesh

        self.plate_with_hole()
        with tempfile.TemporaryDirectory() as directory:
            for extension, exporter in [("stl", view.export_stl), ("obj", view.export_obj)]:
                path = str(Path(directory) / ("test." + extension))
                result = exporter(path)
                self.assertEqual(result["objects_exported"], 1)
                mesh = Mesh.Mesh(path)
                self.assertGreater(mesh.CountFacets, 12)
                self.assertTrue(mesh.isSolid())
                self.assertAlmostEqual(mesh.Volume, self.body.Shape.Volume, delta=5)

    def test_export_step_roundtrip(self):
        self.plate_with_hole()
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "test.step")
            result = view.export_step(path)
            self.assertEqual(result["objects_exported"], 1)
            shape = Part.read(path)
            self.assertTrue(shape.isValid())
            self.assertEqual(len(shape.Solids), 1)
            self.assertAlmostEqual(shape.Volume, self.body.Shape.Volume, places=4)

    def test_export_empty_selection_fails(self):
        self.plate_with_hole()
        with self.assertRaises(ValueError):
            view.export_stl("unused.stl", obj_names=[])

    def test_export_hidden_body_is_excluded(self):
        self.plate_with_hole()
        self.body.Visibility = False
        with self.assertRaises(ValueError):
            view.export_step("unused.step")

    def test_loft_rejects_unsupported_shell_before_creation(self):
        count = len(self.doc.Objects)
        with self.assertRaises(ValueError):
            design.loft([], solid=False)
        self.assertEqual(len(self.doc.Objects), count)

    def test_linear_pattern(self):
        self.plate_with_hole()
        result = design.linear_pattern("Pocket", direction="Y", length=12, occurrences=2)
        self.assertEqual(self.body.Tip.Direction[0].Role, "Y_Axis")
        self.assertAlmostEqual(result["volume"], 36000 - 2 * math.pi * 4 * 10, places=5)
        self.assertFalse(self.doc.Pocket.Visibility)

    def test_polar_pattern(self):
        self.plate_with_hole()
        result = design.polar_pattern("Pocket", axis="Z", occurrences=4)
        self.assertEqual(self.body.Tip.Axis[0].Role, "Z_Axis")
        self.assertAlmostEqual(result["volume"], 36000 - 4 * math.pi * 4 * 10, places=5)

    def test_mirrored(self):
        self.plate_with_hole()
        result = design.mirrored("Pocket", plane="YZ")
        self.assertEqual(self.body.Tip.MirrorPlane[0].Role, "YZ_Plane")
        self.assertAlmostEqual(result["volume"], 36000 - 2 * math.pi * 4 * 10, places=5)

    def test_additive_sweep(self):
        self.circle("Profile", 3)
        path = self.body.newObject("Sketcher::SketchObject", "Path")
        path.Placement = FreeCAD.Placement(FreeCAD.Vector(), FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90))
        path.addGeometry(Part.LineSegment(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 20, 0)), False)
        result = design.sweep("Profile", "Path")
        self.assertAlmostEqual(result["volume"], math.pi * 9 * 20, places=5)


def run_tests(pattern="test_*"):
    stream = io.StringIO()
    names = unittest.defaultTestLoader.getTestCaseNames(FreeCADIntegrationTests)
    suite = unittest.TestSuite(
        FreeCADIntegrationTests(name) for name in names if fnmatch.fnmatch(name, pattern)
    )
    outcome = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return {"success": outcome.wasSuccessful(), "tests": outcome.testsRun, "output": stream.getvalue()}