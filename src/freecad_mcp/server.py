"""FreeCAD MCP Server - Main entry point.

Exposes FreeCAD functionality as MCP tools for Claude and other AI assistants.
Uses FastMCP with stdio transport.
"""

import base64
import json
import xmlrpc.client
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP, Image
from pydantic import BaseModel, ConfigDict, Field

from freecad_mcp.connection import FreeCADConnection, FreeCADRemoteError
from freecad_mcp.schema import SchemaMCP


class Reference(BaseModel):
    """Exact names in currently open documents, not persistent identity tokens."""

    document: str = Field(description="Internal document Name, not Label or file path.")
    object: str | None = Field(default=None, description="Internal object Name within document, not Label.")


class ContractError(BaseModel):
    code: str
    message: str
    cause: str
    references: list[Reference] = Field(default_factory=list)
    retryable: bool = False
    state: Literal["unchanged", "rolled_back", "unknown"] = "unknown"
    rollback_error: str | None = None


class ContractResponse(BaseModel):
    """Additive v1 response; existing tools retain their legacy JSON text."""

    contract_version: Literal["1.0"] = "1.0"
    status: Literal["success", "error"]
    data: dict[str, Any] | None = None
    references: list[Reference] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: ContractError | None = None


class BatchStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$", description="Unique step ID; backward references only.")
    operation: Literal["part_box", "part_cylinder", "part_sphere", "part_cone", "part_torus",
                       "move_object", "set_placement", "boolean_cut", "part_fillet", "part_chamfer", "delete_object"] = Field(
                           description="Allowlisted tool name. No files, scripts, lifecycle or nested batches.")
    doc_name: str = Field(min_length=1, pattern=r"\S", description="Explicit existing internal document Name.")
    arguments: dict[str, Any] = Field(
        description="Parameters of the named tool except doc_name. Object-name parameters accept {'$ref':'earlier_id'} for its returned name; same document only. Length mm, angles deg; transforms parent-local, primitives document-global. Validated before any execution.")


def _contract_failure(error: Exception) -> ContractResponse:
    if isinstance(error, FreeCADRemoteError):
        details = error.details
        failure = ContractError(
            code=error.code, message=details.get("message", str(error)),
            cause=details.get("cause", type(error).__name__),
            references=details.get("references", []),
            retryable=details.get("retryable", False), state=details.get("state", "unknown"),
            rollback_error=details.get("rollback_error"),
        )
    else:
        failure = ContractError(code="transport_error", message=str(error), cause=type(error).__name__)
    return ContractResponse(status="error", error=failure, references=failure.references)


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "unknown"

# Initialize MCP server
mcp = SchemaMCP("FreeCAD AI Server")

# Global connection instance
_conn = FreeCADConnection()


def _call(module: str, function: str, **kwargs) -> Any:
    """Helper to call a function in FreeCAD via RPC."""
    # Remove None values to use defaults on the FreeCAD side
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    return _conn.call_function(module, function, **kwargs)


# =============================================================================
# Connection & Document Tools
# =============================================================================


@mcp.tool()
def execute_batch(
    steps: Annotated[list[BatchStep], Field(min_length=1, max_length=100,
                                           description="Ordered 1..100 steps, max 65536 UTF-8 JSON bytes. All validated before mutation.")],
    atomic: Annotated[bool, Field(strict=True, description="True: one existing document, one Undo record and rollback. False: multiple documents, stop on first error.")] = True,
    preview: Annotated[bool, Field(strict=True, description="Validate and describe effects without executing geometry or mutating documents.")] = False,
) -> ContractResponse:
    """Execute or preview allowlisted CAD operations with explicit document ownership.

    Atomic batches use one existing document and one Undo record. Nonatomic
    batches may span documents, stop at first error and retain earlier successes.
    Preview never executes geometry. Results report each step as planned,
    succeeded, failed, rolled_back, unknown or not_executed; inspect status.
    Deletion accepts only unreferenced leaf objects. No persistent preview token,
    retries, distributed transaction, file rollback or guaranteed kernel cancel.
    Errors: invalid_batch, transaction_conflict, dependency_conflict and reference/
    kernel/transport errors. A timeout means unknown outcome, never automatic retry.
    """
    try:
        result = _call("freecad_ai_bridge.operations", "execute_batch",
                       steps=[step.model_dump() for step in steps], atomic=atomic, preview=preview)
        success = result["status"] in {"succeeded", "preview"}
        return ContractResponse(status="success" if success else "error", data=result,
                                references=[reference for step in result["steps"] for reference in step.get("references", [])],
                                warnings=result.get("warnings", []), error=None if success else ContractError(
                                    **result["error"]))
    except (FreeCADRemoteError, OSError, xmlrpc.client.Error) as error:
        return _contract_failure(error)


@mcp.tool()
def get_capabilities() -> ContractResponse:
    """Read FreeCAD build, bridge/host versions, feature flags and units (mm, deg).

    Reports document-global model coordinates and sketch-local XY geometry.
    Workbench presence is availability only, not proof of supported options.
    No document is activated, recomputed or mutated. Errors include
    transport_error or legacy_error when the bridge needs an update.
    """
    try:
        result = _call("freecad_ai_bridge.operations", "get_capabilities")
        result["mcp_server_version"] = _package_version("freecad-mcp-server")
        result["mcp_sdk_version"] = _package_version("mcp")
        return ContractResponse(status="success", data=result)
    except (FreeCADRemoteError, OSError, xmlrpc.client.Error) as error:
        return _contract_failure(error)


@mcp.tool()
def resolve_reference(
    doc_name: Annotated[str, Field(strict=True, min_length=1, pattern=r"\S",
                                  description="Required internal document Name; no active-document fallback.")],
    obj_name: Annotated[str | None, Field(strict=True, min_length=1, pattern=r"\S",
                                         description="Internal object Name, not Label; omit to resolve document.")] = None,
) -> ContractResponse:
    """Resolve exact names without mutation, label search or document activation.

    Returns document/object references and type/label metadata only (no geometry).
    References are current name lookups, not persistent IDs across delete/reopen.
    Errors: document_not_found, object_not_found, invalid_arguments,
    transport_error, legacy_error. No automatic retries or guessed replacements.
    """
    try:
        result = _call("freecad_ai_bridge.operations", "resolve_reference", doc_name=doc_name, obj_name=obj_name)
        return ContractResponse(status="success", data=result, references=[result["reference"]])
    except (FreeCADRemoteError, OSError, xmlrpc.client.Error) as error:
        return _contract_failure(error)


@mcp.tool()
def connect(host: str = "127.0.0.1", port: int = 9875) -> str:
    """Connect to a running FreeCAD instance with the AI Bridge addon.

    Must be called before using any other tools. FreeCAD must be running
    with the FreecadAIBridge addon loaded.
    """
    global _conn
    _conn = FreeCADConnection(host=host, port=port)
    if _conn.connect():
        version = _conn.get_version()
        return f"Connected to FreeCAD {version} at {host}:{port}"
    else:
        return f"Failed to connect to FreeCAD at {host}:{port}. Is FreeCAD running with the AI Bridge addon?"


@mcp.tool()
def get_status() -> str:
    """Check connection status and get document state."""
    if not _conn.is_connected:
        return "Not connected to FreeCAD. Use 'connect' tool first."
    state = _conn.get_document_state()
    return json.dumps(state, indent=2)


@mcp.tool()
def create_document(name: str = "Unnamed") -> str:
    """Create a new FreeCAD document."""
    result = _call("freecad_ai_bridge.operations", "create_document", name=name)
    return json.dumps(result)


@mcp.tool()
def open_document(path: str) -> str:
    """Open a FreeCAD document from file."""
    result = _call("freecad_ai_bridge.operations", "open_document", path=path)
    return json.dumps(result)


@mcp.tool()
def save_document(name: str = None, path: str = None) -> str:
    """Save the current document. Optionally specify path for 'Save As'."""
    result = _call("freecad_ai_bridge.operations", "save_document", name=name, path=path)
    return json.dumps(result)


@mcp.tool()
def close_document(name: str) -> str:
    """Close a document by name."""
    result = _call("freecad_ai_bridge.operations", "close_document", name=name)
    return json.dumps(result)


@mcp.tool()
def list_objects(doc_name: str = None) -> str:
    """List all objects in the active (or specified) document with their types and properties."""
    result = _call("freecad_ai_bridge.operations", "list_objects", doc_name=doc_name)
    return json.dumps(result, indent=2)


@mcp.tool()
def inspect_object(obj_name: str, doc_name: str = None) -> str:
    """Get detailed information about a specific object (properties, shape info, etc.)."""
    result = _call("freecad_ai_bridge.operations", "inspect_object", obj_name=obj_name, doc_name=doc_name)
    return json.dumps(result, indent=2)


@mcp.tool()
def delete_object(obj_name: str, doc_name: str = None) -> str:
    """Delete an object from the document."""
    result = _call("freecad_ai_bridge.operations", "delete_object", obj_name=obj_name, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Sketcher - Geometry Tools
# =============================================================================


InternalName = Annotated[str, Field(strict=True, min_length=1, pattern=r"\S",
                                    description="Explicit internal Name; no Label or active-document fallback.")]


CoordinateVector = Annotated[list[Annotated[float, Field(strict=True, allow_inf_nan=False)]],
                             Field(min_length=3, max_length=3, description="XYZ in document-global mm; directions dimensionless.")]
GeometryKind = Annotated[Literal["face", "edge", "vertex"], Field(description="BRep subelement kind.")]
GeometryTolerance = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False,
    description="Absolute tolerance in mm (position/radius/length/BBox) or mm^2 (area).", json_schema_extra={"x-unit": "mm"})]
AngularTolerance = Annotated[float, Field(strict=True, ge=0, le=180, allow_inf_nan=False,
    description="Angular tolerance in degrees; normals oriented, axes unoriented.", json_schema_extra={"x-unit": "deg"})]


class GeometryRange(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    min: float | None = Field(default=None, ge=0, allow_inf_nan=False, description="Inclusive lower bound; at least one bound required.")
    max: float | None = Field(default=None, ge=0, allow_inf_nan=False, description="Inclusive upper bound in mm or mm^2 for area.")


class GeometryBounds(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    min: CoordinateVector
    max: CoordinateVector


class GeometryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    geometry_type: Literal["plane", "cylinder", "cone", "sphere", "torus", "bspline_surface", "line", "circle",
                           "ellipse", "bspline_curve", "bezier_curve", "vertex", "other"] | None = None
    position: CoordinateVector | None = Field(default=None, description="Center of mass (vertex: point) in document-global mm.")
    bbox: GeometryBounds | None = Field(default=None, description="Require the entire subelement bounding box inside these bounds in mm.")
    normal: CoordinateVector | None = Field(default=None, description="Oriented outward planar normal; nonplanar faces do not match.")
    axis: CoordinateVector | None = Field(default=None, description="Unoriented analytic axis or straight-edge tangent; nonzero vector.")
    radius: GeometryRange | None = Field(default=None, description="Analytic circle/cylinder/sphere radius in mm, absent for other geometry.")
    area: GeometryRange | None = Field(default=None, description="Face area range in mm^2.")
    length: GeometryRange | None = Field(default=None, description="Edge length range in mm.")


class SubelementSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document: InternalName
    object: InternalName
    revision: str = Field(min_length=1, description="Opaque session/document revision returned by a geometry query; never manufacture it.")
    subelement: str = Field(pattern=r"^(Face|Edge|Vertex)[1-9][0-9]*$", description="Exact returned subelement name; valid only at the returned revision.")


def _geometry_call(function: str, **arguments) -> ContractResponse:
    try:
        result = _conn.call_function("freecad_ai_bridge.geometry_ops", function, **arguments)
        references = result.get("references", [result["reference"]] if "reference" in result else [])
        return ContractResponse(status="success", data=result, references=references, warnings=result.get("warnings", []))
    except (FreeCADRemoteError, OSError, xmlrpc.client.Error) as error:
        return _contract_failure(error)


@mcp.tool()
def list_subelements(doc_name: InternalName, obj_name: InternalName, kind: GeometryKind,
                     filters: Annotated[GeometryFilter | None, Field(description="AND-combined geometric filters; null lists all.")] = None,
                     tolerance: GeometryTolerance = 0.001, angular_tolerance: AngularTolerance = 0.001,
                     offset: Annotated[int, Field(strict=True, ge=0, description="Zero-based match offset; requery after any revision change.")] = 0,
                     limit: Annotated[int, Field(strict=True, ge=1, le=256, description="Maximum returned matches; total counts all matches, at most 10000 subelements scanned.")] = 100,
                     ) -> ContractResponse:
    """List filtered BRep faces/edges/vertices with global geometry and revision tokens, without recompute. geometry_not_ready requires explicit recompute."""
    return _geometry_call("list_subelements", doc_name=doc_name, obj_name=obj_name, kind=kind,
                          filters=filters.model_dump(exclude_none=True) if filters else None,
                          tolerance=tolerance, angular_tolerance=angular_tolerance, offset=offset, limit=limit)


@mcp.tool()
def select_subelement(doc_name: InternalName, obj_name: InternalName, kind: GeometryKind,
                      filters: Annotated[GeometryFilter | None, Field(description="AND-combined geometric filters requiring exactly one match.")] = None,
                      tolerance: GeometryTolerance = 0.001, angular_tolerance: AngularTolerance = 0.001) -> ContractResponse:
    """Select exactly one subelement without hard-coded indices. Errors selection_empty/selection_ambiguous; no guessed match."""
    return _geometry_call("select_subelement", doc_name=doc_name, obj_name=obj_name, kind=kind,
                          filters=filters.model_dump(exclude_none=True) if filters else None,
                          tolerance=tolerance, angular_tolerance=angular_tolerance)


@mcp.tool()
def resolve_subelement(selection: Annotated[SubelementSelection, Field(description="Complete selection returned by list/select_subelement.")]) -> ContractResponse:
    """Validate and inspect an issued selection. Document changes, Undo/Redo or reopen invalidate it: stale_selection; never remap."""
    return _geometry_call("resolve_subelement", selection=selection.model_dump())


class GeometryObjectReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document: InternalName
    object: InternalName


GeometryTarget = Annotated[SubelementSelection | GeometryObjectReference, Field(
    description="Whole object {document,object} at current state, or complete issued subelement selection with revision. Both targets must be in one document; global mm.")]


@mcp.tool()
def measure_distance(first: GeometryTarget, second: GeometryTarget) -> ContractResponse:
    """Minimum distance in mm between finite BReps, with up to 32 closest-point pairs in document-global coordinates. Stale selections fail."""
    return _geometry_call("measure_distance", first=first.model_dump(), second=second.model_dump())


@mcp.tool()
def measure_angle(first: GeometryTarget, second: GeometryTarget) -> ContractResponse:
    """Smallest unoriented angle (0..90 deg) between selected straight edges/planar faces, including line-plane. Others: unsupported_geometry."""
    return _geometry_call("measure_angle", first=first.model_dump(), second=second.model_dump())


@mcp.tool()
def check_interference(first: GeometryTarget, second: GeometryTarget,
                       contact_tolerance: Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False,
                           description="Distance <= this mm threshold is within contact tolerance; default 0.001 mm.")] = 0.001,
                       volume_tolerance: Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False,
                           description="Intersection volume > this mm^3 threshold is interference; default 1e-6 mm^3.")] = 0.000001) -> ContractResponse:
    """Static closed-solid collision check: distance, intersection volume and separated/contact/interference. Whole objects only; no motion/safety assurance."""
    return _geometry_call("check_interference", first=first.model_dump(), second=second.model_dump(),
                          contact_tolerance=contact_tolerance, volume_tolerance=volume_tolerance)


@mcp.tool()
def highlight_subelements(doc_name: InternalName,
                           selections: Annotated[list[SubelementSelection], Field(max_length=100,
                               description="Complete issued selections in this document; validate all before replacing its GUI selection. Empty clears only this document.")]) -> ContractResponse:
    """Mark revision-checked matches in the GUI without changing visibility or geometry. No document Undo entry; stale input preserves previous selection."""
    return _geometry_call("highlight_subelements", doc_name=doc_name, selections=[selection.model_dump() for selection in selections])


@mcp.tool()
def get_view_state(doc_name: InternalName,
                    obj_names: Annotated[list[InternalName], Field(max_length=256,
                        description="Objects whose visibility, RGB color and transparency to read; empty reads camera and selection only.")]) -> ContractResponse:
    """Read explicit document camera quaternion, GUI selection and appearance for restoration with existing set_visibility/color/transparency tools."""
    return _geometry_call("get_view_state", doc_name=doc_name, obj_names=obj_names)


@mcp.tool(structured_output=False)
def capture_view(doc_name: InternalName,
                  width: Annotated[int, Field(strict=True, ge=64, le=2048, description="PNG width in pixels.")] = 800,
                  height: Annotated[int, Field(strict=True, ge=64, le=2048, description="PNG height in pixels.")] = 600,
                  view: Annotated[Literal["isometric", "front", "back", "top", "bottom", "left", "right"],
                                  Field(description="Explicit target document camera preset; fit all visible objects.")] = "isometric",
                  selections: Annotated[list[SubelementSelection] | None, Field(max_length=100,
                      description="Null preserves highlight; empty clears; otherwise validate and replace only this document's selection.")] = None) -> list[Image | str]:
    """Return ContractResponse JSON metadata plus a native MCP PNG image. No recompute; stale/dirty geometry fails. Camera/highlight are GUI-only changes."""
    try:
        result = _call("freecad_ai_bridge.geometry_ops", "capture_view", doc_name=doc_name, width=width, height=height,
                       view=view, selections=[selection.model_dump() for selection in selections] if selections is not None else None)
        image = Image(data=base64.b64decode(result.pop("image_base64")), format="png")
        response = ContractResponse(status="success", data=result, references=[result["reference"]], warnings=result.get("warnings", []))
        return [response.model_dump_json(), image]
    except (FreeCADRemoteError, OSError, xmlrpc.client.Error) as error:
        return [_contract_failure(error).model_dump_json()]


def _document_call(function: str, **arguments) -> ContractResponse:
    try:
        result = _conn.call_function("freecad_ai_bridge.document_ops", function, **arguments)
        references = result.get("references", [result["reference"]] if "reference" in result else [])
        return ContractResponse(status="success", data=result, references=references, warnings=result.get("warnings", []))
    except (FreeCADRemoteError, OSError, xmlrpc.client.Error) as error:
        return _contract_failure(error)


@mcp.tool()
def inspect_document(doc_name: InternalName) -> ContractResponse:
    """Read active/modified/file state, object states, Body Tips and container members without recompute."""
    return _document_call("inspect_document", doc_name=doc_name)


@mcp.tool()
def activate_document(doc_name: InternalName) -> ContractResponse:
    """Activate an explicitly named open document. Rejects foreign pending transactions."""
    return _document_call("activate_document", doc_name=doc_name)


@mcp.tool()
def recompute_document(doc_name: InternalName) -> ContractResponse:
    """Recompute and reject invalid object states with recompute_failed and transaction rollback."""
    return _document_call("recompute_document", doc_name=doc_name)


@mcp.tool()
def save_document_safe(doc_name: InternalName, path: Annotated[str | None, Field(
    description="Absolute .FCStd destination; omit to save to the document's existing path.")] = None,
    overwrite: Annotated[bool, Field(strict=True, description="Explicit permission to overwrite an existing file, including ordinary Save.")] = False,
) -> ContractResponse:
    """Save with file_exists protection. Files are outside Undo/rollback; failed writes report possible artifact path."""
    return _document_call("save_document_safe", doc_name=doc_name, path=path, overwrite=overwrite)


@mcp.tool()
def close_document_safe(doc_name: InternalName, discard_changes: Annotated[bool, Field(
    strict=True, description="Explicit permission to discard unsaved changes; dependent documents must be closed first.")] = False,
) -> ContractResponse:
    """Close with unsaved_changes/dependency_conflict protection. Never discards a foreign transaction."""
    return _document_call("close_document_safe", doc_name=doc_name, discard_changes=discard_changes)


@mcp.tool()
def create_container(doc_name: InternalName, name: InternalName,
                     kind: Annotated[Literal["group", "body"], Field(description="group: App::DocumentObjectGroup; body: PartDesign::Body.")] = "group") -> ContractResponse:
    """Create a document group or PartDesign Body and return its actual internal Name."""
    return _document_call("create_container", doc_name=doc_name, name=name, kind=kind)


@mcp.tool()
def set_container_members(doc_name: InternalName, obj_name: InternalName,
                          members: Annotated[list[InternalName], Field(max_length=100,
                              description="Complete ordered member Names in the same document; empty removes all. No duplicate/cyclic membership.")]) -> ContractResponse:
    """Group/ungroup or replace Body members. Body members are sketches/PartDesign features; preserve or clear Tip first."""
    return _document_call("set_container_members", doc_name=doc_name, obj_name=obj_name, members=members)


@mcp.tool()
def set_body_tip(doc_name: InternalName, obj_name: InternalName, tip_name: InternalName | None = None) -> ContractResponse:
    """Set Body Tip to one of its PartDesign features; null clears Tip. Invalid membership is rejected."""
    return _document_call("set_body_tip", doc_name=doc_name, obj_name=obj_name, tip_name=tip_name)


@mcp.tool()
def get_properties(doc_name: InternalName, obj_name: InternalName,
                   properties: Annotated[list[InternalName] | None, Field(max_length=256,
                       description="Selected property Names; omit for metadata of all properties (max 256).")] = None) -> ContractResponse:
    """Read property type, writable/status, unit, enum choices and typed value. Unknown types return supported=false/value=null."""
    return _document_call("get_properties", doc_name=doc_name, obj_name=obj_name, properties=properties)


@mcp.tool()
def set_properties(doc_name: InternalName, obj_name: InternalName,
                   values: Annotated[dict[str, Any], Field(min_length=1, max_length=100, description=(
                       "Property/value map. Scalars retain JSON types; Quantity={value:number,unit:string}; Vector=[x,y,z] mm; "
                       "Placement={position:[x,y,z] mm,quaternion:[x,y,z,w]} parent-local, unit norm; Link={document,object} or null; "
                       "LinkSub={reference:{document,object},subelements:[Face1]} or null; list properties contain those values. "
                       "Read-only, managed, expression-driven and unsupported types rejected; lists max 256. "
                       "Errors: property_read_only, invalid_enum, invalid_unit, invalid_reference, dependency_cycle, recompute_failed."))]) -> ContractResponse:
    """Atomically edit typed properties and recompute with one Undo entry; no generic methods or string coercion."""
    return _document_call("set_properties", doc_name=doc_name, obj_name=obj_name, values=values)


@mcp.tool()
def get_expressions(doc_name: InternalName, obj_name: InternalName) -> ContractResponse:
    """Read native property paths and Expressions without evaluating Python or mutating the document."""
    return _document_call("get_expressions", doc_name=doc_name, obj_name=obj_name)


@mcp.tool()
def set_expression(doc_name: InternalName, obj_name: InternalName, property_name: InternalName,
                   expression: Annotated[str | None, Field(max_length=4096, description=(
                       "Native arithmetic expression with units and same-document object/cell/alias references; + - * / ^ and parentheses. "
                       "No function calls, scripts or external-document expressions. Null removes expression. "
                       "Invalid references, cycles and failed recomputes cause invalid_expression and rollback."))] = None) -> ContractResponse:
    """Set/remove a native property Expression, recompute and roll back on failure. Property paths may include components/indexes."""
    return _document_call("set_expression", doc_name=doc_name, obj_name=obj_name, property_name=property_name, expression=expression)


@mcp.tool()
def create_spreadsheet(doc_name: InternalName, name: InternalName = "Parameters") -> ContractResponse:
    """Create a native Spreadsheet parameter sheet and return its actual internal Name."""
    return _document_call("create_spreadsheet", doc_name=doc_name, name=name)


@mcp.tool()
def read_spreadsheet(doc_name: InternalName, obj_name: InternalName,
                     cell_range: Annotated[str, Field(description="Uppercase cell or ordered rectangular range, e.g. A1:B4; A1..ZZ99999, at most 256 cells.")]) -> ContractResponse:
    """Read raw cell contents, evaluated values and aliases. No recompute or mutation."""
    return _document_call("read_spreadsheet", doc_name=doc_name, obj_name=obj_name, cell_range=cell_range)


@mcp.tool()
def set_spreadsheet_cells(doc_name: InternalName, obj_name: InternalName,
                          cells: Annotated[dict[str, str | None], Field(min_length=1, max_length=256,
                              description="Cell/content map (A1..ZZ99999). String is raw native content (max 4096 chars), leading = arithmetic formula; null clears. Units explicit in strings.")]) -> ContractResponse:
    """Atomically set/clear spreadsheet cells and recompute dependents. Invalid formulas/references/cycles roll back all cells."""
    return _document_call("set_spreadsheet_cells", doc_name=doc_name, obj_name=obj_name, cells=cells)


@mcp.tool()
def set_spreadsheet_alias(doc_name: InternalName, obj_name: InternalName,
                          cell: Annotated[str, Field(description="Uppercase cell A1..ZZ99999.")],
                          alias: Annotated[str | None, Field(description="Unique identifier, not a cell address; null removes the alias.")] = None) -> ContractResponse:
    """Set/remove a Spreadsheet alias. Duplicates and invalid dependent expressions are rejected with rollback."""
    return _document_call("set_spreadsheet_alias", doc_name=doc_name, obj_name=obj_name, cell=cell, alias=alias)


@mcp.tool()
def rename_object(doc_name: InternalName, obj_name: InternalName,
                   label: Annotated[str, Field(strict=True, min_length=1, max_length=256, description="New display Label; internal Name remains unchanged.")]) -> ContractResponse:
    """Rename the display Label without invalidating Name-based references."""
    return _document_call("rename_object", doc_name=doc_name, obj_name=obj_name, label=label)


@mcp.tool()
def get_dependencies(doc_name: InternalName, obj_name: InternalName) -> ContractResponse:
    """Read direct dependencies/dependents and transitive affected objects, including external references. Not a geometry simulation."""
    return _document_call("get_dependencies", doc_name=doc_name, obj_name=obj_name)


@mcp.tool()
def copy_object(doc_name: InternalName, obj_name: InternalName) -> ContractResponse:
    """Recursively copy a native object and its inputs in the same document; reject retained source references. Returns all created Names."""
    return _document_call("copy_object", doc_name=doc_name, obj_name=obj_name)


@mcp.tool()
def create_link(doc_name: InternalName, name: InternalName, source_document: InternalName,
                source_object: InternalName) -> ContractResponse:
    """Create App::Link to an explicit source in this or another document. For external links save both documents first; source changes propagate."""
    return _document_call("create_link", doc_name=doc_name, name=name, source_document=source_document, source_object=source_object)


@mcp.tool()
def preview_delete(doc_name: InternalName,
                    obj_names: Annotated[list[InternalName], Field(min_length=1, max_length=100, description="Root object Names; preview includes dependents and owned container contents.")]) -> ContractResponse:
    """Read complete deletion set and required confirmation without mutation. External dependents block deletion."""
    return _document_call("preview_delete", doc_name=doc_name, obj_names=obj_names)


@mcp.tool()
def delete_objects(doc_name: InternalName,
                    obj_names: Annotated[list[InternalName], Field(min_length=1, max_length=100, description="Root object Names from preview.")],
                    confirmed_objects: Annotated[list[InternalName], Field(description="Every Name in the current preview confirmation, without duplicates. Revalidated immediately before mutation.")]) -> ContractResponse:
    """Delete exactly the confirmed dependency/ownership closure in one transaction. Changed confirmation or external references fail safely."""
    return _document_call("delete_objects", doc_name=doc_name, obj_names=obj_names, confirmed_objects=confirmed_objects)


@mcp.tool()
def create_sketch(name: str = "Sketch", plane: str = "XY", offset: float = 0.0,
                  body_name: str = None, doc_name: str = None) -> str:
    """Create a new sketch on a plane (XY, XZ, or YZ).

    If body_name is specified, attaches the sketch to that PartDesign Body.
    Returns the sketch name and constraint status.
    """
    result = _call("freecad_ai_bridge.sketcher_ops", "create_sketch",
                   name=name, plane=plane, offset=offset, body_name=body_name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_line(sketch_name: str, x1: float, y1: float, x2: float, y2: float,
                    construction: bool = False, doc_name: str = None) -> str:
    """Add a line segment to a sketch. Returns geometry index."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_line",
                   sketch_name=sketch_name, x1=x1, y1=y1, x2=x2, y2=y2,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_rectangle(sketch_name: str, x1: float, y1: float, x2: float, y2: float,
                         construction: bool = False, doc_name: str = None) -> str:
    """Add a rectangle to a sketch (4 lines with coincident + H/V constraints).

    (x1,y1) is bottom-left, (x2,y2) is top-right corner.
    Returns geometry indices of the 4 lines.
    """
    result = _call("freecad_ai_bridge.sketcher_ops", "add_rectangle",
                   sketch_name=sketch_name, x1=x1, y1=y1, x2=x2, y2=y2,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_circle(sketch_name: str, cx: float, cy: float, radius: float,
                      construction: bool = False, doc_name: str = None) -> str:
    """Add a circle to a sketch. Returns geometry index."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_circle",
                   sketch_name=sketch_name, cx=cx, cy=cy, radius=radius,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_arc(sketch_name: str, cx: float, cy: float, radius: float,
                   start_angle: float, end_angle: float,
                   construction: bool = False, doc_name: str = None) -> str:
    """Add an arc (portion of circle) to a sketch. Angles in radians."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_arc",
                   sketch_name=sketch_name, cx=cx, cy=cy, radius=radius,
                   start_angle=start_angle, end_angle=end_angle,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_ellipse(sketch_name: str, cx: float, cy: float,
                       major_radius: float, minor_radius: float,
                       angle: float = 0.0, construction: bool = False,
                       doc_name: str = None) -> str:
    """Add an ellipse to a sketch."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_ellipse",
                   sketch_name=sketch_name, cx=cx, cy=cy,
                   major_radius=major_radius, minor_radius=minor_radius,
                   angle=angle, construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_bspline(sketch_name: str, points: list,
                       construction: bool = False, doc_name: str = None) -> str:
    """Add a B-spline curve through control points.

    Args:
        points: List of [x, y] coordinate pairs, e.g. [[0,0], [5,10], [10,0]]
    """
    result = _call("freecad_ai_bridge.sketcher_ops", "add_bspline",
                   sketch_name=sketch_name, points=points,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_point(sketch_name: str, x: float, y: float,
                     construction: bool = False, doc_name: str = None) -> str:
    """Add a point to a sketch."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_point",
                   sketch_name=sketch_name, x=x, y=y,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_polygon(sketch_name: str, points: list, close: bool = True,
                       construction: bool = False, doc_name: str = None) -> str:
    """Add a polygon (connected lines) to a sketch.

    Args:
        points: List of [x, y] coordinate pairs
        close: If True, connect last point back to first
    """
    result = _call("freecad_ai_bridge.sketcher_ops", "add_polygon",
                   sketch_name=sketch_name, points=points, close=close,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_slot(sketch_name: str, x1: float, y1: float, x2: float, y2: float,
                    radius: float, construction: bool = False, doc_name: str = None) -> str:
    """Add a slot (two parallel lines connected by semicircles) to a sketch."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_slot",
                   sketch_name=sketch_name, x1=x1, y1=y1, x2=x2, y2=y2,
                   radius=radius, construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_move_point(sketch_name: str, geo_idx: int, point_idx: int,
                      x: float, y: float, doc_name: str = None) -> str:
    """Move a geometry point to an absolute sketch-local XY position in mm."""
    result = _call("freecad_ai_bridge.sketcher_ops", "move_geometry_point",
                   sketch_name=sketch_name, geo_idx=geo_idx, point_idx=point_idx,
                   x=x, y=y, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_set_construction(sketch_name: str, geo_idx: int, construction: bool,
                            doc_name: str = None) -> str:
    """Set one geometry element to normal or construction geometry."""
    result = _call("freecad_ai_bridge.sketcher_ops", "set_geometry_construction",
                   sketch_name=sketch_name, geo_idx=geo_idx, construction=construction,
                   doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_delete_geometry(sketch_name: str, geo_idx: int, doc_name: str = None) -> str:
    """Delete one geometry element and constraints that natively depend on it."""
    result = _call("freecad_ai_bridge.sketcher_ops", "delete_geometry",
                   sketch_name=sketch_name, geo_idx=geo_idx, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_external(sketch_name: str, selection: SubelementSelection,
                        defining: bool = False, intersection: bool = False,
                        doc_name: str = None) -> str:
    """Project one revision-checked edge from another object into this sketch."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_external_geometry",
                   sketch_name=sketch_name, selection=selection.model_dump(),
                   defining=defining, intersection=intersection, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_delete_external(sketch_name: str, external_idx: int,
                           doc_name: str = None) -> str:
    """Remove an external geometry link by its zero-based external-list index."""
    result = _call("freecad_ai_bridge.sketcher_ops", "delete_external_geometry",
                   sketch_name=sketch_name, external_idx=external_idx, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_set_attachment(sketch_name: str, support_name: str = None,
                          support_selection: SubelementSelection | None = None,
                          offset_x: float = 0.0, offset_y: float = 0.0, offset_z: float = 0.0,
                          rotation_x: float = 0.0, rotation_y: float = 0.0, rotation_z: float = 0.0,
                          doc_name: str = None) -> str:
    """Attach to a datum plane or revision-checked planar face; omit both supports to detach. Rotations apply X then Y then Z."""
    result = _call("freecad_ai_bridge.sketcher_ops", "set_sketch_attachment",
                   sketch_name=sketch_name, support_name=support_name,
                   support_selection=None if support_selection is None else support_selection.model_dump(),
                   offset_x=offset_x, offset_y=offset_y, offset_z=offset_z,
                   rotation_x=rotation_x, rotation_y=rotation_y, rotation_z=rotation_z,
                   doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_trim(sketch_name: str, geo_idx: int, x: float, y: float,
                include_axes: bool = False, doc_name: str = None) -> str:
    """Trim a line or circular arc at a sketch-local reference point. FreeCAD 1.1 rejects include_axes=true."""
    result = _call("freecad_ai_bridge.sketcher_ops", "trim_geometry",
                   sketch_name=sketch_name, geo_idx=geo_idx, x=x, y=y,
                   include_axes=include_axes, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_extend(sketch_name: str, geo_idx: int, increment: float, point_idx: int,
                  doc_name: str = None) -> str:
    """Extend start point 1 or end point 2 of a line/circular arc by a signed increment in mm."""
    result = _call("freecad_ai_bridge.sketcher_ops", "extend_geometry",
                   sketch_name=sketch_name, geo_idx=geo_idx, increment=increment,
                   point_idx=point_idx, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_fillet(sketch_name: str, geo_idx1: int, geo_idx2: int,
                  near1_x: float, near1_y: float, near2_x: float, near2_y: float,
                  radius: float, trim: bool = True, create_corner: bool = True,
                  doc_name: str = None) -> str:
    """Create a tangent fillet between two sketch lines or circular arcs."""
    result = _call("freecad_ai_bridge.sketcher_ops", "fillet_geometry",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, geo_idx2=geo_idx2,
                   near1_x=near1_x, near1_y=near1_y, near2_x=near2_x, near2_y=near2_y,
                   radius=radius, trim=trim, create_corner=create_corner, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_copy(sketch_name: str,
                geometry_indices: Annotated[list[int], Field(min_length=1, max_length=100,
                                                             description="Unique zero-based local geometry indices to copy.")],
                offset_x: float, offset_y: float, clone: bool = False,
                doc_name: str = None) -> str:
    """Copy selected local sketch geometry by an XY offset; clone=true adds equality-style clone constraints."""
    result = _call("freecad_ai_bridge.sketcher_ops", "copy_geometry",
                   sketch_name=sketch_name, geometry_indices=geometry_indices,
                   offset_x=offset_x, offset_y=offset_y, clone=clone, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_mirror(sketch_name: str,
                  geometry_indices: Annotated[list[int], Field(min_length=1, max_length=100,
                                                               description="Unique zero-based local geometry indices to mirror.")],
                  reference_geo_idx: int, reference_point_idx: int = 0,
                  doc_name: str = None) -> str:
    """Mirror selected local geometry about a local/external line (point 0) or supported point."""
    result = _call("freecad_ai_bridge.sketcher_ops", "mirror_geometry",
                   sketch_name=sketch_name, geometry_indices=geometry_indices,
                   reference_geo_idx=reference_geo_idx, reference_point_idx=reference_point_idx,
                   doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_info(sketch_name: str, doc_name: str = None) -> str:
    """Get detailed sketch info: all geometries, constraints, and constraint status."""
    result = _call("freecad_ai_bridge.sketcher_ops", "get_sketch_info",
                   sketch_name=sketch_name, doc_name=doc_name)
    return json.dumps(result, indent=2)


# =============================================================================
# Sketcher - Constraint Tools
# =============================================================================


@mcp.tool()
def sketch_constrain_coincident(sketch_name: str, geo_idx1: int, point_idx1: int,
                                geo_idx2: int, point_idx2: int,
                                doc_name: str = None) -> str:
    """Make two points coincident (same location).

    Point indices: 1=start, 2=end, 3=center (circles/arcs).
    The origin is geometry -1, point 1. External axes are -1 (X) and -2 (Y).
    """
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_coincident",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, point_idx1=point_idx1,
                   geo_idx2=geo_idx2, point_idx2=point_idx2, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_tangent(sketch_name: str, geo_idx1: int, geo_idx2: int,
                             point_idx1: int = None, point_idx2: int = None,
                             doc_name: str = None) -> str:
    """Make two geometries tangent to each other."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_tangent",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, geo_idx2=geo_idx2,
                   point_idx1=point_idx1, point_idx2=point_idx2, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_perpendicular(sketch_name: str, geo_idx1: int, geo_idx2: int,
                                   doc_name: str = None) -> str:
    """Make two lines perpendicular."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_perpendicular",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, geo_idx2=geo_idx2, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_parallel(sketch_name: str, geo_idx1: int, geo_idx2: int,
                              doc_name: str = None) -> str:
    """Make two lines parallel."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_parallel",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, geo_idx2=geo_idx2, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_equal(sketch_name: str, geo_idx1: int, geo_idx2: int,
                           doc_name: str = None) -> str:
    """Make two elements equal (same length for lines, same radius for circles)."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_equal",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, geo_idx2=geo_idx2, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_symmetric(sketch_name: str,
                               geo_idx1: int, point_idx1: int,
                               geo_idx2: int, point_idx2: int,
                               sym_geo: int, sym_point: int = None,
                               doc_name: str = None) -> str:
    """Make two points symmetric about a line (omit sym_point) or a point."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_symmetric",
                   sketch_name=sketch_name,
                   geo_idx1=geo_idx1, point_idx1=point_idx1,
                   geo_idx2=geo_idx2, point_idx2=point_idx2,
                   sym_geo=sym_geo, sym_point=sym_point, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_horizontal(sketch_name: str, geo_idx: int,
                                doc_name: str = None) -> str:
    """Constrain a line to be horizontal."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_horizontal",
                   sketch_name=sketch_name, geo_idx=geo_idx, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_vertical(sketch_name: str, geo_idx: int,
                              doc_name: str = None) -> str:
    """Constrain a line to be vertical."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_vertical",
                   sketch_name=sketch_name, geo_idx=geo_idx, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_lock(sketch_name: str, geo_idx: int, point_idx: int,
                          doc_name: str = None) -> str:
    """Lock a point at its current position."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_lock",
                   sketch_name=sketch_name, geo_idx=geo_idx, point_idx=point_idx, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_block(sketch_name: str, geo_idx: int,
                           doc_name: str = None) -> str:
    """Block a geometry element (prevent any movement)."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_block",
                   sketch_name=sketch_name, geo_idx=geo_idx, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_distance(sketch_name: str, geo_idx1: int, point_idx1: int,
                              geo_idx2: int, point_idx2: int, value: float,
                              doc_name: str = None) -> str:
    """Set distance between two points."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_distance",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, point_idx1=point_idx1,
                   geo_idx2=geo_idx2, point_idx2=point_idx2, value=value, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_length(sketch_name: str, geo_idx: int, value: float,
                            doc_name: str = None) -> str:
    """Set the length of a line segment in mm."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_length",
                   sketch_name=sketch_name, geo_idx=geo_idx, value=value, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_distance_x(sketch_name: str, geo_idx: int, point_idx: int,
                                value: float, doc_name: str = None) -> str:
    """Set horizontal distance from origin to a point."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_distance_x",
                   sketch_name=sketch_name, geo_idx=geo_idx, point_idx=point_idx,
                   value=value, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_distance_y(sketch_name: str, geo_idx: int, point_idx: int,
                                value: float, doc_name: str = None) -> str:
    """Set vertical distance from origin to a point."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_distance_y",
                   sketch_name=sketch_name, geo_idx=geo_idx, point_idx=point_idx,
                   value=value, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_distance_x_between(sketch_name: str,
                                        geo_idx1: int, point_idx1: int,
                                        geo_idx2: int, point_idx2: int,
                                        value: float, doc_name: str = None) -> str:
    """Set signed horizontal distance in mm between two sketch points."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_distance_x_between",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, point_idx1=point_idx1,
                   geo_idx2=geo_idx2, point_idx2=point_idx2, value=value, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_distance_y_between(sketch_name: str,
                                        geo_idx1: int, point_idx1: int,
                                        geo_idx2: int, point_idx2: int,
                                        value: float, doc_name: str = None) -> str:
    """Set signed vertical distance in mm between two sketch points."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_distance_y_between",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, point_idx1=point_idx1,
                   geo_idx2=geo_idx2, point_idx2=point_idx2, value=value, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_angle(sketch_name: str, geo_idx1: int, geo_idx2: int,
                           angle: float, doc_name: str = None) -> str:
    """Set angle between two lines (in degrees)."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_angle",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, geo_idx2=geo_idx2,
                   angle=angle, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_angle_to_axis(sketch_name: str, geo_idx: int, angle: float,
                                   doc_name: str = None) -> str:
    """Set a line angle in degrees relative to the sketch-local positive X axis."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_angle_to_axis",
                   sketch_name=sketch_name, geo_idx=geo_idx, angle=angle, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_radius(sketch_name: str, geo_idx: int, radius: float,
                            doc_name: str = None) -> str:
    """Set radius of a circle or arc."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_radius",
                   sketch_name=sketch_name, geo_idx=geo_idx, radius=radius, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_diameter(sketch_name: str, geo_idx: int, diameter: float,
                              doc_name: str = None) -> str:
    """Set the diameter of a circle or arc in mm."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_diameter",
                   sketch_name=sketch_name, geo_idx=geo_idx, diameter=diameter, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_point_on_object(sketch_name: str, geo_idx: int, point_idx: int,
                                     target_geo_idx: int, doc_name: str = None) -> str:
    """Constrain a sketch point onto another curve or a sketch axis."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_point_on_object",
                   sketch_name=sketch_name, geo_idx=geo_idx, point_idx=point_idx,
                   target_geo_idx=target_geo_idx, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_set_constraint_value(sketch_name: str, constraint_idx: int, value: float,
                                doc_name: str = None) -> str:
    """Change a dimensional constraint; angle constraints use degrees, all lengths use mm."""
    result = _call("freecad_ai_bridge.sketcher_ops", "set_constraint_value",
                   sketch_name=sketch_name, constraint_idx=constraint_idx,
                   value=value, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_set_constraint_mode(sketch_name: str, constraint_idx: int,
                               driving: bool = None, active: bool = None,
                               doc_name: str = None) -> str:
    """Change a constraint between driving/reference and active/inactive; provide at least one mode."""
    result = _call("freecad_ai_bridge.sketcher_ops", "set_constraint_mode",
                   sketch_name=sketch_name, constraint_idx=constraint_idx,
                   driving=driving, active=active, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_delete_constraint(sketch_name: str, constraint_idx: int,
                             doc_name: str = None) -> str:
    """Delete one constraint from a sketch."""
    result = _call("freecad_ai_bridge.sketcher_ops", "delete_constraint",
                   sketch_name=sketch_name, constraint_idx=constraint_idx,
                   doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# PartDesign Tools
# =============================================================================


@mcp.tool()
def partdesign_body(name: str = "Body", doc_name: str = None) -> str:
    """Create a new PartDesign Body (container for features)."""
    result = _call("freecad_ai_bridge.partdesign_ops", "create_body", name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_pad(sketch_name: str, length: float, name: str = "Pad",
                   symmetric: bool = False, reversed: bool = False,
                   doc_name: str = None) -> str:
    """Pad (extrude) a sketch to create a solid.

    Args:
        sketch_name: Name of the sketch to pad
        length: Extrusion length in mm
        symmetric: Pad equally in both directions
        reversed: Pad in reverse direction
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "pad",
                   sketch_name=sketch_name, length=length, name=name,
                   symmetric=symmetric, reversed=reversed, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_pocket(sketch_name: str, length: float = 10.0, name: str = "Pocket",
                      through_all: bool = False, reversed: bool = False,
                      doc_name: str = None) -> str:
    """Create a pocket (subtractive extrusion) from a sketch.

    Args:
        length: Pocket depth (ignored if through_all=True)
        through_all: Cut through entire part
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "pocket",
                   sketch_name=sketch_name, length=length, name=name,
                   through_all=through_all, reversed=reversed, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_revolution(sketch_name: str, angle: float = 360.0,
                          name: str = "Revolution", axis: str = "V",
                          reversed: bool = False, doc_name: str = None) -> str:
    """Revolve a sketch around an axis to create a solid of revolution.

    Args:
        angle: Revolution angle in degrees (360 = full)
        axis: 'V' (vertical/Y-axis), 'H' (horizontal/X-axis), 'N' (normal/Z-axis)
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "revolution",
                   sketch_name=sketch_name, angle=angle, name=name,
                   axis=axis, reversed=reversed, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_groove(sketch_name: str, angle: float = 360.0,
                      name: str = "Groove", axis: str = "V",
                      reversed: bool = False, doc_name: str = None) -> str:
    """Create a groove (subtractive revolution) - cuts material by revolving a sketch."""
    result = _call("freecad_ai_bridge.partdesign_ops", "groove",
                   sketch_name=sketch_name, angle=angle, name=name,
                   axis=axis, reversed=reversed, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_loft(sketch_names: list, name: str = "Loft",
                    solid: bool = True, ruled: bool = False,
                    closed: bool = False, doc_name: str = None) -> str:
    """Create a loft (blend) between multiple sketch profiles.

    Args:
        sketch_names: List of sketch names in order (at least 2)
        ruled: Use ruled surfaces (straight edges between profiles)
        closed: Connect last profile back to first
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "loft",
                   sketch_names=sketch_names, name=name, solid=solid,
                   ruled=ruled, closed=closed, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_sweep(sketch_name: str, spine_name: str, name: str = "Sweep",
                     solid: bool = True, doc_name: str = None) -> str:
    """Sweep a profile sketch along a spine/path.

    Args:
        sketch_name: Profile sketch
        spine_name: Path sketch or edge to sweep along
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "sweep",
                   sketch_name=sketch_name, spine_name=spine_name,
                   name=name, solid=solid, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_hole(sketch_name: str, diameter: float, depth: float,
                    name: str = "Hole", threaded: bool = False,
                    thread_type: str = "ISO", thread_size: str = "M6",
                    doc_name: str = None) -> str:
    """Create a hole feature (positioned by sketch points).

    Args:
        sketch_name: Sketch with center point(s) for hole positions
        diameter: Hole diameter in mm
        depth: Hole depth in mm
        threaded: Create threaded hole
        thread_size: Thread size (e.g., 'M6', 'M8', 'M10')
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "hole",
                   sketch_name=sketch_name, diameter=diameter, depth=depth,
                   name=name, threaded=threaded, thread_type=thread_type,
                   thread_size=thread_size, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_fillet(base_name: str, edges: list, radius: float,
                     name: str = "Fillet", doc_name: str = None) -> str:
    """Add fillet (rounded edges) to a feature.

    Args:
        base_name: Name of the feature to fillet
        edges: List of edge names, e.g. ["Edge1", "Edge2", "Edge5"]
        radius: Fillet radius in mm
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "fillet",
                   base_name=base_name, edges=edges, radius=radius,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_chamfer(base_name: str, edges: list, size: float,
                       name: str = "Chamfer", doc_name: str = None) -> str:
    """Add chamfer (beveled edges) to a feature.

    Args:
        base_name: Name of the feature to chamfer
        edges: List of edge names, e.g. ["Edge1", "Edge3"]
        size: Chamfer size in mm
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "chamfer",
                   base_name=base_name, edges=edges, size=size,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_thickness(base_name: str, faces: list, value: float,
                         name: str = "Thickness", doc_name: str = None) -> str:
    """Shell a solid - removes faces and offsets remaining walls.

    Args:
        base_name: Feature name
        faces: List of face names to remove, e.g. ["Face1"]
        value: Wall thickness in mm
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "thickness",
                   base_name=base_name, faces=faces, value=value,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_draft(base_name: str, faces: list, angle: float,
                     name: str = "Draft", doc_name: str = None,
                     plane_name: str = None) -> str:
    """Add draft angle to faces (for mold release).

    Args:
        faces: List of face names to draft
        angle: Draft angle in degrees
        plane_name: Required neutral plane, e.g. 'Pad.Face6' or a datum plane name
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "draft",
                   base_name=base_name, faces=faces, angle=angle,
                   name=name, doc_name=doc_name, plane_name=plane_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_linear_pattern(feature_name: str, direction: str = "X",
                              length: float = 100.0, occurrences: int = 3,
                              name: str = "LinearPattern", doc_name: str = None) -> str:
    """Create a linear pattern (array) of a feature.

    Args:
        feature_name: Feature to pattern
        direction: 'X', 'Y', or 'Z'
        length: Total span of the pattern in mm
        occurrences: Number of copies including original
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "linear_pattern",
                   feature_name=feature_name, direction=direction,
                   length=length, occurrences=occurrences,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_polar_pattern(feature_name: str, axis: str = "Z",
                             angle: float = 360.0, occurrences: int = 6,
                             name: str = "PolarPattern", doc_name: str = None) -> str:
    """Create a polar (circular) pattern of a feature.

    Args:
        axis: Rotation axis - 'X', 'Y', or 'Z'
        angle: Total angle span in degrees
        occurrences: Number of copies including original
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "polar_pattern",
                   feature_name=feature_name, axis=axis,
                   angle=angle, occurrences=occurrences,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_mirrored(feature_name: str, plane: str = "XY",
                        name: str = "Mirrored", doc_name: str = None) -> str:
    """Mirror a feature about a plane (XY, XZ, or YZ)."""
    result = _call("freecad_ai_bridge.partdesign_ops", "mirrored",
                   feature_name=feature_name, plane=plane,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Part Primitives
# =============================================================================


@mcp.tool()
def part_box(length: float, width: float, height: float,
             x: float = 0, y: float = 0, z: float = 0,
             name: str = "Box", doc_name: str = None) -> str:
    """Create a box (Part primitive). Position at (x, y, z)."""
    result = _call("freecad_ai_bridge.part_ops", "make_box",
                   length=length, width=width, height=height,
                   x=x, y=y, z=z, name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def part_cylinder(radius: float, height: float,
                  x: float = 0, y: float = 0, z: float = 0,
                  angle: float = 360.0, name: str = "Cylinder",
                  doc_name: str = None) -> str:
    """Create a cylinder (Part primitive). Angle < 360 for partial cylinder."""
    result = _call("freecad_ai_bridge.part_ops", "make_cylinder",
                   radius=radius, height=height, x=x, y=y, z=z,
                   angle=angle, name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def part_sphere(radius: float, x: float = 0, y: float = 0, z: float = 0,
                name: str = "Sphere", doc_name: str = None) -> str:
    """Create a sphere (Part primitive)."""
    result = _call("freecad_ai_bridge.part_ops", "make_sphere",
                   radius=radius, x=x, y=y, z=z, name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def part_cone(radius1: float, radius2: float, height: float,
              x: float = 0, y: float = 0, z: float = 0,
              name: str = "Cone", doc_name: str = None) -> str:
    """Create a cone (Part primitive). radius2=0 for pointed cone."""
    result = _call("freecad_ai_bridge.part_ops", "make_cone",
                   radius1=radius1, radius2=radius2, height=height,
                   x=x, y=y, z=z, name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def part_torus(radius1: float, radius2: float,
               x: float = 0, y: float = 0, z: float = 0,
               name: str = "Torus", doc_name: str = None) -> str:
    """Create a torus (donut shape). radius1=major, radius2=minor."""
    result = _call("freecad_ai_bridge.part_ops", "make_torus",
                   radius1=radius1, radius2=radius2,
                   x=x, y=y, z=z, name=name, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Boolean Operations
# =============================================================================


@mcp.tool()
def boolean_fuse(obj_names: list, name: str = "Fuse", doc_name: str = None) -> str:
    """Fuse (union/add) multiple objects together."""
    result = _call("freecad_ai_bridge.part_ops", "boolean_fuse",
                   obj_names=obj_names, name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def boolean_cut(base_name: str, tool_name: str, name: str = "Cut",
                doc_name: str = None) -> str:
    """Cut (subtract) tool from base."""
    result = _call("freecad_ai_bridge.part_ops", "boolean_cut",
                   base_name=base_name, tool_name=tool_name,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def boolean_common(obj_names: list, name: str = "Common",
                   doc_name: str = None) -> str:
    """Common (intersection) of multiple objects."""
    result = _call("freecad_ai_bridge.part_ops", "boolean_common",
                   obj_names=obj_names, name=name, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Transform
# =============================================================================


@mcp.tool()
def set_placement(obj_name: str, x: float = 0, y: float = 0, z: float = 0,
                  rx: float = 0, ry: float = 0, rz: float = 0,
                  doc_name: str = None) -> str:
    """Set position and X/Y/Z rotations in degrees, applied X then Y then Z."""
    result = _call("freecad_ai_bridge.part_ops", "set_placement",
                   obj_name=obj_name, x=x, y=y, z=z, rx=rx, ry=ry, rz=rz, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def move_object(obj_name: str, dx: float = 0, dy: float = 0, dz: float = 0,
                doc_name: str = None) -> str:
    """Move an object by a relative offset."""
    result = _call("freecad_ai_bridge.part_ops", "move_object",
                   obj_name=obj_name, dx=dx, dy=dy, dz=dz, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def rotate_object(obj_name: str, axis_x: float = 0, axis_y: float = 0,
                  axis_z: float = 1, angle: float = 0,
                  doc_name: str = None) -> str:
    """Rotate an object around an axis (angle in degrees)."""
    result = _call("freecad_ai_bridge.part_ops", "rotate_object",
                   obj_name=obj_name, axis_x=axis_x, axis_y=axis_y,
                   axis_z=axis_z, angle=angle, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def scale_object(obj_name: str, factor: float, name: str = None,
                 doc_name: str = None) -> str:
    """Scale an object uniformly (creates a scaled copy)."""
    result = _call("freecad_ai_bridge.part_ops", "scale_object",
                   obj_name=obj_name, factor=factor, name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def mirror_object(obj_name: str, plane: str = "XY", name: str = None,
                  doc_name: str = None) -> str:
    """Mirror an object across a plane (XY, XZ, or YZ)."""
    result = _call("freecad_ai_bridge.part_ops", "mirror_object",
                   obj_name=obj_name, plane=plane, name=name, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# View & Visualization
# =============================================================================


@mcp.tool()
def screenshot(width: int = 800, height: int = 600, view: str = None,
               doc_name: str = None) -> Image:
    """Capture a screenshot of the FreeCAD 3D view.

    Args:
        view: Optional camera preset - 'isometric', 'front', 'back', 'top', 'bottom', 'left', 'right'
    Returns:
        Native MCP PNG image content
    """
    result = _call("freecad_ai_bridge.view_ops", "get_screenshot",
                   width=width, height=height, view=view, doc_name=doc_name)
    return Image(data=base64.b64decode(result["image_base64"]), format="png")


@mcp.tool()
def set_view(direction: str) -> str:
    """Set the 3D view direction: 'isometric', 'front', 'back', 'top', 'bottom', 'left', 'right'."""
    result = _call("freecad_ai_bridge.view_ops", "set_view", direction=direction)
    return json.dumps(result)


@mcp.tool()
def fit_view() -> str:
    """Zoom to fit all objects in view."""
    result = _call("freecad_ai_bridge.view_ops", "fit_all")
    return json.dumps(result)


@mcp.tool()
def set_visibility(obj_name: str, visible: bool, doc_name: str = None) -> str:
    """Show or hide an object."""
    result = _call("freecad_ai_bridge.view_ops", "set_visibility",
                   obj_name=obj_name, visible=visible, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def set_color(obj_name: str, r: float, g: float, b: float,
              doc_name: str = None) -> str:
    """Set object color (RGB values 0.0-1.0)."""
    result = _call("freecad_ai_bridge.view_ops", "set_color",
                   obj_name=obj_name, r=r, g=g, b=b, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def set_transparency(obj_name: str, transparency: int, doc_name: str = None) -> str:
    """Set object transparency (0=opaque, 100=fully transparent)."""
    result = _call("freecad_ai_bridge.view_ops", "set_transparency",
                   obj_name=obj_name, transparency=transparency, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Export / Import
# =============================================================================


@mcp.tool()
def export_step(path: str, obj_names: list = None, doc_name: str = None) -> str:
    """Export to STEP format (industry standard)."""
    result = _call("freecad_ai_bridge.view_ops", "export_step",
                   path=path, obj_names=obj_names, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def export_stl(path: str, obj_names: list = None, doc_name: str = None) -> str:
    """Export to STL format (for 3D printing)."""
    result = _call("freecad_ai_bridge.view_ops", "export_stl",
                   path=path, obj_names=obj_names, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def import_step(path: str, doc_name: str = None) -> str:
    """Import a STEP file."""
    result = _call("freecad_ai_bridge.view_ops", "import_step",
                   path=path, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def import_stl(path: str, doc_name: str = None) -> str:
    """Import an STL file."""
    result = _call("freecad_ai_bridge.view_ops", "import_stl",
                   path=path, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Measurement & Utilities
# =============================================================================


@mcp.tool()
def measure(obj_name: str, doc_name: str = None) -> str:
    """Measure an object: volume, area, bounding box, center of mass."""
    result = _call("freecad_ai_bridge.view_ops", "measure_object",
                   obj_name=obj_name, doc_name=doc_name)
    return json.dumps(result, indent=2)


@mcp.tool()
def undo(doc_name: str = None) -> str:
    """Undo the last operation."""
    result = _call("freecad_ai_bridge.view_ops", "undo", doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def redo(doc_name: str = None) -> str:
    """Redo the last undone operation."""
    result = _call("freecad_ai_bridge.view_ops", "redo", doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Fallback: Execute Python
# =============================================================================


@mcp.tool()
def execute_python(code: str) -> str:
    """Execute arbitrary Python code in FreeCAD (for operations not covered by other tools).

    The code runs in FreeCAD's Python environment with access to all modules.
    Set a variable named 'result' to return data.

    Example: "import Part; result = Part.makeBox(10,10,10).Volume"
    """
    result = _conn.execute(code)
    return json.dumps({"result": result})


# =============================================================================
# Entry point
# =============================================================================


@mcp.tool()
def partdesign_subtractive_loft(sketch_names: list, name: str = "SubtractiveLoft",
                                solid: bool = True, ruled: bool = False,
                                doc_name: str = None) -> str:
    """Cut a solid using a loft between at least two sketch profiles."""
    return json.dumps(_call("freecad_ai_bridge.partdesign_ops", "subtractive_loft",
                           sketch_names=sketch_names, name=name, solid=solid,
                           ruled=ruled, doc_name=doc_name))


@mcp.tool()
def partdesign_subtractive_pipe(sketch_name: str, spine_name: str,
                                name: str = "SubtractivePipe", doc_name: str = None) -> str:
    """Cut a solid by sweeping a sketch profile along a path sketch."""
    return json.dumps(_call("freecad_ai_bridge.partdesign_ops", "subtractive_pipe",
                           sketch_name=sketch_name, spine_name=spine_name,
                           name=name, doc_name=doc_name))


@mcp.tool()
def part_fillet(obj_name: str, edges: list, radius: float,
                name: str = "Fillet", doc_name: str = None) -> str:
    """Round edges of a Part object; edges are 1-based indices or names such as Edge1."""
    return json.dumps(_call("freecad_ai_bridge.part_ops", "part_fillet",
                           obj_name=obj_name, edges=edges, radius=radius,
                           name=name, doc_name=doc_name))


@mcp.tool()
def part_chamfer(obj_name: str, edges: list, size: float,
                 name: str = "Chamfer", doc_name: str = None) -> str:
    """Bevel edges of a Part object; edges are 1-based indices or names such as Edge1."""
    return json.dumps(_call("freecad_ai_bridge.part_ops", "part_chamfer",
                           obj_name=obj_name, edges=edges, size=size,
                           name=name, doc_name=doc_name))


@mcp.tool()
def export_obj(path: str, obj_names: list = None, doc_name: str = None) -> str:
    """Export selected objects, or visible final objects, as a Wavefront OBJ mesh."""
    return json.dumps(_call("freecad_ai_bridge.view_ops", "export_obj",
                           path=path, obj_names=obj_names, doc_name=doc_name))


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
