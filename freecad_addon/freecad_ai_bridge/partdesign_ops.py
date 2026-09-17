"""PartDesign operations running inside FreeCAD.

Provides Body creation, feature operations (Pad, Pocket, Revolution, etc.),
and pattern operations.
"""

import FreeCAD
import FreeCADGui
from FreeCAD import Vector


def _get_doc(doc_name=None):
    doc = FreeCAD.getDocument(doc_name) if doc_name else FreeCAD.ActiveDocument
    if not doc:
        raise ValueError("No active document")
    return doc


def _get_object(name, doc_name=None):
    doc = _get_doc(doc_name)
    obj = doc.getObject(name)
    if not obj:
        raise ValueError(f"Object '{name}' not found")
    return obj


# =============================================================================
# Body
# =============================================================================


def create_body(name: str = "Body", doc_name: str = None) -> dict:
    """Create a new PartDesign Body."""
    doc = _get_doc(doc_name)
    body = doc.addObject("PartDesign::Body", name)
    doc.recompute()
    return {"name": body.Name, "label": body.Label}


# =============================================================================
# Additive Features
# =============================================================================


def pad(sketch_name: str, length: float, name: str = "Pad",
        symmetric: bool = False, reversed: bool = False,
        doc_name: str = None) -> dict:
    """Pad (extrude) a sketch.

    Args:
        sketch_name: Name of the sketch to pad
        length: Extrusion length
        symmetric: If True, pad symmetrically in both directions
        reversed: If True, pad in reverse direction
    """
    doc = _get_doc(doc_name)
    sketch = _get_object(sketch_name, doc_name)

    pad_obj = doc.addObject("PartDesign::Pad", name)
    pad_obj.Profile = sketch
    pad_obj.Length = length
    if "SideType" in pad_obj.PropertiesList:
        pad_obj.SideType = "Symmetric" if symmetric else "One side"
    else:
        pad_obj.Midplane = symmetric
    if reversed and hasattr(pad_obj, "Reversed"):
        pad_obj.Reversed = reversed

    # Add to body if sketch is in a body
    _add_to_body(sketch, pad_obj, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(pad_obj)


def pocket(sketch_name: str, length: float, name: str = "Pocket",
           through_all: bool = False, reversed: bool = False,
           doc_name: str = None) -> dict:
    """Create a pocket (subtractive extrusion) from a sketch.

    Args:
        sketch_name: Name of the sketch
        length: Depth of pocket (ignored if through_all=True)
        through_all: If True, cut through entire part
        reversed: If True, cut in reverse direction
    """
    doc = _get_doc(doc_name)
    sketch = _get_object(sketch_name, doc_name)

    pocket_obj = doc.addObject("PartDesign::Pocket", name)
    pocket_obj.Profile = sketch
    pocket_obj.Reversed = reversed

    if through_all:
        pocket_obj.Type = 1  # Through All
    else:
        pocket_obj.Type = 0  # Dimension
        pocket_obj.Length = length

    _add_to_body(sketch, pocket_obj, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(pocket_obj)


def revolution(sketch_name: str, angle: float = 360.0, name: str = "Revolution",
               axis: str = "V", reversed: bool = False,
               doc_name: str = None) -> dict:
    """Revolve a sketch around an axis.

    Args:
        sketch_name: Name of the sketch
        angle: Revolution angle in degrees (default 360 = full revolution)
        axis: Axis to revolve around - 'V' (vertical/Y), 'H' (horizontal/X), or 'N' (normal/Z)
        reversed: If True, revolve in reverse direction
    """
    doc = _get_doc(doc_name)
    sketch = _get_object(sketch_name, doc_name)

    rev = doc.addObject("PartDesign::Revolution", name)
    rev.Profile = sketch
    rev.Angle = angle
    rev.Reversed = reversed

    # Set axis
    axis_map = {"V": "V_Axis", "H": "H_Axis", "N": "N_Axis"}
    axis_name = axis_map.get(axis.upper(), "V_Axis")
    rev.ReferenceAxis = (sketch, [axis_name])

    _add_to_body(sketch, rev, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(rev)


def groove(sketch_name: str, angle: float = 360.0, name: str = "Groove",
           axis: str = "V", reversed: bool = False,
           doc_name: str = None) -> dict:
    """Create a groove (subtractive revolution) from a sketch."""
    doc = _get_doc(doc_name)
    sketch = _get_object(sketch_name, doc_name)

    grv = doc.addObject("PartDesign::Groove", name)
    grv.Profile = sketch
    grv.Angle = angle
    grv.Reversed = reversed

    axis_map = {"V": "V_Axis", "H": "H_Axis", "N": "N_Axis"}
    axis_name = axis_map.get(axis.upper(), "V_Axis")
    grv.ReferenceAxis = (sketch, [axis_name])

    _add_to_body(sketch, grv, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(grv)


def loft(sketch_names: list, name: str = "Loft", solid: bool = True,
         ruled: bool = False, closed: bool = False, doc_name: str = None) -> dict:
    """Create a loft between multiple sketches/profiles.

    Args:
        sketch_names: List of sketch names to loft between (in order)
        solid: If True, create a solid (vs. shell)
        ruled: If True, use ruled surfaces
        closed: If True, close the loft (connect last to first)
    """
    if not solid:
        raise ValueError("PartDesign lofts must be solid; use Part for shells")
    if len(sketch_names) < 2:
        raise ValueError("A loft requires at least two profiles")
    doc = _get_doc(doc_name)
    sketches = [_get_object(s, doc_name) for s in sketch_names]

    loft_obj = doc.addObject("PartDesign::AdditiveLoft", name)
    loft_obj.Profile = sketches[0]
    loft_obj.Sections = sketches[1:]
    loft_obj.Ruled = ruled
    loft_obj.Closed = closed

    _add_to_body(sketches[0], loft_obj, doc)

    for s in sketches:
        s.Visibility = False
    doc.recompute()
    return _feature_result(loft_obj)


def sweep(sketch_name: str, spine_name: str, name: str = "Sweep",
          solid: bool = True, doc_name: str = None) -> dict:
    """Sweep a profile along a spine (path).

    Args:
        sketch_name: Profile sketch name
        spine_name: Path/spine sketch or edge name
    """
    if not solid:
        raise ValueError("PartDesign sweeps must be solid; use Part for shells")
    doc = _get_doc(doc_name)
    sketch = _get_object(sketch_name, doc_name)
    spine = _get_object(spine_name, doc_name)

    sweep_obj = doc.addObject("PartDesign::AdditivePipe", name)
    sweep_obj.Profile = sketch
    sweep_obj.Spine = (spine, [])

    _add_to_body(sketch, sweep_obj, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(sweep_obj)


def hole(sketch_name: str, diameter: float, depth: float,
         name: str = "Hole", threaded: bool = False,
         thread_type: str = "ISO", thread_size: str = "M6",
         doc_name: str = None) -> dict:
    """Create a hole feature.

    Args:
        sketch_name: Sketch with center point(s) for hole positions
        diameter: Hole diameter
        depth: Hole depth
        threaded: If True, create threaded hole
        thread_type: Thread standard ('ISO', 'UTS')
        thread_size: Thread size (e.g., 'M6', 'M8')
    """
    doc = _get_doc(doc_name)
    sketch = _get_object(sketch_name, doc_name)

    hole_obj = doc.addObject("PartDesign::Hole", name)
    hole_obj.Profile = sketch
    _add_to_body(sketch, hole_obj, doc)
    doc.recompute()
    hole_obj.Diameter = diameter
    hole_obj.Depth = depth
    hole_obj.Threaded = threaded

    if threaded:
        thread_types = {"ISO": "ISOMetricProfile", "UTS": "UNC"}
        hole_obj.ThreadType = thread_types.get(thread_type, thread_type)
        sizes = hole_obj.getEnumerationsOfProperty("ThreadSize")
        matches = [size for size in sizes if size == thread_size or size.split("x")[0] == thread_size]
        if not matches:
            raise ValueError(f"Unknown thread size '{thread_size}' for {hole_obj.ThreadType}")
        hole_obj.ThreadSize = matches[0]

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(hole_obj)


# =============================================================================
# Subtractive Features
# =============================================================================


def subtractive_loft(sketch_names: list, name: str = "SubtractiveLoft",
                     solid: bool = True, ruled: bool = False,
                     doc_name: str = None) -> dict:
    """Create a subtractive loft (cut) between multiple sketches."""
    if not solid:
        raise ValueError("PartDesign lofts must be solid; use Part for shells")
    if len(sketch_names) < 2:
        raise ValueError("A loft requires at least two profiles")
    doc = _get_doc(doc_name)
    sketches = [_get_object(s, doc_name) for s in sketch_names]

    loft_obj = doc.addObject("PartDesign::SubtractiveLoft", name)
    loft_obj.Profile = sketches[0]
    loft_obj.Sections = sketches[1:]
    loft_obj.Ruled = ruled

    _add_to_body(sketches[0], loft_obj, doc)

    for s in sketches:
        s.Visibility = False
    doc.recompute()
    return _feature_result(loft_obj)


def subtractive_pipe(sketch_name: str, spine_name: str,
                     name: str = "SubtractivePipe", doc_name: str = None) -> dict:
    """Create a subtractive pipe/sweep (cut along path)."""
    doc = _get_doc(doc_name)
    sketch = _get_object(sketch_name, doc_name)
    spine = _get_object(spine_name, doc_name)

    pipe_obj = doc.addObject("PartDesign::SubtractivePipe", name)
    pipe_obj.Profile = sketch
    pipe_obj.Spine = (spine, [])

    _add_to_body(sketch, pipe_obj, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(pipe_obj)


# =============================================================================
# Dress-up Features
# =============================================================================


def fillet(base_name: str, edges: list, radius: float,
           name: str = "Fillet", doc_name: str = None) -> dict:
    """Add fillet to edges of a feature.

    Args:
        base_name: Name of the base feature
        edges: List of edge names, e.g. ["Edge1", "Edge2"]
        radius: Fillet radius
    """
    doc = _get_doc(doc_name)
    base = _get_object(base_name, doc_name)

    from freecad_ai_bridge.geometry_ops import _selection_names

    edges = _selection_names(doc.Name, base.Name, edges, "edge")

    fillet_obj = doc.addObject("PartDesign::Fillet", name)
    fillet_obj.Base = (base, edges)
    fillet_obj.Radius = radius

    _add_to_body(base, fillet_obj, doc)
    doc.recompute()
    return _feature_result(fillet_obj)


def chamfer(base_name: str, edges: list, size: float,
            name: str = "Chamfer", doc_name: str = None) -> dict:
    """Add chamfer to edges of a feature.

    Args:
        base_name: Name of the base feature
        edges: List of edge names, e.g. ["Edge1", "Edge2"]
        size: Chamfer size
    """
    doc = _get_doc(doc_name)
    base = _get_object(base_name, doc_name)

    from freecad_ai_bridge.geometry_ops import _selection_names

    edges = _selection_names(doc.Name, base.Name, edges, "edge")

    chamfer_obj = doc.addObject("PartDesign::Chamfer", name)
    chamfer_obj.Base = (base, edges)
    chamfer_obj.Size = size

    _add_to_body(base, chamfer_obj, doc)
    doc.recompute()
    return _feature_result(chamfer_obj)


def thickness(base_name: str, faces: list, value: float,
              name: str = "Thickness", doc_name: str = None) -> dict:
    """Shell a solid by removing faces and offsetting remaining faces.

    Args:
        base_name: Name of the base feature
        faces: List of face names to remove, e.g. ["Face1"]
        value: Wall thickness
    """
    doc = _get_doc(doc_name)
    base = _get_object(base_name, doc_name)

    from freecad_ai_bridge.geometry_ops import _selection_names

    faces = _selection_names(doc.Name, base.Name, faces, "face")

    thick_obj = doc.addObject("PartDesign::Thickness", name)
    thick_obj.Base = (base, faces)
    thick_obj.Value = value

    _add_to_body(base, thick_obj, doc)
    doc.recompute()
    return _feature_result(thick_obj)


def draft(base_name: str, faces: list, angle: float,
          plane_name: str = None, name: str = "Draft", doc_name: str = None) -> dict:
    """Add draft angle to faces.

    Args:
        base_name: Name of the base feature
        faces: List of face names to draft
        angle: Draft angle in degrees
    """
    doc = _get_doc(doc_name)
    base = _get_object(base_name, doc_name)

    from freecad_ai_bridge.geometry_ops import _selection_names

    faces = _selection_names(doc.Name, base.Name, faces, "face")
    if not plane_name:
        raise ValueError("A neutral plane is required, e.g. 'Pad.Face6' or a datum plane name")
    object_name, separator, subelement = plane_name.partition(".")
    plane = _get_object(object_name, doc_name)

    draft_obj = doc.addObject("PartDesign::Draft", name)
    draft_obj.Base = (base, faces)
    draft_obj.Angle = angle

    draft_obj.NeutralPlane = (plane, [subelement] if separator else [])

    _add_to_body(base, draft_obj, doc)
    doc.recompute()
    return _feature_result(draft_obj)


# =============================================================================
# Patterns
# =============================================================================


def linear_pattern(feature_name: str, direction: str = "X",
                   length: float = 100.0, occurrences: int = 3,
                   name: str = "LinearPattern", doc_name: str = None) -> dict:
    """Create a linear pattern of a feature.

    Args:
        feature_name: Feature to pattern
        direction: 'X', 'Y', or 'Z'
        length: Total length of the pattern
        occurrences: Number of copies (including original)
    """
    doc = _get_doc(doc_name)
    feature = _get_object(feature_name, doc_name)
    reference = _origin_reference(feature, direction, ("X", "Y", "Z"), "Axis")
    if occurrences < 2 or length <= 0:
        raise ValueError("Pattern requires at least two occurrences and positive length")

    pattern = doc.addObject("PartDesign::LinearPattern", name)
    pattern.Originals = [feature]
    pattern.Length = length
    pattern.Occurrences = occurrences

    # Set direction
    pattern.Direction = (reference, [""])

    _add_to_body(feature, pattern, doc)
    doc.recompute()
    return _feature_result(pattern)


def polar_pattern(feature_name: str, axis: str = "Z",
                  angle: float = 360.0, occurrences: int = 6,
                  name: str = "PolarPattern", doc_name: str = None) -> dict:
    """Create a polar (circular) pattern of a feature.

    Args:
        feature_name: Feature to pattern
        axis: Rotation axis - 'X', 'Y', or 'Z'
        angle: Total angle span in degrees
        occurrences: Number of copies (including original)
    """
    doc = _get_doc(doc_name)
    feature = _get_object(feature_name, doc_name)
    reference = _origin_reference(feature, axis, ("X", "Y", "Z"), "Axis")
    if occurrences < 2 or not 0 < angle <= 360:
        raise ValueError("Pattern requires at least two occurrences and an angle in (0, 360]")

    pattern = doc.addObject("PartDesign::PolarPattern", name)
    pattern.Originals = [feature]
    pattern.Angle = angle
    pattern.Occurrences = occurrences
    pattern.Axis = (reference, [""])

    _add_to_body(feature, pattern, doc)
    doc.recompute()
    return _feature_result(pattern)


def mirrored(feature_name: str, plane: str = "XY",
             name: str = "Mirrored", doc_name: str = None) -> dict:
    """Mirror a feature about a plane.

    Args:
        feature_name: Feature to mirror
        plane: Mirror plane - 'XY', 'XZ', or 'YZ'
    """
    doc = _get_doc(doc_name)
    feature = _get_object(feature_name, doc_name)
    reference = _origin_reference(feature, plane, ("XY", "XZ", "YZ"), "Plane")

    mirror = doc.addObject("PartDesign::Mirrored", name)
    mirror.Originals = [feature]
    mirror.MirrorPlane = (reference, [""])

    _add_to_body(feature, mirror, doc)
    doc.recompute()
    return _feature_result(mirror)


# =============================================================================
# Helpers
# =============================================================================


def _origin_reference(feature, selection, allowed, kind):
    selection = selection.upper()
    if selection not in allowed:
        raise ValueError(f"Unknown {kind.lower()} '{selection}'; expected {', '.join(allowed)}")
    body = feature.getParentGeoFeatureGroup()
    if body is None or body.TypeId != "PartDesign::Body":
        raise ValueError(f"Feature '{feature.Name}' must belong to a PartDesign Body")
    role = f"{selection}_{kind}"
    for origin_feature in body.Origin.OriginFeatures:
        if origin_feature.Role == role:
            return origin_feature
    raise ValueError(f"Body origin has no {role}")


def _add_to_body(reference_obj, new_obj, doc):
    """Add new_obj to the same body as reference_obj."""
    for obj in doc.Objects:
        if obj.TypeId == "PartDesign::Body":
            if hasattr(obj, "Group") and reference_obj in obj.Group:
                previous_tip = obj.Tip
                obj.addObject(new_obj)
                if previous_tip:
                    previous_tip.Visibility = False
                return
    # If reference is itself in the model tree, try to find body through InList
    if hasattr(reference_obj, "InList"):
        for parent in reference_obj.InList:
            if parent.TypeId == "PartDesign::Body":
                previous_tip = parent.Tip
                parent.addObject(new_obj)
                if previous_tip:
                    previous_tip.Visibility = False
                return


def _feature_result(obj) -> dict:
    """Build a standard result dict for a feature."""
    if "Invalid" in obj.State or obj.Shape.isNull() or not obj.Shape.isValid():
        raise ValueError(f"Feature '{obj.Name}' failed: {obj.getStatusString()}")
    result = {
        "name": obj.Name,
        "label": obj.Label,
        "type": obj.TypeId,
    }
    if hasattr(obj, "Shape") and obj.Shape and not obj.Shape.isNull():
        result["shape_valid"] = obj.Shape.isValid()
        result["volume"] = obj.Shape.Volume
    return result
