"""Parametric workshop vise demo. Run build_model() inside the FreeCAD GUI.

Units: mm. Demonstration assembly, not a load-rated manufacturing design.
The spindle uses a simplified trapezoidal thread without standard tolerances.
"""

from datetime import datetime
import math
from pathlib import Path

import FreeCAD
import FreeCADGui
import Part

from freecad_ai_bridge import partdesign_ops as design
from freecad_ai_bridge import sketcher_ops as sketcher
from freecad_ai_bridge import view_ops as view


VECTOR = FreeCAD.Vector
TEAL = (0.12, 0.43, 0.40)
STEEL = (0.72, 0.76, 0.79)
DARK_STEEL = (0.24, 0.28, 0.31)
BLACK = (0.10, 0.12, 0.14)
BRASS = (0.76, 0.56, 0.24)
DOCUMENT_NAME = None


def document():
    if DOCUMENT_NAME is None:
        raise RuntimeError("Run build_frame() first")
    doc = FreeCAD.getDocument(DOCUMENT_NAME)
    FreeCAD.setActiveDocument(doc.Name)
    return doc


def body(name, label, color):
    doc = document()
    component = doc.addObject("PartDesign::Body", name)
    component.Label = label
    component.ViewObject.ShapeColor = color
    doc.Assembly.addObject(component)
    return component


def finish_body(component, color):
    for feature in component.Group:
        if feature.ViewObject:
            feature.Visibility = False
    component.Tip.Visibility = True
    component.Tip.ViewObject.ShapeColor = color
    component.Tip.ViewObject.LineColor = (0.12, 0.14, 0.15)
    component.Tip.ViewObject.DisplayMode = "Flat Lines"
    component.Visibility = True
    if component.Shape.isNull() or not component.Shape.isValid() or len(component.Shape.Solids) != 1:
        raise ValueError(f"Invalid body: {component.Name}")


def rectangle(component, suffix, bounds, offset, plane="XY"):
    name = component.Name + suffix
    sketcher.create_sketch(name, plane=plane, offset=offset, body_name=component.Name)
    indices = sketcher.add_rectangle(name, *bounds)["geometry_indices"]
    sketcher.add_constraint_lock(name, indices[0], 1)
    sketcher.add_constraint_distance(name, indices[0], 1, indices[0], 2, bounds[2] - bounds[0])
    sketcher.add_constraint_distance(name, indices[1], 1, indices[1], 2, bounds[3] - bounds[1])
    return name


def circles(component, suffix, centers, offset, plane="YZ"):
    name = component.Name + suffix
    sketcher.create_sketch(name, plane=plane, offset=offset, body_name=component.Name)
    for center_x, center_y, radius in centers:
        index = sketcher.add_circle(name, center_x, center_y, radius)["geometry_index"]
        sketcher.add_constraint_lock(name, index, 3)
        sketcher.add_constraint_radius(name, index, radius)
    return name


def solid_feature(name, label, shape, color, group="Hardware"):
    doc = document()
    if shape.isNull() or not shape.isValid() or len(shape.Solids) != 1:
        raise ValueError(f"Invalid solid: {name}")
    feature = doc.addObject("Part::Feature", name)
    feature.Label = label
    feature.Shape = shape
    getattr(doc, group).addObject(feature)
    feature.ViewObject.ShapeColor = color
    feature.ViewObject.LineColor = (0.12, 0.14, 0.15)
    feature.ViewObject.DisplayMode = "Flat Lines"
    return feature


def summary():
    doc = document()
    solids = [obj for obj in doc.Objects if obj.TypeId == "PartDesign::Body"
              or (obj.TypeId == "Part::Feature" and obj.ViewObject.Visibility)]
    return {"document": doc.Name, "objects": len(doc.Objects), "components": len(solids),
            "all_valid": all(obj.Shape.isValid() and len(obj.Shape.Solids) == 1 for obj in solids)}


def build_frame():
    global DOCUMENT_NAME
    doc = FreeCAD.newDocument("Praezisions_Schraubstock_MCP")
    DOCUMENT_NAME = doc.Name
    doc.Label = "Praezisions-Schraubstock | MCP Demo"
    assembly = doc.addObject("App::Part", "Assembly")
    assembly.Label = "Schraubstock 190 x 100 mm"
    for name, label in [("Guides", "Fuehrungswellen"), ("Hardware", "Spindel und Verbindungselemente")]:
        group = doc.addObject("App::Part", name)
        group.Label = label
        assembly.addObject(group)
    parameters = doc.addObject("Spreadsheet::Sheet", "Parameters")
    parameters.Label = "Hauptabmessungen (mm)"
    for row, (label, value, alias) in enumerate([
        ("Grundplattenlaenge", "190", "BaseLength"),
        ("Grundplattenbreite", "100", "BaseWidth"),
        ("Grundplattenstaerke", "12", "BaseThickness"),
        ("Backenbreite", "78", "JawWidth"),
        ("Backenoeffnung (Darstellung)", "58", "JawGap"),
        ("Fuehrungsdurchmesser", "12", "GuideDiameter"),
        ("Spindelsteigung (vereinfacht)", "3.5", "ThreadPitch"),
    ], 1):
        parameters.set(f"A{row}", label)
        parameters.set(f"B{row}", value)
        parameters.setAlias(f"B{row}", alias)
    parameters.setColumnWidth("A", 260)

    base = body("Base", "01 | Grundplatte mit vier Spannlangloechern", TEAL)
    profile = rectangle(base, "Profile", (-95, -50, 95, 50), 0)
    design.pad(profile, 12, name="BasePad")
    doc.BasePad.setExpression("Length", "Parameters.BaseThickness")
    vertical = [f"Edge{index}" for index, edge in enumerate(doc.BasePad.Shape.Edges, 1)
                if abs(edge.BoundBox.ZLength - 12) < 1e-7]
    design.fillet("BasePad", vertical, 4, name="BaseCorners")
    slots = sketcher.create_sketch("MountingSlots", offset=12, body_name=base.Name)["name"]
    for center_x in [-77, 77]:
        for center_y in [-43, 43]:
            indices = sketcher.add_slot(slots, center_x - 5, center_y, center_x + 5, center_y, 3.5)["geometry_indices"]
            sketcher.add_constraint_lock(slots, indices[2], 3)
            sketcher.add_constraint_lock(slots, indices[3], 3)
            sketcher.add_constraint_radius(slots, indices[2], 3.5)
    design.pocket(slots, 12, through_all=True, name="MountingSlotCut")
    top_edges = [f"Edge{index}" for index, edge in enumerate(doc.MountingSlotCut.Shape.Edges, 1)
                 if abs(edge.BoundBox.ZMin - 12) < 1e-7 and abs(edge.BoundBox.ZMax - 12) < 1e-7]
    design.chamfer("MountingSlotCut", top_edges, 0.6, name="BaseEdgeBreak")
    finish_body(base, TEAL)

    fixed = body("FixedJaw", "02 | Feste Backe", TEAL)
    profile = rectangle(fixed, "FootProfile", (-76, -39, -40, 39), 12)
    design.pad(profile, 16, name="FixedFoot")
    profile = rectangle(fixed, "UprightProfile", (-74, -39, -50, 39), 28)
    design.pad(profile, 38, name="FixedUpright")
    holes = circles(fixed, "GuideBores", [(-23, -24, 6), (-23, 24, 6)], -40)
    design.pocket(holes, 36, name="FixedGuideSeats")
    finish_body(fixed, TEAL)

    moving = body("MovingJaw", "03 | Bewegliche Backe und Schlitten", STEEL)
    profile = rectangle(moving, "CarriageProfile", (16, -39, 49, 39), 12)
    design.pad(profile, 24, name="CarriagePad")
    profile = rectangle(moving, "UprightProfile", (16, -39, 37, 39), 36)
    design.pad(profile, 30, name="MovingUpright")
    bores = circles(moving, "BoreProfile", [(-23, -24, 6.15), (-23, 24, 6.15), (-28, 0, 8.1)], 49)
    design.pocket(bores, 33, name="CarriageBores")
    finish_body(moving, STEEL)

    support = body("EndSupport", "04 | Spindel-Lagerbock", TEAL)
    profile = rectangle(support, "Profile", (67, -39, 83, 39), 12)
    design.pad(profile, 31, name="SupportPad")
    bores = circles(support, "BoreProfile", [(-23, -24, 6), (-23, 24, 6), (-28, 0, 6.6)], 83)
    design.pocket(bores, 16, name="SupportBores")
    finish_body(support, TEAL)
    doc.recompute()
    return summary()


def build_details():
    doc = document()
    for name, label, origin, front, reverse in [
        ("FixedPlate", "05 | Gehaertete feste Spannbacke", -50, -46, False),
        ("MovingPlate", "06 | Gehaertete bewegliche Spannbacke", 12, 12, True),
    ]:
        plate = body(name, label, DARK_STEEL)
        profile = rectangle(plate, "Profile", (-65, -39, -44, 39), origin, plane="YZ")
        design.pad(profile, 4, name=name + "Pad")
        groove_bounds = ((front - 0.8, -35.4, front + 0.1, -34.6) if not reverse
                         else (front - 0.1, -35.4, front + 0.8, -34.6))
        groove = rectangle(plate, "GrooveProfile", groove_bounds, 65)
        design.pocket(groove, 21, name=name + "FirstGroove")
        design.linear_pattern(name + "FirstGroove", direction="Y", length=70, occurrences=15,
                              name=name + "Serrations")
        holes = circles(plate, "ScrewHoles", [(-54.5, -25, 2.7), (-54.5, 25, 2.7)], front)
        design.pocket(holes, 4, reversed=reverse, name=name + "Drillings")
        recesses = circles(plate, "RecessProfile", [(-54.5, -25, 4.4), (-54.5, 25, 4.4)], front)
        design.pocket(recesses, 1.5, reversed=reverse, name=name + "Counterbores")
        finish_body(plate, DARK_STEEL)
        for number, center_y in enumerate([-25, 25], 1):
            direction = VECTOR(1, 0, 0) if reverse else VECTOR(-1, 0, 0)
            start = VECTOR(front, center_y, 54.5)
            head = Part.makeCylinder(4.2, 1.3, start, direction)
            shank = Part.makeCylinder(2.5, 12, start, direction)
            vertices = [VECTOR(front, center_y + 2 * math.cos(index * math.pi / 3),
                               54.5 + 2 * math.sin(index * math.pi / 3)) for index in range(6)]
            socket = Part.Face(Part.makePolygon(vertices + [vertices[0]])).extrude(direction * 1.1)
            bolt = head.fuse(shank).cut(socket).removeSplitter()
            solid_feature(name + f"Screw{number}", "M5 | Innensechskantschraube", bolt, BLACK)

    for number, center_y in enumerate([-24, 24], 1):
        rail = Part.makeCylinder(6, 155, VECTOR(-74, center_y, 23), VECTOR(1, 0, 0))
        solid_feature(f"GuideRail{number}", f"Fuehrungswelle {number} | D12", rail, STEEL, "Guides")
    nut = Part.makeCylinder(8, 29, VECTOR(18, 0, 28), VECTOR(1, 0, 0)).cut(
        Part.makeCylinder(6.5, 29, VECTOR(18, 0, 28), VECTOR(1, 0, 0)))
    solid_feature("SpindleNut", "07 | Bronzemutter (Gewinde vereinfacht)", nut, BRASS)
    collar = Part.makeCylinder(9, 8, VECTOR(83, 0, 28), VECTOR(1, 0, 0)).cut(
        Part.makeCylinder(5.3, 8, VECTOR(83, 0, 28), VECTOR(1, 0, 0)))
    solid_feature("ThrustCollar", "08 | Anlaufring", collar, BRASS)
    doc.recompute()
    return summary()


def build_spindle():
    doc = document()
    pitch = float(doc.Parameters.get("B7"))
    helix = Part.makeHelix(pitch, 98, 5.5)
    section_points = [VECTOR(5.1, 0, -1.05), VECTOR(6.4, 0, -0.5),
                      VECTOR(6.4, 0, 0.5), VECTOR(5.1, 0, 1.05)]
    section = Part.Wire(Part.makePolygon(section_points + [section_points[0]]).Edges)
    thread = Part.Wire(helix.Edges).makePipeShell([section], True, True)
    thread.rotate(VECTOR(), VECTOR(0, 1, 0), 90)
    thread.translate(VECTOR(-36, 0, 28))
    core = Part.makeCylinder(5.2, 142, VECTOR(-38, 0, 28), VECTOR(1, 0, 0))
    spindle = solid_feature("LeadScrew", "09 | Spindel mit modellierter Gewindehelix", core.fuse(thread).removeSplitter(), STEEL)
    spindle.addProperty("App::PropertyLength", "Pitch", "Thread")
    spindle.Pitch = pitch
    spindle.addProperty("App::PropertyString", "Specification", "Thread")
    spindle.Specification = "Simplified trapezoidal profile; no manufacturing tolerance"
    hub = Part.makeCylinder(10, 14, VECTOR(96, 0, 28), VECTOR(1, 0, 0))
    hub = hub.cut(Part.makeCylinder(3.2, 30, VECTOR(103, -15, 28), VECTOR(0, 1, 0)))
    solid_feature("HandleHub", "10 | Gleitgriff-Nabe", hub, DARK_STEEL)
    handle = Part.makeCylinder(3, 90, VECTOR(103, -45, 28), VECTOR(0, 1, 0))
    handle = handle.fuse(Part.makeSphere(5, VECTOR(103, -45, 28)))
    handle = handle.fuse(Part.makeSphere(5, VECTOR(103, 45, 28))).removeSplitter()
    solid_feature("SlidingHandle", "11 | Knebel mit Kugelenden", handle, STEEL)
    doc.recompute()
    return summary()


def save_model():
    doc = document()
    invalid = [obj.Name for obj in doc.Objects if "Invalid" in obj.State]
    if invalid:
        raise ValueError(f"Invalid document objects: {invalid}")
    unconstrained = [obj.Name for obj in doc.Objects
                     if obj.TypeId == "Sketcher::SketchObject" and not obj.FullyConstrained]
    if unconstrained:
        raise ValueError(f"Unconstrained sketches: {unconstrained}")
    output = Path(__file__).resolve().parents[1] / "examples"
    stem = "Praezisions_Schraubstock_MCP"
    if (output / (stem + ".FCStd")).exists():
        stem += "_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = {extension: str(output / (stem + "." + extension)) for extension in ["FCStd", "step", "stl", "png"]}
    active_view = FreeCADGui.activeDocument().activeView()
    active_view.viewIsometric()
    doc.recompute()
    FreeCADGui.updateGui()
    active_view.fitAll()
    FreeCADGui.updateGui()
    doc.recompute()
    doc.saveAs(paths["FCStd"])
    view.export_step(paths["step"], doc_name=doc.Name)
    view.export_stl(paths["stl"], doc_name=doc.Name)
    FreeCADGui.updateGui()
    active_view.fitAll()
    FreeCADGui.updateGui()
    active_view.saveImage(paths["png"], 1600, 1000, "White")
    return {**summary(), "fully_constrained_sketches": sum(obj.TypeId == "Sketcher::SketchObject" for obj in doc.Objects),
            "paths": paths}


def build_model():
    build_frame()
    build_details()
    build_spindle()
    return save_model()


if __name__ == "__main__":
    result = build_model()