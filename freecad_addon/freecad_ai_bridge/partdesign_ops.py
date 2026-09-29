"""PartDesign operations running inside FreeCAD.

Provides Body creation, feature operations (Pad, Pocket, Revolution, etc.),
and pattern operations.
"""

import FreeCAD
import FreeCADGui
from FreeCAD import Vector


_EXTRUSION_TYPES = {
    "dimension": "Length",
    "through_all": "ThroughAll",
    "up_to_first": "UpToFirst",
    "up_to_face": "UpToFace",
    "two_lengths": "Length",
}


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


def create_datum(body_name: str, kind: str, name: str = None,
                 support_selection: dict = None,
                 x: float = 0, y: float = 0, z: float = 0,
                 rotation_x: float = 0, rotation_y: float = 0,
                 rotation_z: float = 0, doc_name: str = None) -> dict:
    """Create a datum plane, line, or point in a PartDesign Body."""
    doc = _get_doc(doc_name)
    body = _get_object(body_name, doc_name)
    kinds = {
        "plane": ("PartDesign::Plane", "DatumPlane"),
        "axis": ("PartDesign::Line", "DatumLine"),
        "point": ("PartDesign::Point", "DatumPoint"),
    }
    normalized = kind.lower()
    if normalized not in kinds:
        raise ValueError("Datum kind must be plane, axis, or point")
    if body.TypeId != "PartDesign::Body":
        raise ValueError(f"Object '{body.Name}' is not a PartDesign Body")
    placement = FreeCAD.Placement(
        Vector(x, y, z), FreeCAD.Rotation(rotation_z, rotation_y, rotation_x))
    resolved_support = None
    if support_selection is not None:
        from freecad_ai_bridge.geometry_ops import _descriptor, _resolve

        support_doc, owner, shape, support_kind = _resolve(support_selection)
        geometry_type = _descriptor(shape, support_kind)["geometry_type"]
        allowed_supports = {"plane": {("face", "plane")},
                            "axis": {("face", "cylinder"), ("edge", "line")},
                            "point": {("vertex", "vertex")}}
        if support_doc.Name != doc.Name or (support_kind, geometry_type) not in allowed_supports[normalized]:
            raise ValueError(f"Datum {normalized} does not support {geometry_type} {support_kind}")
        resolved_support = owner, support_selection["subelement"]
    type_id, default_name = kinds[normalized]
    datum = body.newObject(type_id, name or default_name)
    if resolved_support is not None:
        owner, subelement = resolved_support
        datum.AttachmentSupport = (owner, [subelement])
        datum.MapMode = {"plane": "FlatFace", "axis": "Concentric", "point": "Translate"}[normalized]
    else:
        datum.Placement = placement
    datum.AttachmentOffset = placement
    doc.recompute()
    return {
        "name": datum.Name,
        "label": datum.Label,
        "type": datum.TypeId,
        "kind": normalized,
        "support": support_selection,
        "attachment_offset": {
            "position": [x, y, z],
            "rotation_xyz_deg": [rotation_x, rotation_y, rotation_z],
        },
    }


# =============================================================================
# Additive Features
# =============================================================================


def pad(sketch_name: str, length: float, name: str = "Pad",
    symmetric: bool = False, reversed: bool = False,
    end_condition: str = "dimension", second_length: float = None,
    target_selection: dict = None, doc_name: str = None) -> dict:
    """Pad (extrude) a sketch.

    Args:
        sketch_name: Name of the sketch to pad
        length: Extrusion length
        symmetric: If True, pad symmetrically in both directions
        reversed: If True, pad in reverse direction
    """
    doc = _get_doc(doc_name)
    sketch = _get_object(sketch_name, doc_name)

    condition = _validate_extrusion(end_condition, length, symmetric,
                                    second_length, target_selection, False)
    target = _resolve_extrusion_target(target_selection, doc) if condition == "up_to_face" else None
    pad_obj = doc.addObject("PartDesign::Pad", name)
    pad_obj.Profile = sketch
    _configure_extrusion(pad_obj, condition, length, symmetric, reversed,
                         second_length, target, doc)

    # Add to body if sketch is in a body
    _add_to_body(sketch, pad_obj, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(pad_obj)


def pocket(sketch_name: str, length: float, name: str = "Pocket",
           through_all: bool = False, reversed: bool = False,
           symmetric: bool = False, end_condition: str = None,
           second_length: float = None, target_selection: dict = None,
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

    condition = end_condition or ("through_all" if through_all else "dimension")
    condition = _validate_extrusion(condition, length, symmetric,
                                    second_length, target_selection, True)
    target = _resolve_extrusion_target(target_selection, doc) if condition == "up_to_face" else None
    pocket_obj = doc.addObject("PartDesign::Pocket", name)
    pocket_obj.Profile = sketch
    _configure_extrusion(pocket_obj, condition, length, symmetric, reversed,
                         second_length, target, doc)

    _add_to_body(sketch, pocket_obj, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(pocket_obj)


def revolution(sketch_name: str, angle: float = 360.0, name: str = "Revolution",
               axis: str = "V", reversed: bool = False, symmetric: bool = False,
               second_angle: float = None, axis_name: str = None,
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

    _validate_rotation(angle, symmetric, second_angle)
    rev = doc.addObject("PartDesign::Revolution", name)
    rev.Profile = sketch
    rev.Angle = angle
    rev.Reversed = reversed
    _configure_rotation_axis(rev, sketch, axis, axis_name, doc)
    _configure_rotation_sides(rev, symmetric, second_angle)

    _add_to_body(sketch, rev, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(rev)


def groove(sketch_name: str, angle: float = 360.0, name: str = "Groove",
           axis: str = "V", reversed: bool = False, symmetric: bool = False,
           second_angle: float = None, axis_name: str = None,
           doc_name: str = None) -> dict:
    """Create a groove (subtractive revolution) from a sketch."""
    doc = _get_doc(doc_name)
    sketch = _get_object(sketch_name, doc_name)

    _validate_rotation(angle, symmetric, second_angle)
    grv = doc.addObject("PartDesign::Groove", name)
    grv.Profile = sketch
    grv.Angle = angle
    grv.Reversed = reversed
    _configure_rotation_axis(grv, sketch, axis, axis_name, doc)
    _configure_rotation_sides(grv, symmetric, second_angle)

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
          solid: bool = True, path_edges: list = None,
          orientation: str = "standard", transition: str = "transformed",
          doc_name: str = None) -> dict:
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
    _configure_pipe(sweep_obj, spine, path_edges, orientation, transition)

    _add_to_body(sketch, sweep_obj, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(sweep_obj)


def hole(sketch_name: str, diameter: float, depth: float,
         name: str = "Hole", threaded: bool = False,
         thread_type: str = "ISO", thread_size: str = "M6",
         thread_pitch: float = None, through_all: bool = False,
         cut_type: str = "simple", cut_diameter: float = None,
         cut_depth: float = None, countersink_angle: float = 90,
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
    cut_types = {"simple": "None", "counterbore": "Counterbore", "countersink": "Countersink"}
    normalized_cut = cut_type.lower()
    if diameter <= 0 or depth <= 0:
        raise ValueError("Hole diameter and depth must be positive")
    if normalized_cut not in cut_types:
        raise ValueError("cut_type must be simple, counterbore, or countersink")
    if normalized_cut != "simple" and (cut_diameter is None or cut_diameter <= diameter):
        raise ValueError("Counterbore/countersink requires cut_diameter greater than diameter")
    if normalized_cut == "counterbore" and (cut_depth is None or cut_depth <= 0):
        raise ValueError("Counterbore requires positive cut_depth")
    if normalized_cut == "countersink" and not 0 < countersink_angle < 180:
        raise ValueError("countersink_angle must be in (0, 180)")

    hole_obj = doc.addObject("PartDesign::Hole", name)
    hole_obj.Profile = sketch
    _add_to_body(sketch, hole_obj, doc)
    doc.recompute()
    hole_obj.Diameter = diameter
    hole_obj.Depth = depth
    hole_obj.DepthType = "ThroughAll" if through_all else "Dimension"
    hole_obj.HoleCutType = cut_types[normalized_cut]
    if normalized_cut != "simple":
        hole_obj.HoleCutCustomValues = True
        hole_obj.HoleCutDiameter = cut_diameter
    if normalized_cut == "counterbore":
        hole_obj.HoleCutDepth = cut_depth
    elif normalized_cut == "countersink":
        hole_obj.HoleCutCountersinkAngle = countersink_angle
    hole_obj.Threaded = threaded

    if threaded:
        thread_types = {"ISO": "ISOMetricProfile", "UTS": "UNC"}
        hole_obj.ThreadType = thread_types.get(thread_type, thread_type)
        sizes = hole_obj.getEnumerationsOfProperty("ThreadSize")
        requested = thread_size if thread_pitch is None else f"{thread_size.split('x')[0]}x{thread_pitch:g}"
        matches = [size for size in sizes if size == requested or (thread_pitch is None and size.split("x")[0] == requested)]
        if not matches:
            raise ValueError(f"Unknown thread size '{requested}' for {hole_obj.ThreadType}; available: {sizes}")
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
                     name: str = "SubtractivePipe", path_edges: list = None,
                     orientation: str = "standard", transition: str = "transformed",
                     doc_name: str = None) -> dict:
    """Create a subtractive pipe/sweep (cut along path)."""
    doc = _get_doc(doc_name)
    sketch = _get_object(sketch_name, doc_name)
    spine = _get_object(spine_name, doc_name)

    pipe_obj = doc.addObject("PartDesign::SubtractivePipe", name)
    pipe_obj.Profile = sketch
    _configure_pipe(pipe_obj, spine, path_edges, orientation, transition)

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
            name: str = "Chamfer", second_size: float = None,
            doc_name: str = None) -> dict:
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
    if second_size is not None:
        if second_size <= 0:
            raise ValueError("second_size must be positive")
        chamfer_obj.ChamferType = "Two distances"
        chamfer_obj.Size2 = second_size

    _add_to_body(base, chamfer_obj, doc)
    doc.recompute()
    return _feature_result(chamfer_obj)


def thickness(base_name: str, faces: list, value: float,
              name: str = "Thickness", direction: str = "inside",
              join: str = "arc", doc_name: str = None) -> dict:
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
    if value <= 0:
        raise ValueError("Thickness value must be positive")
    if direction not in {"inside", "outside"}:
        raise ValueError("direction must be inside or outside")

    thick_obj = doc.addObject("PartDesign::Thickness", name)
    thick_obj.Base = (base, faces)
    thick_obj.Value = value
    thick_obj.Reversed = direction == "outside"
    _set_enum(thick_obj, "Join", join, {"arc": ["Arc"], "intersection": ["Intersection"]})

    _add_to_body(base, thick_obj, doc)
    doc.recompute()
    return _feature_result(thick_obj)


def draft(base_name: str, faces: list, angle: float,
          plane_name: str = None, name: str = "Draft",
          pull_selection: dict = None, doc_name: str = None) -> dict:
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
    if pull_selection is not None:
        from freecad_ai_bridge.geometry_ops import _resolve

        pull_doc, pull_owner, _shape, pull_kind = _resolve(pull_selection)
        if pull_doc.Name != doc.Name or pull_kind not in {"edge", "face"}:
            raise ValueError("Pull direction requires a same-document edge or face selection")
        draft_obj.PullDirection = (pull_owner, [pull_selection["subelement"]])

    _add_to_body(base, draft_obj, doc)
    doc.recompute()
    return _feature_result(draft_obj)


# =============================================================================
# Patterns
# =============================================================================


def linear_pattern(feature_name: str, direction: str = "X",
                   length: float = 100.0, occurrences: int = 3,
                   name: str = "LinearPattern", feature_names: list = None,
                   direction_name: str = None, doc_name: str = None) -> dict:
    """Create a linear pattern of a feature.

    Args:
        feature_name: Feature to pattern
        direction: 'X', 'Y', or 'Z'
        length: Total length of the pattern
        occurrences: Number of copies (including original)
    """
    doc = _get_doc(doc_name)
    feature = _get_object(feature_name, doc_name)
    originals, body = _pattern_originals(feature, feature_names, doc)
    reference = _pattern_reference(feature, direction, direction_name, ("X", "Y", "Z"), "Axis", doc)
    if occurrences < 2 or length <= 0:
        raise ValueError("Pattern requires at least two occurrences and positive length")

    pattern = doc.addObject("PartDesign::LinearPattern", name)
    pattern.Originals = originals
    pattern.Length = length
    pattern.Occurrences = occurrences

    # Set direction
    pattern.Direction = (reference, [""])

    _add_to_body(feature, pattern, doc)
    doc.recompute()
    return _feature_result(pattern)


def polar_pattern(feature_name: str, axis: str = "Z",
                  angle: float = 360.0, occurrences: int = 6,
                  name: str = "PolarPattern", feature_names: list = None,
                  axis_name: str = None, doc_name: str = None) -> dict:
    """Create a polar (circular) pattern of a feature.

    Args:
        feature_name: Feature to pattern
        axis: Rotation axis - 'X', 'Y', or 'Z'
        angle: Total angle span in degrees
        occurrences: Number of copies (including original)
    """
    doc = _get_doc(doc_name)
    feature = _get_object(feature_name, doc_name)
    originals, body = _pattern_originals(feature, feature_names, doc)
    reference = _pattern_reference(feature, axis, axis_name, ("X", "Y", "Z"), "Axis", doc)
    if occurrences < 2 or not 0 < angle <= 360:
        raise ValueError("Pattern requires at least two occurrences and an angle in (0, 360]")

    pattern = doc.addObject("PartDesign::PolarPattern", name)
    pattern.Originals = originals
    pattern.Angle = angle
    pattern.Occurrences = occurrences
    pattern.Axis = (reference, [""])

    _add_to_body(feature, pattern, doc)
    doc.recompute()
    return _feature_result(pattern)


def mirrored(feature_name: str, plane: str = "XY",
             name: str = "Mirrored", feature_names: list = None,
             plane_name: str = None, doc_name: str = None) -> dict:
    """Mirror a feature about a plane.

    Args:
        feature_name: Feature to mirror
        plane: Mirror plane - 'XY', 'XZ', or 'YZ'
    """
    doc = _get_doc(doc_name)
    feature = _get_object(feature_name, doc_name)
    originals, body = _pattern_originals(feature, feature_names, doc)
    reference = _pattern_reference(feature, plane, plane_name, ("XY", "XZ", "YZ"), "Plane", doc)

    mirror = doc.addObject("PartDesign::Mirrored", name)
    mirror.Originals = originals
    mirror.MirrorPlane = (reference, [""])

    _add_to_body(feature, mirror, doc)
    doc.recompute()
    return _feature_result(mirror)


def multi_transform(feature_names: list, transformations: list,
                    name: str = "MultiTransform", doc_name: str = None) -> dict:
    """Apply an ordered chain of linear, polar, and mirrored transforms."""
    doc = _get_doc(doc_name)
    if not isinstance(feature_names, list) or not feature_names:
        raise ValueError("feature_names must be a nonempty list")
    if not isinstance(transformations, list) or not transformations:
        raise ValueError("transformations must be a nonempty ordered list")
    first = _get_object(feature_names[0], doc_name)
    originals, body = _pattern_originals(first, feature_names[1:], doc)
    multi = doc.addObject("PartDesign::MultiTransform", name)
    multi.Originals = originals
    multi.Shape = body.Tip.Shape
    body.addObject(multi)
    helpers = []
    for index, step in enumerate(transformations, 1):
        if not isinstance(step, dict) or step.get("type") not in {"linear", "polar", "mirrored"}:
            raise ValueError("Each transformation requires type linear, polar, or mirrored")
        kind = step["type"]
        helper_name = f"{multi.Name}_{kind.title()}{index}"
        if kind == "linear":
            length = step.get("length")
            occurrences = step.get("occurrences")
            if not isinstance(length, (int, float)) or length <= 0 or not isinstance(occurrences, int) or occurrences < 2:
                raise ValueError("Linear transformation requires positive length and occurrences >= 2")
            helper = doc.addObject("PartDesign::LinearPattern", helper_name)
            helper.Direction = (_pattern_reference(first, step.get("direction", "X"), step.get("direction_name"),
                                                   ("X", "Y", "Z"), "Axis", doc), [""])
            helper.Length = length
            helper.Occurrences = occurrences
        elif kind == "polar":
            angle = step.get("angle")
            occurrences = step.get("occurrences")
            if not isinstance(angle, (int, float)) or not 0 < angle <= 360 or not isinstance(occurrences, int) or occurrences < 2:
                raise ValueError("Polar transformation requires angle in (0, 360] and occurrences >= 2")
            helper = doc.addObject("PartDesign::PolarPattern", helper_name)
            helper.Axis = (_pattern_reference(first, step.get("axis", "Z"), step.get("axis_name"),
                                              ("X", "Y", "Z"), "Axis", doc), [""])
            helper.Angle = angle
            helper.Occurrences = occurrences
        else:
            helper = doc.addObject("PartDesign::Mirrored", helper_name)
            helper.MirrorPlane = (_pattern_reference(first, step.get("plane", "XY"), step.get("plane_name"),
                                                     ("XY", "XZ", "YZ"), "Plane", doc), [""])
        body.addObject(helper)
        helpers.append(helper)
    multi.Transformations = helpers
    body.Tip = multi
    for helper in helpers:
        helper.Visibility = False
    doc.recompute()
    result = _feature_result(multi)
    result["transformations"] = [helper.Name for helper in helpers]
    result["originals"] = [original.Name for original in originals]
    return result


def edit_feature(feature_name: str, profile_names: list = None,
                 parameters: dict = None, doc_name: str = None) -> dict:
    """Replace feature profiles and edit a bounded set of native parameters."""
    doc = _get_doc(doc_name)
    feature = _get_object(feature_name, doc_name)
    body = feature.getParentGeoFeatureGroup()
    if body is None or body.TypeId != "PartDesign::Body":
        raise ValueError(f"Feature '{feature.Name}' must belong to a PartDesign Body")
    if profile_names is None and not parameters:
        raise ValueError("profile_names or parameters is required")
    if profile_names is not None:
        if not isinstance(profile_names, list) or not profile_names:
            raise ValueError("profile_names must be a nonempty list")
        profiles = [_get_object(profile_name, doc.Name) for profile_name in profile_names]
        if any(profile.getParentGeoFeatureGroup() != body for profile in profiles):
            raise ValueError("Replacement profiles must belong to the same Body")
        if "Sections" in feature.PropertiesList:
            if len(profiles) < 2:
                raise ValueError("Loft profile replacement requires at least two profiles")
            feature.Profile = profiles[0]
            feature.Sections = profiles[1:]
        elif "Profile" in feature.PropertiesList:
            if len(profiles) != 1:
                raise ValueError("This feature accepts exactly one replacement profile")
            feature.Profile = profiles[0]
        else:
            raise ValueError(f"Feature '{feature.Name}' does not expose editable profiles")
    property_map = {
        "length": "Length", "second_length": "Length2",
        "angle": "Angle", "second_angle": "Angle2",
        "diameter": "Diameter", "depth": "Depth",
        "occurrences": "Occurrences", "radius": "Radius",
        "size": "Size", "second_size": "Size2",
        "reversed": "Reversed",
    }
    for key, value in (parameters or {}).items():
        property_name = property_map.get(key)
        if property_name is None or property_name not in feature.PropertiesList:
            raise ValueError(f"Parameter '{key}' is not editable for {feature.TypeId}")
        if key == "reversed":
            if not isinstance(value, bool):
                raise ValueError("reversed must be boolean")
        elif not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"Parameter '{key}' must be positive")
        setattr(feature, property_name, value)
    old_tip = body.Tip
    doc.recompute()
    if body.Tip != old_tip:
        raise ValueError("Editing changed the Body Tip unexpectedly")
    result = _feature_result(feature)
    result["body"] = body.Name
    result["tip"] = body.Tip.Name if body.Tip else None
    return result


# =============================================================================
# Helpers
# =============================================================================


def _validate_extrusion(end_condition, length, symmetric, second_length,
                        target_selection, allow_through_all):
    condition = str(end_condition).lower()
    allowed = set(_EXTRUSION_TYPES)
    if not allow_through_all:
        allowed.remove("through_all")
    if condition not in allowed:
        raise ValueError(f"Unknown end condition '{end_condition}'; expected {', '.join(sorted(allowed))}")
    if length <= 0:
        raise ValueError("Extrusion length must be positive")
    if condition == "two_lengths" and (second_length is None or second_length <= 0):
        raise ValueError("two_lengths requires a positive second_length")
    if condition == "up_to_face" and target_selection is None:
        raise ValueError("up_to_face requires target_selection")
    if condition != "up_to_face" and target_selection is not None:
        raise ValueError("target_selection is only valid for up_to_face")
    if symmetric and condition in {"up_to_first", "up_to_face", "two_lengths"}:
        raise ValueError(f"symmetric is not supported with {condition}")
    return condition


def _validate_rotation(angle, symmetric, second_angle):
    if not 0 < angle <= 360:
        raise ValueError("Rotation angle must be in (0, 360]")
    if second_angle is not None and not 0 < second_angle <= 360:
        raise ValueError("Second rotation angle must be in (0, 360]")
    if symmetric and second_angle is not None:
        raise ValueError("symmetric and second_angle are mutually exclusive")


def _configure_rotation_axis(feature, sketch, axis, axis_name, doc):
    if axis_name:
        reference = _get_object(axis_name, doc.Name)
        if reference.TypeId != "PartDesign::Line":
            raise ValueError(f"Axis '{axis_name}' is not a datum axis")
        feature.ReferenceAxis = (reference, [""])
        return
    axis_map = {"V": "V_Axis", "H": "H_Axis", "N": "N_Axis"}
    normalized = axis.upper()
    if normalized not in axis_map:
        raise ValueError("Rotation axis must be V, H, or N, or axis_name must name a datum axis")
    feature.ReferenceAxis = (sketch, [axis_map[normalized]])


def _configure_rotation_sides(feature, symmetric, second_angle):
    if "Type" in feature.PropertiesList:
        feature.Type = "TwoAngles" if second_angle is not None else "Angle"
    if "Midplane" in feature.PropertiesList:
        feature.Midplane = symmetric
    if "Angle2" in feature.PropertiesList and second_angle is not None:
        feature.Angle2 = second_angle
    if "SideType" in feature.PropertiesList:
        feature.SideType = "Symmetric" if symmetric else ("Two sides" if second_angle is not None else "One side")


def _configure_pipe(feature, spine, path_edges, orientation, transition):
    edges = [] if path_edges is None else path_edges
    if not isinstance(edges, list) or any(not isinstance(edge, str) or not edge.startswith("Edge") for edge in edges):
        raise ValueError("path_edges must contain EdgeN names")
    feature.Spine = (spine, edges)
    _set_enum(feature, "Mode", orientation, {
        "standard": ["Standard"], "frenet": ["Frenet"],
    })
    _set_enum(feature, "Transition", transition, {
        "transformed": ["Transformed"], "right": ["Right corner", "RightCorner"],
        "round": ["Round corner", "RoundCorner"],
    })


def _set_enum(obj, property_name, requested, aliases):
    normalized = str(requested).lower()
    if normalized not in aliases:
        raise ValueError(f"Unsupported {property_name} '{requested}'; expected {', '.join(sorted(aliases))}")
    if property_name not in obj.PropertiesList:
        if normalized != next(iter(aliases)):
            raise ValueError(f"FreeCAD runtime does not expose {property_name}")
        return
    available = obj.getEnumerationsOfProperty(property_name)
    for candidate in aliases[normalized]:
        if candidate in available:
            setattr(obj, property_name, candidate)
            return
    raise ValueError(f"FreeCAD runtime does not support {property_name} '{requested}'; available: {available}")


def _configure_extrusion(feature, condition, length, symmetric, reversed,
                         second_length, target, doc):
    feature.Length = length
    if "SideType" in feature.PropertiesList:
        feature.SideType = "Symmetric" if symmetric else ("Two sides" if condition == "two_lengths" else "One side")
    elif "Midplane" in feature.PropertiesList:
        feature.Midplane = symmetric
    if "Reversed" in feature.PropertiesList:
        feature.Reversed = reversed
    feature.Type = _EXTRUSION_TYPES[condition]
    if condition == "two_lengths":
        feature.Length2 = second_length
        if "Type2" in feature.PropertiesList:
            feature.Type2 = "Length"
    elif condition == "up_to_face":
        owner, subelement = target
        feature.UpToFace = (owner, [subelement])


def _resolve_extrusion_target(selection, doc):
    from freecad_ai_bridge.geometry_ops import _resolve

    target_doc, owner, _shape, kind = _resolve(selection)
    if target_doc.Name != doc.Name or kind != "face":
        raise ValueError("Target face must be in the feature document")
    return owner, selection["subelement"]


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


def _pattern_originals(first, additional_names, doc):
    body = first.getParentGeoFeatureGroup()
    if body is None or body.TypeId != "PartDesign::Body":
        raise ValueError(f"Feature '{first.Name}' must belong to a PartDesign Body")
    originals = [first]
    for name in additional_names or []:
        obj = _get_object(name, doc.Name)
        if obj.getParentGeoFeatureGroup() != body:
            raise ValueError("All pattern originals must belong to the same PartDesign Body")
        if obj not in originals:
            originals.append(obj)
    return originals, body


def _pattern_reference(feature, selection, datum_name, allowed, kind, doc):
    if datum_name:
        reference = _get_object(datum_name, doc.Name)
        expected = "PartDesign::Line" if kind == "Axis" else "PartDesign::Plane"
        if reference.TypeId != expected or reference.getParentGeoFeatureGroup() != feature.getParentGeoFeatureGroup():
            raise ValueError(f"{datum_name} must be a {expected} in the same Body")
        return reference
    return _origin_reference(feature, selection, allowed, kind)


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
    if len(obj.Shape.Solids) != 1:
        raise ValueError(f"Feature '{obj.Name}' must produce one connected solid")
    result = {
        "name": obj.Name,
        "label": obj.Label,
        "type": obj.TypeId,
    }
    if hasattr(obj, "Shape") and obj.Shape and not obj.Shape.isNull():
        result["shape_valid"] = obj.Shape.isValid()
        result["volume"] = obj.Shape.Volume
    return result
