# FreeCAD MCP implementation audit

Date: 2026-09-15. Runtime: FreeCAD 1.1 on Windows; MCP client tested with Python 3.10.

## Scope and result

The original server registered 77 tools, not the 84 advertised in the README.
All existing RPC targets were implemented, but several contained broken FreeCAD
API calls, ignored arguments, or incorrect results. Five additional operations
already existed in the addon but were not exposed through MCP. They are now
available, bringing the total to 82 tools.

This is not full FreeCAD API coverage. FEM, Assembly joints, TechDraw, CAM, and
arbitrary workbench commands are not implemented as dedicated MCP tools.

## Fixed findings

| Area | Finding and correction |
| --- | --- |
| RPC dispatch | The module allowlist was unused. Enforce allowed modules and public functions defined in those modules; reject private and imported callables. |
| Network | Enforce loopback binding, use the configured socket timeout, close server sockets, and stop the executor if startup fails. |
| Python execution | Separate globals and locals broke script functions and comprehensions. Use one fresh namespace per invocation. |
| Queue | Expired queued tasks could execute later. Cancel tasks before execution and reject submissions to a stopped executor. Running kernel computations cannot be forcibly cancelled. |
| Undo/redo | Modeling calls did not create transactions. Group mutations in existing documents, commit success, and roll back failures without taking ownership of an existing transaction. |
| Document lifecycle | Avoid using deleted document wrappers after closing a document. |
| Sketch status | `solve()` is a solver status, not a degree-of-freedom count. Report `DoF` and `FullyConstrained`. |
| Sketch constraints | Replace nonexistent `Lock` constraints with point coordinates/axis constraints. Support symmetry about a line by omitting the symmetry-point argument. |
| Sketch geometry | Respect XZ/YZ offsets, reject invalid bodies/polygons, and keep slot segments connected and tangent with equal arc radii. |
| Pad | Use `SideType` on FreeCAD 1.1 and `Midplane` as an older-version fallback for symmetric pads. |
| Loft/pipe | Remove nonexistent `Solid` properties, validate profile count, use LinkSub spine references, explicitly reject PartDesign shell requests. |
| Patterns | Use Body-origin axis/plane references. Linear-pattern direction had the wrong type; polar axis and mirror plane were previously ignored. |
| Hole | Establish Body membership before assigning depth. Map ISO/UTS aliases and shorthand metric sizes to FreeCAD enumeration values. |
| Draft | Expose a neutral-plane argument and support face references such as `Pad.Face6`. |
| Features | Hide preceding Body tips; report invalid/empty PartDesign results as errors rather than apparent success. |
| Part dress-ups | Store parametric edge/radius lists instead of overwriting a calculated Shape. |
| Placement | Map `rx`, `ry`, `rz` to FreeCAD's yaw/pitch/roll constructor in the correct order. |
| Export | Mesh complete triangles with MeshPart. Export only visible final objects by default; avoid duplicate Body geometry and hidden intermediate features. Reject empty selections. |
| Screenshots | Honor the requested document, validate dimensions/view names, clean unique temporary files, refresh before fitting, and return native MCP image content. |
| Missing tools | Add subtractive loft/pipe, Part fillet/chamfer, and OBJ export. |

## Verification

- 11 local unittest tests pass: namespace isolation, queue cancellation, timeout
  configuration, RPC target restrictions, response errors, all forwarded
  function arguments, public-operation exposure, registration, and MCP images.
- 23 integration tests pass inside FreeCAD: symmetric pads, additive/subtractive
  lofts and pipes, three pattern types, slot geometry, sketch freedom/locking,
  plane offsets, threaded holes, draft, parametric dress-ups, rotation axes,
  STEP/STL/OBJ round trips, empty/hidden export selection, undo/redo/rollback,
  and document closing.
- The MCP stdio smoke test passes through the real server and XML-RPC bridge:
  82 tools registered, modeling, measuring, undo/redo, three export formats,
  PNG image content, and a Python function using script-level imports.
- The demonstration has 17 valid single-solid components, 133 document objects,
  and 18 fully constrained sketches. Its saved document and exports are checked
  by `tests/verify_model.py`; the PNG was visually inspected.

Tests are deliberately not an exhaustive Cartesian product of all parameters.
Every tool's routing is checked, but not every original geometry/constraint tool
has a dedicated live case. FreeCAD versions other than 1.1, remote deployments,
platform-specific installers, and adversarial concurrent clients were not tested.

## Security and compatibility notes

The raw Python filter is not a sandbox. Trusted scripts have the full rights of
the FreeCAD process. The local RPC endpoint has no authentication; do not expose
or forward it to untrusted clients. File operations can overwrite existing paths.

Changed behavior: screenshots are MCP images instead of JSON/base64 text;
`solid=False` for PartDesign loft/pipe is rejected; draft requires a neutral
plane; X/Y/Z placement angles now match their names; empty export lists fail.
An already running operation may finish after a timeout, so inspect state before
retrying it. Arbitrary Python scripts manage their own transactions.

The example is not a manufacturing release: thread geometry is simplified,
clearances and strength are not certified, and not all dimensions are linked to
one master parameter table. Standard Assembly-workbench joints are not used.