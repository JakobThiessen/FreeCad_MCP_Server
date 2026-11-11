# Changelog

Alle relevanten Aenderungen am FreeCAD-MCP-Server, je abgeschlossenem Schritt
(Stufe, Teilstufe oder Wartungsschritt). Neueste Eintraege stehen oben; jeder
Eintrag nennt Datum, Commit/Tag (sofern vorhanden), neue Funktionen, geaenderte
Vertraege/Verhalten, Fehlerbehebungen und den Pruefnachweis in Kurzform.
Ausfuehrliche Laufdaten: [memory.md](memory.md); Vertraege: [docs/CONTRACTS.md](docs/CONTRACTS.md).

Kategorien: **Neu** (Tools/Optionen), **Geaendert** (Vertrag/Verhalten, Migrationen
markiert), **Behoben** (Fehler mit Ursache), **Tests**, **Doku**.

## 2026-11-11 - Stufe 12b-2a PartDesign Datum/Extrusion/Rotation/Loft/Pipe (Tag `stage-12b2a-2026-11-11`)

194 Tools, Bridge 0.11.0, Paket 0.1.0 (unveraendert). Referenzlaufzeit FreeCAD 1.1.4.

- **Behoben:** `partdesign_datum` mit Support: Achse auf Zylinderflaeche/Gerade und Punkt auf
  Vertex meldeten Erfolg, waren nativ aber ungueltig (falsche MapModes). Jetzt `TwoPointLine`,
  `AxisOfCurvature` an einer Kreisrandkante (auch Teilzylinder) bzw. `Vertex`; nicht
  berechenbare Datums werden abgelehnt.
- **Behoben:** Pocket, Groove und Subtractive Loft erzeugten ohne Basis-Solid Material;
  Revolution um Achse N lieferte ein Volumen-0-Solid als Erfolg; `transformed` an Pfaden mit
  Knick fegte still nur das erste Segment; doppelte `path_edges` ergaben Volumen ~0;
  `angle + second_angle > 360` ergab ein falsches Teilvolumen.
- **Behoben:** `measure` liefert `center_of_mass` auch fuer generische Shapes (z. B. Pocket).
- **Geaendert (Migration, Ablehnung bisher akzeptierter Eingaben):** Subtraktive Features
  ohne Basis-Solid; Winkelsumme > 360; `axis_name` aus fremdem Body; Loft `closed` mit
  2 Profilen sowie `closed`+`ruled`; Pocket `through_all` mit abweichendem `end_condition`;
  `second_length` ohne `two_lengths`; `transformed` bei Knick; doppelte `path_edges`; Profile
  ausserhalb eines PartDesign Bodys oder Nicht-Skizzen. Achse `N` bleibt formal, scheitert an
  der neuen Werkzeugvolumenpruefung. Details: CONTRACTS "12b-2a".
- **Neu (additiv):** `partdesign_datum` meldet `attachment` (map_mode, subelements);
  `path_edges` nimmt revisionsgepruefte Kantenauswahlen; klarere Fehlermeldungen
  ("produced invalid BRep geometry", up_to_face-Ziel muss Flaeche sein, Datum-Support-Dokument).
- **Tests:** neues MCP-Gate `tests/mcp_smoke.py --stage12b-partdesign-a-only` (zweimal je
  3259 Aufrufe, 70 Negativfaelle, 51 Bodies, Undo/Redo je Mutation, FCStd-Reopen + zweite
  Aenderung); vier native Tests `test_stage12b_partdesign_*`, Stufe-6-Datumtest korrigiert.
  Ergebnis: Host 55/55, nativ 67/67, `--stage12-only` 30/30, `--stage12b-sketcher-only` 2x,
  12b-2a-Gate 2x bestanden.
- **Doku:** CONTRACTS "12b-2a", COVERAGE I19-I22/N10-N11, ACCEPTANCE, README-Checkliste,
  AGENTS-Kurzstatus, memory.

## 2026-11-11 - Stufe 12b-1 Sketcher, W1, W2 (Tag `stage-12b1-2026-11-11`)

194 Tools, Bridge 0.11.0, Paket 0.1.0 (unveraendert). Referenzlaufzeit FreeCAD 1.1.4.

### 12b-1 Sketcher-Einzelvarianten-Audit (2026-11-11)

- **Neu:** `sketch_info` liefert zusaetzlich `point` (Punktgeometrie), `parameter_range`
  (Boegen, rad), `major_radius`/`minor_radius`/`major_axis` (Ellipse), `degree`/`poles`/
  `periodic` (B-Spline), `external_geometries` (Index -3.., Typ, Koordinaten) und
  `attachment.placement`.
- **Geaendert (Migration):** `conflicting/redundant/partially_redundant_constraint_indices`
  sind jetzt 0-basiert wie alle anderen Constraint-Indizes (vorher FreeCAD-1-basiert).
- **Geaendert:** Alle Sketch-Erzeuger, Constraints und Bearbeitungen validieren Werte,
  Geometrietypen und Punktpositionen **vor** der Mutation und melden die Ursache
  (vorher teils stilles Annehmen oder Rollback mit "solver status -5"). Neu abgelehnt:
  Kreis/Bogen r<=0, Bogen-Sweep ausserhalb (0, 2*pi) bzw. umgekehrte Winkel, Ellipse
  minor>=major, Punkt-Punkt-Abstand <=0, Tangent mit nur einem point_idx, Wert setzen auf
  Referenz-Constraints, `driving` fuer Nicht-Mass-Constraints, Equal fuer Ellipsenpaare.
- **Geaendert:** `sketch_trim` verlangt einen Pick-Punkt auf der Kurve (<=0,001 mm);
  `sketch_extend` interpretiert das Inkrement auch bei Boegen als Laenge in mm.
- **Geaendert (dokumentiert, keine Migration):** `create_sketch` XZ/YZ-Orientierung bleibt
  (XZ: lokal y=-Z, Normale +Y; YZ: lokal x=-Z, y=+Y, Normale +X).
- **Behoben:** `sketch_set_attachment(support_name=Datum)` wirkte nicht - FreeCAD verwarf
  den Support mit leerer Unterelementliste still.
- **Behoben:** `sketch_info` machte ausgegebene Subelement-Auswahlen ungueltig, weil
  `Sketch.solve()` das Flag `FullyConstrained` schreibt; der Revisionszaehler in
  `geometry_ops` ignoriert dieses Solver-Flag.
- **Behoben:** Externer Index bei mehreren Kanten desselben Quellobjekts falsch; Loeschen
  gueltiger externer Geometrie wurde abgelehnt.
- **Behoben:** Undo/Redo nach `sketch_extend` an Boegen wirkungslos bzw. falsch (natives
  In-place-Aendern); extend/trim/fillet sichern die Geometrie jetzt in der Transaktion.
- **Behoben:** Trim mit Pick-Punkt neben der Kurve fuehrte zu C++-Ausnahme bzw. Absturz.
- **Tests:** neues MCP-Gate `tests/mcp_smoke.py --stage12b-sketcher-only` (zweimal je
  1153 Aufrufe, 82 Negativfaelle, 23 Skizzen, Undo/Redo je Variante, FCStd-Reopen);
  drei native Tests `test_stage12b_sketcher_*`. Ergebnis: Host 55/55, nativ 63/63,
  `--stage12-only` 30/30, 12b-Gate 2x bestanden.
- **Doku:** 12b-Plan (Teilstufen 12b-1..12b-5) in memory; CONTRACTS "12b-1",
  COVERAGE/ACCEPTANCE/README-Checkliste; CHANGELOG eingefuehrt.

### W2 FreeCAD 1.1.4 als Referenzlaufzeit (2026-11-10/11)

- **Geaendert:** Nur FreeCAD 1.1.4 zugesagt, 1.1.1 "frueher geprueft"; Capabilities fuer
  Draft/Mesh/Austausch/STEP-Schema/TechDraw aus `operations.TESTED_PATCH_VERSIONS`
  ("1.1.1", "1.1.4").
- **Neu:** `undo`/`redo` melden additiv `draft_wire_endpoint_repairs`; `capture_view`
  meldet `active_document_before`/`active_document`.
- **Behoben:** Draft-Wire-Endpunkt verschob sich nach Undo/Redo/Rollback (ungeordnete
  Property-Wiederherstellung in `Wire.onChanged`); gezielte Reparatur in `transactions`.
- **Geaendert:** Aktivdokument gilt als GUI-eigener Zustand (keine Fokus-Eingriffe).
- **Tests:** nativ 2x 60/60, `--stage12-only` 30/30 auf frischen 1.1.4-GUIs.

### W1 MCP-SDK abgesichert (2026-11-10)

- **Geaendert:** `pyproject.toml` `mcp[cli]>=1.30.0,<2` (SDK 2.x entfernt FastMCP-Pfad).
- **Tests:** 194 Schemas identisch zu 1.27.1, Host 55/55, `--stage12-only` 30/30.

## 2026-10-10 - Stufe 12a (Commit `f1ca258`)

- **Geaendert:** Normalmodus ohne freie Codeausfuehrung (`raw_python_disabled`,
  `rpc_not_allowed`); Entwickler-Opt-in nur `FREECAD_MCP_ALLOW_RAW_PYTHON=1`.
- **Behoben:** `capture_view` veraenderte Kamera/Aktivierung fremder Dokumente;
  Assembly-Gelenke ohne nativen `ViewProviderJoint` (Fehler nach FCStd-Reopen).
- **Tests:** `--stage12-only` (15 Gates je Durchlauf, zweimal), 113 Normalmodus-
  Negativchecks; Host 55/55, nativ 59/59.

## 2026-10-09 - Stufen 10 und 11 (Commit `c465e93`, Tag `stage-11-2026-10-09`)

- **Neu 10 TechDraw:** `techdraw_list_templates`, `techdraw_create_page`,
  `techdraw_create_view`, `techdraw_set_layout`, `techdraw_update_page`,
  `techdraw_inspect_page`, `techdraw_export_page` (PDF/SVG), `techdraw_create_projection_group`,
  `techdraw_create_section`, `techdraw_create_detail`, `techdraw_create_dimension`
  (length/distance/distance_x/distance_y/diameter/radius/angle), `techdraw_create_annotation`,
  `techdraw_create_leader`, `techdraw_list_geometry` (182 Tools).
- **Neu 11a Draft:** `draft_create_element`, `draft_edit_element` (Linie, Wire, Rechteck,
  Kreis, Bogen, Text, Label), `draft_create_array`, `draft_edit_array` (Ortho/Polar),
  `draft_inspect` (187 Tools).
- **Neu 11b/11c Mesh/Austausch:** `mesh_create`, `mesh_inspect`, `mesh_repair`,
  `mesh_from_shape`, `mesh_to_shape`, `exchange_export`, `exchange_import`
  (STEP AP214/AP242, STL ASCII/binaer, OBJ, DXF, SVG) (194 Tools).

## 2026-10-09 - Versionsaudit FreeCAD 1.1.4 (Commit `762d4dc`, Tag `bridge-v0.11.0`)

- **Neu:** `techdraw_scrub_edges` (168 Tools), Bridge 0.11.0.
- **Geaendert:** Freie Python-Ausfuehrung standardmaessig gesperrt; Repository bereinigt.

## 2026-10-01 - Stufen 8 und 9 (Commit `730aa0f`)

- **Neu 8a Jobs:** `start_batch_job`, `get_job`, `cancel_job`, `list_objects_page`
  (Bridge 0.9.0, 159 Tools); A1-A3-Gesamtworkflows per MCP abgenommen.
- **Neu 9 Assembly:** `assembly_create`, `assembly_add_component`, `assembly_set_grounded`,
  `assembly_create_joint` (fixed/revolute/slider/cylindrical/ball), `assembly_set_joint`,
  `assembly_set_component_pose`, `assembly_inspect`, `assembly_check_collisions`
  (Bridge 0.10.0, 167 Tools).

## 2026-09-29 - Stufen 6 und 7 (Commits `bbf292a`, `3307fff`)

- **Neu 6 PartDesign:** `partdesign_datum`, `partdesign_multi_transform`,
  `partdesign_edit_feature`; Pad/Pocket-Endbedingungen, Revolution/Groove-Achsen und
  zwei Winkel, Pipe-Modi, Hole-Senkungen/Gewindemetadaten, Chamfer zwei Abstaende,
  Thickness/Draft-Optionen (Bridge 0.7.0, 139 Tools).
- **Neu 7 Part:** `part_wire`, `part_face`, `part_shell`, `part_solid`, `part_extrude`,
  `part_revolve`, `part_loft`, `part_sweep`, `part_validate`, `part_section`,
  `part_split`, `part_offset_2d`, `part_offset_shape`, `part_refine`, `part_sew`,
  `part_repair` (Bridge 0.8.0, 155 Tools).

## 2026-09-16/17 - Stufen 1 bis 5 (Commit `2d3d1cf`)

- **Stufe 1:** Abdeckungsmatrix `docs/COVERAGE.md` und Abnahmevertrag `docs/ACCEPTANCE.md`
  (Ausgangsbasis 82 Tools).
- **Neu 2:** `get_capabilities`, `resolve_reference`, `execute_batch`; einheitliche
  `ContractResponse`, Transaktionen, Vorschau (Bridge 0.3.0, 85 Tools).
- **Neu 3:** `inspect_document`, `activate_document`, `recompute_document`,
  `save_document_safe`, `close_document_safe`, `create_container`, `set_container_members`,
  `set_body_tip`, `get_properties`, `set_properties`, `get_expressions`, `set_expression`,
  `create_spreadsheet`, `read_spreadsheet`, `set_spreadsheet_cells`, `set_spreadsheet_alias`,
  `rename_object`, `copy_object`, `create_link`, `get_dependencies`, `preview_delete`,
  `delete_objects` (Bridge 0.4.0, 107 Tools).
- **Neu 4:** `list_subelements`, `select_subelement`, `resolve_subelement`,
  `measure_distance`, `measure_angle`, `check_interference`, `highlight_subelements`,
  `get_view_state`, `capture_view` (Bridge 0.5.0, 116 Tools).
- **Neu 5:** `sketch_move_point`, `sketch_set_construction`, `sketch_delete_geometry`,
  `sketch_add_external`, `sketch_delete_external`, `sketch_set_attachment`, `sketch_trim`,
  `sketch_extend`, `sketch_fillet`, `sketch_copy`, `sketch_mirror`,
  `sketch_constrain_length`, `sketch_constrain_distance_x_between`,
  `sketch_constrain_distance_y_between`, `sketch_constrain_angle_to_axis`,
  `sketch_constrain_diameter`, `sketch_constrain_point_on_object`,
  `sketch_set_constraint_value`, `sketch_set_constraint_mode`, `sketch_delete_constraint`
  (Bridge 0.6.0, 136 Tools).

## 2026-05-24 - Erstveroeffentlichung (Commits `0f4293b`..`ab2cfb1`)

- Ausgangsbasis: MCP-Tools fuer Dokumente, Sketcher, PartDesign, Part, Ansicht/Export und
  `execute_python`, FreeCAD-Addon-Bridge per XML-RPC, README mit Installation und
  Copilot-Einrichtung (im Audit vom 2026-09-15 mit 82 Tools inventarisiert).
