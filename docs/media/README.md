# README demo GIFs

Short demos (640x480, 4-6 frames each) for the README. Created on 2026-11-20 with FreeCAD 1.1.4 in an own, isolated
GUI instance (own port, normal mode, raw Python disabled) and an MCP stdio client; the models were built **only** through the
structured MCP tools (no `execute_python`). Frames: `capture_view` (3D) and `techdraw_export_page` (PDF rendered to PNG);
captions added afterwards. Raw frames and test models were kept in TEMP and are not part of the repository.

| File | Shows | Tools used |
|------|-------|------------|
| `build-housing.gif` | Housing from a spreadsheet-driven sketch: sketch, pad, pocket (3 mm walls), 4 mounting holes | `create_spreadsheet`, `create_sketch`, `sketch_*`, `set_expression`, `partdesign_pad/pocket/hole`, `capture_view` |
| `parametric-edit.gif` | Same model while `LengthParam` 80 -> 100 -> 130 mm and `HeightParam` 45 mm are changed; volume updates | `set_spreadsheet_cells`, `measure`, `capture_view` |
| `techdraw-views.gif` | A4 page with top, front, side view and section A-A; after a model edit (110 mm) the page updates | `techdraw_create_page/view/section`, `techdraw_update_page`, `techdraw_export_page` |
| `assembly-joints.gif` | Native Assembly: grounded base, revolute joint (arm 0..90 deg) and slider joint (0..20 mm); no collisions reported | `assembly_create/add_component/create_joint/set_component_pose/check_collisions`, `capture_view` |
