"""Structured native FreeCAD Assembly operations."""

import math
import sys

import FreeCAD

from freecad_ai_bridge.contracts import BridgeError


JOINT_TYPES = {"fixed": 0, "revolute": 1, "cylindrical": 2, "slider": 3, "ball": 4}
JOINT_DOF = {"Fixed": 0, "Revolute": 1, "Cylindrical": 2, "Slider": 1, "Ball": 3}


def _load_joint_module():
    assembly_path = FreeCAD.getResourceDir() + "Mod/Assembly"
    if assembly_path not in sys.path:
        sys.path.insert(0, assembly_path)
    try:
        import JointObject
    except Exception as error:
        raise BridgeError("assembly_unavailable", f"Native Assembly workbench is unavailable: {error}") from error
    return JointObject


def _document(doc_name):
    document = FreeCAD.listDocuments().get(doc_name)
    if document is None:
        raise BridgeError("document_not_found", f"Document '{doc_name}' is not open", [{"document": doc_name}])
    return document


def _object(document, name):
    obj = document.getObject(name)
    if obj is None:
        raise BridgeError("object_not_found", f"Object '{name}' is not in '{document.Name}'",
                          [{"document": document.Name, "object": name}])
    return obj


def _assembly(document, name):
    assembly = _object(document, name)
    if not assembly.isDerivedFrom("Assembly::AssemblyObject"):
        raise BridgeError("invalid_arguments", f"Object '{name}' is not a native Assembly")
    return assembly


def _joint_group(assembly):
    for item in assembly.Group:
        if item.isDerivedFrom("Assembly::JointGroup"):
            return item
    raise BridgeError("invalid_assembly", f"Assembly '{assembly.Name}' has no JointGroup")


def _component(assembly, name):
    component = _object(assembly.Document, name)
    if component not in assembly.Group or not component.isDerivedFrom("App::Link"):
        raise BridgeError("invalid_reference", f"Object '{name}' is not a component of '{assembly.Name}'")
    if component.LinkedObject is None:
        raise BridgeError("unresolved_component", f"Component '{name}' has no resolved source",
                          [{"document": assembly.Document.Name, "object": name}])
    return component


def _joint(assembly, name):
    joint = _object(assembly.Document, name)
    if joint not in _joint_group(assembly).Group or not hasattr(joint, "JointType"):
        raise BridgeError("invalid_reference", f"Object '{name}' is not a joint of '{assembly.Name}'")
    return joint


def _vector(values, label):
    if (not isinstance(values, list) or len(values) != 3 or
            any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                for value in values)):
        raise BridgeError("invalid_arguments", f"{label} must contain three finite numbers")
    return FreeCAD.Vector(*values)


def _rotation(values, label):
    vector = _vector(values, label)
    return FreeCAD.Rotation(vector.z, vector.y, vector.x)


def _placement(position, rotation, position_label="position", rotation_label="rotation"):
    return FreeCAD.Placement(_vector(position, position_label), _rotation(rotation, rotation_label))


def _reference_data(reference):
    if not reference or reference[0] is None:
        return None
    return {"component": reference[0].Name, "subelements": list(reference[1])}


def _placement_data(placement):
    quaternion = placement.Rotation.Q
    return {"position": [placement.Base.x, placement.Base.y, placement.Base.z],
            "quaternion": list(quaternion)}


def _solve(assembly):
    try:
        code = int(assembly.solve(True))
    except Exception as error:
        raise BridgeError("assembly_unsolved", f"Assembly solver failed: {error}") from error
    if code != 0:
        raise BridgeError("assembly_unsolved", f"Assembly solver returned code {code}")
    return code


def create_assembly(doc_name: str, name: str = "Assembly") -> dict:
    document = _document(doc_name)
    if not isinstance(name, str) or not name.strip():
        raise BridgeError("invalid_arguments", "Assembly name must be nonempty")
    _load_joint_module()
    assembly = document.addObject("Assembly::AssemblyObject", name)
    assembly.Type = "Assembly"
    joints = assembly.newObject("Assembly::JointGroup", "Joints")
    return {"reference": {"document": document.Name, "object": assembly.Name},
            "name": assembly.Name, "joint_group": joints.Name}


def add_component(doc_name: str, assembly_name: str, source_document: str, source_object: str,
                  name: str = "Component", position: list = None, rotation: list = None) -> dict:
    document = _document(doc_name)
    assembly = _assembly(document, assembly_name)
    source_doc = _document(source_document)
    source = _object(source_doc, source_object)
    if source is assembly or assembly in source.OutListRecursive:
        raise BridgeError("dependency_cycle", "Component source would introduce an Assembly dependency cycle")
    if source_doc is not document:
        if not source_doc.FileName or not document.FileName:
            raise BridgeError("invalid_reference", "Save both source and Assembly documents before inserting an external component")
        if source_doc.HasPendingTransaction:
            raise BridgeError("transaction_conflict", "Source document has a foreign pending transaction")
    if not isinstance(name, str) or not name.strip():
        raise BridgeError("invalid_arguments", "Component name must be nonempty")
    link_type = "Assembly::AssemblyLink" if source.isDerivedFrom("Assembly::AssemblyObject") else "App::Link"
    component = assembly.newObject(link_type, name)
    component.LinkedObject = source
    component.LinkTransform = True
    component.Label = source.Label
    component.Placement = _placement(position or [0, 0, 0], rotation or [0, 0, 0])
    component.recompute()
    warnings = (["External source file must remain available and be saved separately."]
                if source_doc is not document else [])
    return {"reference": {"document": document.Name, "object": component.Name}, "name": component.Name,
            "source": {"document": source_doc.Name, "object": source.Name},
            "placement": _placement_data(component.Placement), "warnings": warnings}


def set_grounded(doc_name: str, assembly_name: str, component_name: str, grounded: bool = True) -> dict:
    document = _document(doc_name)
    assembly = _assembly(document, assembly_name)
    component = _component(assembly, component_name)
    if type(grounded) is not bool:
        raise BridgeError("invalid_arguments", "grounded must be boolean")
    group = _joint_group(assembly)
    grounds = [item for item in group.Group
               if hasattr(item, "ObjectToGround") and item.ObjectToGround is component]
    if grounded and not grounds:
        grounded_names = {item.ObjectToGround.Name for item in group.Group
                          if hasattr(item, "ObjectToGround") and item.ObjectToGround is not None}
        graph = {}
        for joint in group.Group:
            if not hasattr(joint, "JointType") or bool(joint.Suppressed):
                continue
            first = _reference_data(joint.Reference1)
            second = _reference_data(joint.Reference2)
            if first and second:
                graph.setdefault(first["component"], set()).add(second["component"])
                graph.setdefault(second["component"], set()).add(first["component"])
        reachable = {component.Name}
        pending = [component.Name]
        while pending:
            current = pending.pop()
            for neighbor in graph.get(current, ()):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    pending.append(neighbor)
        if reachable & grounded_names:
            raise BridgeError("assembly_unsolved",
                              "Grounding this component would overconstrain its connected joint tree")
        joint_module = _load_joint_module()
        ground = group.newObject("App::FeaturePython", f"Ground_{component.Name}")
        joint_module.GroundedJoint(ground, component)
        grounds = [ground]
    elif not grounded:
        for ground in grounds:
            document.removeObject(ground.Name)
        grounds = []
    document.recompute()
    solver_code = _solve(assembly)
    return {"reference": {"document": document.Name, "object": component.Name}, "grounded": grounded,
            "ground_joint": grounds[0].Name if grounds else None, "solver_code": solver_code}


def create_joint(doc_name: str, assembly_name: str, joint_type: str, component1: str, component2: str,
                 subelement1: str = "", vertex1: str = "", subelement2: str = "", vertex2: str = "",
                 offset1_position: list = None, offset1_rotation: list = None,
                 offset2_position: list = None, offset2_rotation: list = None,
                 length_min: float = None, length_max: float = None,
                 angle_min: float = None, angle_max: float = None, name: str = "Joint") -> dict:
    document = _document(doc_name)
    assembly = _assembly(document, assembly_name)
    if joint_type not in JOINT_TYPES:
        raise BridgeError("invalid_arguments", f"Unsupported joint type '{joint_type}'")
    first = _component(assembly, component1)
    second = _component(assembly, component2)
    if first is second:
        raise BridgeError("invalid_arguments", "A joint requires two different components")
    for label, value in (("subelement1", subelement1), ("vertex1", vertex1),
                         ("subelement2", subelement2), ("vertex2", vertex2)):
        if not isinstance(value, str):
            raise BridgeError("invalid_arguments", f"{label} must be a string")
    if not isinstance(name, str) or not name.strip():
        raise BridgeError("invalid_arguments", "Joint name must be nonempty")
    _validate_limits(joint_type, length_min, length_max, angle_min, angle_max)
    document.recompute()
    joint_module = _load_joint_module()
    joint = _joint_group(assembly).newObject("App::FeaturePython", name)
    joint_module.Joint(joint, JOINT_TYPES[joint_type])
    joint.Offset1 = _placement(offset1_position or [0, 0, 0], offset1_rotation or [0, 0, 0],
                               "offset1_position", "offset1_rotation")
    joint.Offset2 = _placement(offset2_position or [0, 0, 0], offset2_rotation or [0, 0, 0],
                               "offset2_position", "offset2_rotation")
    _apply_limits(joint, length_min, length_max, angle_min, angle_max)
    refs = [[first, [subelement1, vertex1 or subelement1]],
            [second, [subelement2, vertex2 or subelement2]]]
    try:
        joint.Proxy.setJointConnectors(joint, refs)
        document.recompute()
        solver_code = _solve(assembly)
    except BridgeError:
        raise
    except Exception as error:
        raise BridgeError("invalid_joint_reference", f"Joint connector resolution failed: {error}") from error
    return {"reference": {"document": document.Name, "object": joint.Name}, "name": joint.Name,
            "joint_type": joint.JointType, "relative_dof": JOINT_DOF[joint.JointType],
            "reference1": _reference_data(joint.Reference1), "reference2": _reference_data(joint.Reference2),
            "solver_code": solver_code}


def _validate_limit(value, label):
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
        raise BridgeError("invalid_arguments", f"{label} must be a finite number or null")


def _validate_limits(joint_type, length_min, length_max, angle_min, angle_max):
    for value, label in ((length_min, "length_min"), (length_max, "length_max"),
                         (angle_min, "angle_min"), (angle_max, "angle_max")):
        _validate_limit(value, label)
    if length_min is not None and length_max is not None and length_min > length_max:
        raise BridgeError("invalid_arguments", "length_min must not exceed length_max")
    if angle_min is not None and angle_max is not None and angle_min > angle_max:
        raise BridgeError("invalid_arguments", "angle_min must not exceed angle_max")
    if (length_min is not None or length_max is not None) and joint_type not in {"slider", "cylindrical"}:
        raise BridgeError("invalid_arguments", "Length limits apply only to Slider and Cylindrical joints")
    if (angle_min is not None or angle_max is not None) and joint_type not in {"revolute", "cylindrical"}:
        raise BridgeError("invalid_arguments", "Angle limits apply only to Revolute and Cylindrical joints")


def _apply_limits(joint, length_min, length_max, angle_min, angle_max):
    joint.EnableLengthMin = length_min is not None
    joint.EnableLengthMax = length_max is not None
    joint.EnableAngleMin = angle_min is not None
    joint.EnableAngleMax = angle_max is not None
    if length_min is not None:
        joint.LengthMin = length_min
    if length_max is not None:
        joint.LengthMax = length_max
    if angle_min is not None:
        joint.AngleMin = angle_min
    if angle_max is not None:
        joint.AngleMax = angle_max


def set_joint(doc_name: str, assembly_name: str, joint_name: str, suppressed: bool = None,
              offset1_position: list = None, offset1_rotation: list = None,
              offset2_position: list = None, offset2_rotation: list = None,
              length_min: float = None, length_max: float = None,
              angle_min: float = None, angle_max: float = None) -> dict:
    document = _document(doc_name)
    assembly = _assembly(document, assembly_name)
    joint = _joint(assembly, joint_name)
    joint_type = joint.JointType.lower()
    if suppressed is not None and type(suppressed) is not bool:
        raise BridgeError("invalid_arguments", "suppressed must be boolean or null")
    current_limits = {
        "length_min": joint.LengthMin.Value if joint.EnableLengthMin else None,
        "length_max": joint.LengthMax.Value if joint.EnableLengthMax else None,
        "angle_min": joint.AngleMin.Value if joint.EnableAngleMin else None,
        "angle_max": joint.AngleMax.Value if joint.EnableAngleMax else None,
    }
    updates = {"length_min": length_min, "length_max": length_max,
               "angle_min": angle_min, "angle_max": angle_max}
    limits = {key: updates[key] if updates[key] is not None else value
              for key, value in current_limits.items()}
    _validate_limits(joint_type, **limits)
    if suppressed is not None:
        joint.Suppressed = suppressed
    if offset1_position is not None or offset1_rotation is not None:
        position = _vector(offset1_position, "offset1_position") if offset1_position is not None else joint.Offset1.Base
        rotation = _rotation(offset1_rotation, "offset1_rotation") if offset1_rotation is not None else joint.Offset1.Rotation
        joint.Offset1 = FreeCAD.Placement(position, rotation)
    if offset2_position is not None or offset2_rotation is not None:
        position = _vector(offset2_position, "offset2_position") if offset2_position is not None else joint.Offset2.Base
        rotation = _rotation(offset2_rotation, "offset2_rotation") if offset2_rotation is not None else joint.Offset2.Rotation
        joint.Offset2 = FreeCAD.Placement(position, rotation)
    _apply_limits(joint, **limits)
    document.recompute()
    solver_code = _solve(assembly)
    return {"reference": {"document": document.Name, "object": joint.Name}, "joint_type": joint.JointType,
            "suppressed": bool(joint.Suppressed), "solver_code": solver_code}


def set_component_pose(doc_name: str, assembly_name: str, component_name: str,
                       position: list, rotation: list, solve: bool = True) -> dict:
    document = _document(doc_name)
    assembly = _assembly(document, assembly_name)
    component = _component(assembly, component_name)
    component.Placement = _placement(position, rotation)
    if solve:
        document.recompute()
        solver_code = _solve(assembly)
    else:
        solver_code = None
    return {"reference": {"document": document.Name, "object": component.Name},
            "placement": _placement_data(component.Placement), "solver_code": solver_code,
            "warnings": [] if solve else ["Assembly was not solved after setting the component pose."]}


def inspect_assembly(doc_name: str, assembly_name: str) -> dict:
    document = _document(doc_name)
    assembly = _assembly(document, assembly_name)
    group = _joint_group(assembly)
    components = [item for item in assembly.Group if item.isDerivedFrom("App::Link")]
    grounded = {item.ObjectToGround.Name for item in group.Group
                if hasattr(item, "ObjectToGround") and item.ObjectToGround is not None}
    joints = [item for item in group.Group if hasattr(item, "JointType")]
    joint_data = []
    edges = []
    for joint in joints:
        first = _reference_data(joint.Reference1)
        second = _reference_data(joint.Reference2)
        active = not bool(joint.Suppressed)
        joint_data.append({"name": joint.Name, "joint_type": joint.JointType,
                           "relative_dof": JOINT_DOF.get(joint.JointType), "suppressed": not active,
                           "reference1": first, "reference2": second,
                           "limits": {"length_min": joint.LengthMin.Value if joint.EnableLengthMin else None,
                                      "length_max": joint.LengthMax.Value if joint.EnableLengthMax else None,
                                      "angle_min": joint.AngleMin.Value if joint.EnableAngleMin else None,
                                      "angle_max": joint.AngleMax.Value if joint.EnableAngleMax else None}})
        if active and first and second:
            edges.append((first["component"], second["component"], JOINT_DOF.get(joint.JointType)))
    dof, warning = _tree_dof([item.Name for item in components], grounded, edges)
    warnings = [warning] if warning else []
    return {"reference": {"document": document.Name, "object": assembly.Name},
            "components": [{"name": item.Name,
                            "source": {"document": item.LinkedObject.Document.Name,
                                       "object": item.LinkedObject.Name} if item.LinkedObject else None,
                            "grounded": item.Name in grounded, "placement": _placement_data(item.Placement),
                            "resolved": item.LinkedObject is not None} for item in components],
            "joints": joint_data, "independent_dof": dof, "dof_exact": dof is not None,
            "solver_state": list(assembly.State), "warnings": warnings}


def _tree_dof(components, grounded, edges):
    if not components or len(grounded) != 1 or not grounded.issubset(components):
        return None, "Exact DoF requires exactly one grounded component."
    parent = {name: name for name in components}

    def find(name):
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    total = 0
    for first, second, dof in edges:
        if first not in parent or second not in parent or dof is None:
            return None, "Exact DoF is unavailable for unresolved or unsupported joint references."
        root1, root2 = find(first), find(second)
        if root1 == root2:
            return None, "Exact DoF is unavailable for assemblies with joint loops or overconstraints."
        parent[root2] = root1
        total += dof
    if len(edges) != len(components) - 1 or len({find(name) for name in components}) != 1:
        return None, "Exact DoF requires a fully connected, acyclic joint tree."
    return total, None


def check_collisions(doc_name: str, assembly_name: str, contact_tolerance: float = 0.001,
                     volume_tolerance: float = 0.000001) -> dict:
    document = _document(doc_name)
    assembly = _assembly(document, assembly_name)
    if (isinstance(contact_tolerance, bool) or not isinstance(contact_tolerance, (int, float)) or
            not math.isfinite(contact_tolerance) or contact_tolerance < 0 or
            isinstance(volume_tolerance, bool) or not isinstance(volume_tolerance, (int, float)) or
            not math.isfinite(volume_tolerance) or volume_tolerance < 0):
        raise BridgeError("invalid_arguments", "Collision tolerances must be finite and nonnegative")
    components = [_component(assembly, item.Name) for item in assembly.Group if item.isDerivedFrom("App::Link")]
    pairs = []
    for index, first in enumerate(components):
        if not hasattr(first, "Shape") or first.Shape.isNull():
            raise BridgeError("invalid_geometry", f"Component '{first.Name}' has no resolved Shape")
        for second in components[index + 1:]:
            if not hasattr(second, "Shape") or second.Shape.isNull():
                raise BridgeError("invalid_geometry", f"Component '{second.Name}' has no resolved Shape")
            distance = float(first.Shape.distToShape(second.Shape)[0])
            common = first.Shape.common(second.Shape)
            volume = float(common.Volume) if not common.isNull() else 0.0
            pairs.append({"first": first.Name, "second": second.Name, "distance": distance,
                          "intersection_volume": volume, "interference": volume > volume_tolerance,
                          "contact": volume <= volume_tolerance and distance <= contact_tolerance})
    return {"reference": {"document": document.Name, "object": assembly.Name}, "pairs": pairs,
            "interferences": [pair for pair in pairs if pair["interference"]],
            "contact_tolerance": contact_tolerance, "volume_tolerance": volume_tolerance,
            "warnings": ["Static discrete collision check only; no continuous motion or safety guarantee."]}