# Changelog

Alle relevanten Aenderungen am FreeCAD-MCP-Server, je abgeschlossenem Schritt
(Stufe, Teilstufe oder Wartungsschritt). Neueste Eintraege stehen oben; jeder
Eintrag nennt Datum, Commit/Tag (sofern vorhanden), neue Funktionen, geaenderte
Vertraege/Verhalten, Fehlerbehebungen und den Pruefnachweis in Kurzform.
Ausfuehrliche Laufdaten: [memory.md](memory.md); Vertraege: [docs/CONTRACTS.md](docs/CONTRACTS.md).

Kategorien: **Neu** (Tools/Optionen), **Geaendert** (Vertrag/Verhalten, Migrationen
markiert), **Behoben** (Fehler mit Ursache), **Tests**, **Doku**.

## 2026-11-18 - Wartung nach 12c: Laufzeitdiagnose, Joint-ViewProvider-Migration, 12d-Audit (noch ohne Commit/Tag)

194 Tools, Bridge 0.11.0 (unveraendert). Keine bisher akzeptierte Eingabe abgelehnt.

- **Behoben:** Assembly-Gelenke aus Dokumenten ohne GUI-Proxy (Altstand vor f1ca258) lieferten nach Reopen in frischer GUI
  `'int' object has no attribute 'redrawJointPlacements'` (ViewObject.Proxy war 0). Ursache: Joint/GroundedJoint ohne ViewProvider-Proxy.
- **Geaendert (Migration, additiv):** `_migrate_joint_viewproviders` in `open_document`, `recompute_document` und `_assembly`;
  `open_document` meldet `migrated_joint_viewproviders` nur bei Treffern; `assembly_set_grounded` legt den GroundedJoint-ViewProvider an.
  Vertrag: CONTRACTS "Assembly-Joint-ViewProvider-Migration".
- **Diagnose:** Langsamkeit von `--stage12b-core-only` war lastabhaengig (100-Schritt-Batch > 30-s-GUI-Executor-Limit); auf ruhiger frischer GUI
  2x PASS in 136 s. Kein Code-/Vertragswechsel. Parallele Laeufe auf derselben GUI verfaelschen Ergebnisse.
- **Tests:** `--stage12-only` 50/50 PASS (Addon vor Migration, Report freecad-stage12-mcp-fyzfcnx6); mit Migrationscode `--stage9-only` Exit 0,
  `--stage12b-assembly-only` 2/2 PASS, native Suite 84/84 (inkl. `test_stage12d_joint_viewprovider_migration_after_reopen`), Host 65/65.
- **Tests A3:** Gate-Geometrie erweitert (Spindel x=0..85, 1360 pi, beide Bohrungen); `--stage8-a3-only` 2x PASS. Nur Testgeometrie, kein Serververtrag; `--stage12-only` damit nicht neu gelaufen.
- **Tests Pflichtvarianten:** neue MCP-Faelle `--stage12b-part-only` (3D-Pfad Frenet/Standard, S-Spline Frenet abgelehnt, Bowtie-Face abgelehnt, STEP offene Schale/
  geheilter Vertex), 2x PASS; `--stage12b-mesh-only` Farbpalette 5 Komponenten AP214/AP242, 2x PASS. Gestrichen (Benutzer): 3D-Offset `tangent`, Sketcher-Ausnahmen,
  Assembly-Limits-Erzwingung; als Grenzen in ACCEPTANCE/README/COVERAGE. Offen/Befund: `set_color` auf Link liefert rohen Attributfehler.
- **Doku:** 12d-Kriterienaudit (Notizordner der Sitzung); Stufe 12 bleibt NICHT abgeschlossen, keine Freigabe.

- **Tests (Gesamtlauf):** `--stage12-only` auf dem Endstand (Basis 17bff9a: Migration, A3 x=0..85, neue 12b-part/mesh-Faelle): **50/50 Gates PASS in 2 Laeufen, Exit 0**, `success=true`, 194 Tools, frische eigene GUI (Port 9990, Raw-Python=0, keine parallele Last), ca. 1 h 31 min, Report `%TEMP%/freecad-stage12-mcp-u7a6p15j/report.json`, Log `%TEMP%/w15-stage12.log`; keine Fehlschlaege, keine Timeouts. Stufe 12 damit weiterhin **nicht** abgeschlossen (12d offen).

## 2026-11-18 - Stufe 12c: Installation, Update, Betrieb und Prozessverlust (noch ohne Commit/Tag)

194 Tools, Bridge 0.11.0, Paket 0.1.0 (unveraendert), FreeCAD 1.1.4. Alle Aenderungen additiv, keine bisher akzeptierte Eingabe abgelehnt.

- **Neu:** `get_capabilities.bridge_install` (Pfad, Dateizahl, SHA-256 des geladenen Addons) und `compatibility` (`match`/`mismatch` mit
  Warnung, Host erwartet Bridge 0.11.0); `FREECAD_MCP_TIMEOUT_SECONDS` (0,1..3600, Default 30 s; ungueltig = Startfehler);
  Gate `tests/stage12c_operations.py` (`--phase install|loss|timeout|all`).
- **Geaendert:** `Init.py`/`InitGui.py` suchen den Addon-Ordner in `sys.path` (auch `--module-path`) statt immer den Benutzer-Mod-Pfad
  voranzustellen; Fallback unveraendert.
- **Tests:** Host 65/65; nativ 83/83; `stage12c_operations.py --phase all` 2x PASS: isolierter TEMP-Zyklus Wheel (nur Hostpaket) +
  Addon-Kopie, nativer Autostart, Update Altpaar 0.10.0 -> Neupaar (Hash/Pfad/Version), altes FCStd oeffnet/aendert, Mischzustand-
  Warnung, Rueckrollen, AutoStart aus/Port belegt, MCP-Neustart ohne Doppelmutation, Transport-Timeout ohne verdeckten Retry (Bridge-
  Attrappe zaehlt 1 Aufruf), harter GUI-Prozessverlust (`transport_error`, Job-IDs `unknown`, gespeicherte Datei intakt).
- **Offen/nicht gruen:** `--stage12-only` nicht komplett neu gelaufen (Lauf 1: 15 Basisgates + sketcher PASS, dann abgebrochen wegen Dauer);
  `--stage12b-core-only` scheitert derzeit an der 100-Schritt-Batch-Pruefung (`execution_timeout` >30 s), identisch auf unveraendertem
  HEAD a7094d0 (Maschinenlast). Joint-ViewProvider-Migration nicht bearbeitet; 12d offen.
- **Doku:** ACCEPTANCE (Zuordnung 12c), COVERAGE, CONTRACTS, README, AGENTS, memory.

## 2026-11-17 - Stufe 12b Abschluss: 12b-Gates in `--stage12-only` aufgenommen (noch ohne Commit/Tag)

**Geaendert (nur Tests):** `--stage12-only` enthaelt jetzt 25 Gates je Lauf (15 bisherige + 10 12b-Gates: sketcher, partdesign-a/-b,
part, assembly, draft, mesh, legacy, techdraw, core), 2 Laeufe = 50 Gate-Laeufe.
**Behoben (Test):** `stage12b_legacy` pruefte `queued` des Folgejobs gegen einen 40-Schritt-Batch, der auf warmer GUI schon
fertig sein konnte (Race im ersten Gesamtlauf). Der Batch hat jetzt 100 Schritte (Serverobergrenze).
**Tests:** `--stage12-only` auf frischer GUI (FreeCAD 1.1.4): 50/50 PASS, `success: true`
(`%TEMP%/freecad-stage12-mcp-4f7a1vpy/report.json`); `--stage12b-legacy-only` 2x PASS. Der erste Gesamtlauf
(22 PASS) brach am genannten Race ab. Hinweis: Restrisiko, dass der 100-Schritt-Batch auf sehr schneller Hardware
ebenfalls zu frueh fertig wird, ist nicht ausgeschlossen.

## 2026-11-17 - Stufe 12b-5 Rest: Kriterienzuordnung A4 und N01-N07, Ausdruecke/Auswahl-Vertragsschaerfung (Commit db7b80b, Tag stage-12b5rest-2026-11-17)

194 Tools, Bridge 0.11.0, Paket 0.1.0 (unveraendert). FreeCAD 1.1.4. Benutzerentscheidungen (ask_user): Formelsyntax ablehnen,
Ausdruckseinheit/Endlichkeit ablehnen, Filterkoordinaten begrenzen (Placement-/Vektorgrenze gleichartig angewendet).

- **Neu:** Zuordnungstabellen A4.1-A4.V und N01.1-N07.3 in [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md); Gate `--stage12b-core-only`.
- **Geaendert (Migration, Ablehnung bisher akzeptierter Eingaben):** `set_spreadsheet_cells` lehnt Formeln mit Syntaxfehler ab
  (vorher stilles Textfeld); `set_expression` prueft Endlichkeit und Einheit des Ergebnisses vor dem Binden; Filterkoordinaten
  und Richtungen |v| <= 1e9; Placement-/Vektorposition |x| <= 1e9 mm; `set_container_members` meldet ein Mitglied einer anderen
  Gruppe als `dependency_conflict` (vorher `operation_failed`). Details: CONTRACTS "12b-5 Rest".
- **Behoben:** ein abgelehnter Ausdruck mit falscher Einheit (`Length = 5 deg`) hinterliess nach dem Rollback eine Eigenschaft
  mit der falschen Einheit (`10 deg`); Ausdruecke wie `1/0 mm` liessen die Laenge still auf 0 fallen; `1e300` in
  Auswahlfiltern lieferte `operation_failed`.
- **Tests:** Host 62/62, nativ 83/83, `--stage12b-core-only` 2x je 666 Aufrufe, `--stage9-only` (A4) 2x je 297 Aufrufe mit
  neuen Orakeln (Armgeometrie, Placements nach Reopen, STEP-BBox), `--stage12-only` frische GUI 2x 30/30, alle 12b-Gates
  (sketcher, partdesign-a/-b, part, assembly, draft, mesh, legacy, techdraw) 2x PASS. Das alte Gate `normal_mode` erwartet
  `=import os` jetzt als `invalid_expression`.
- **Doku:** ACCEPTANCE, COVERAGE, CONTRACTS, README, AGENTS, memory.

## 2026-11-17 - Stufe 12b-5 (Teil): Kriterienzuordnung A1-A3, A5/N19 und TechDraw-Variantenaudit (Commit 23c3fc8, Tag `stage-12b5-2026-11-17`)

194 Tools, Bridge 0.11.0, Paket 0.1.0 (unveraendert). Referenzlaufzeit FreeCAD 1.1.4. Benutzerentscheidungen (ask_user):
Nullmasse, Leerschnitte und Zahlengrenzen ablehnen/begrenzen. Nicht erledigt: Zuordnung A4/N01-N07 (12b-5 Rest).

- **Neu:** Zuordnungstabellen A1.1-A3.5, A5.1-A5.7 und N19-Variantenaudit in [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md); neues Gate
  `--stage12b-techdraw-only`.
- **Geaendert (Migration, Ablehnung bisher akzeptierter Eingaben):** `techdraw_create_dimension` lehnt Nullwerte und
  entartete Auswahlen ab (`length` genau eine Kante, `distance*` zwei verschiedene Subelemente oder eine Kante);
  `techdraw_create_section` lehnt eine Schnittebene ab, die das Modell nicht trifft; Massstab 0,001..1000 (Ansicht, Gruppe,
  Schnitt, Detail, Seite), Texthoehe 0,1..100 mm, Leader-Punkte +-1000 mm. Details: CONTRACTS "12b-5".
- **Behoben:** Projektionsgruppe mit Front +-X war nativ undefiniert (`XDirection` parallel zur Blickrichtung);
  Richtungsvektoren werden normiert (1e-11 wurde still durch die Standardrichtung ersetzt, 1e300 scheiterte);
  `set_layout(rotation)` klemmte 370 still auf 360 (jetzt modulo 360); Detail meldete die Standardrichtung statt der
  Basisrichtung; `measure.bounding_box` untertrieb in der GUI gekruemmte Koerper (Flansch z 59,88 statt 60) und ist jetzt BRep-exakt.
- **Tests:** neue Gate-Orakel in A1 (Wand-/Bodenflaechen, Innenmasse, Tip/Objektzustand, STL/STEP-Pruefung), A2 (Hole-Kanten,
  Achse, BBox, Lochzentren, mehrdeutige/veraltete Auswahl), A3 (Innenflaechenabstand, Spindel, STEP je Teil, STL je Teil, Bildtest je Teil),
  A5 (Ansichts-BBox, Texte). Host 61/61, nativ 82/82, `--stage12b-techdraw-only` 2x je 921 Aufrufe, `--stage12-only` 2x 30/30
  (A1-A5 inklusive); Regression nach `measure`-Aenderung: `--stage12b-part-only`, `-partdesign-a-only`, `-partdesign-b-only` je 2x PASS.
- **Doku:** ACCEPTANCE (Zuordnung), COVERAGE, CONTRACTS, README, AGENTS, memory.

## 2026-11-17 - Stufe 12b-4d Altpfade: save/close/screenshot/set_view/fit_view/cancel_job/scrub_edges (Tag `stage-12b4d-2026-11-17`)

194 Tools, Bridge 0.11.0, Paket 0.1.0 (unveraendert). Referenzlaufzeit FreeCAD 1.1.4. Benutzerentscheidung: Absichern wie `*_safe`.

- **Geaendert (Migration, Ablehnung bisher akzeptierter Eingaben):** `save_document` nur absoluter `.FCStd`-Pfad in vorhandenem
  Ordner, neues `overwrite=false` (fremde Dateien werden nicht mehr still ersetzt); `close_document` mit
  `discard_changes=false` (ungespeicherte Aenderungen/Fremdverknuepfungen werden abgelehnt); `screenshot` 1..4096 px je Seite
  und nur kleingeschriebene `view`-Presets; `set_view` als Enum.
- **Neu (additiv):** `set_view(doc_name)` und `fit_view(doc_name)`; Ergebnisse nennen `document`.
- **Behoben:** `screenshot` mit 20000x20000 px beendete FreeCAD; `save_document` legte `x.txt.FCStd`, relative Dateien im
  FreeCAD-Arbeitsverzeichnis und Dateien in fehlenden Ordnern an; `set_view` kehrte vor Ende der Navigationsanimation
  zurueck (Kamera noch im Zwischenzustand); `set_view`/`fit_view` ohne aktives Dokument/3D-Ansicht gaben `AttributeError`.
- **Tests:** neues Gate `--stage12b-legacy-only` (2x je ca. 276 Aufrufe; Speichern/Schliessen mit Dateiorakeln, Kamera-
  und Bildseitenverhaeltnis-Orakel je Ansicht, PNG-Groessen bis 4096x4096, cancel_job-Zustaende, Scrub-Varianten, Reopen);
  ein neuer nativer und ein neuer Hosttest. Host 60/60, nativ 81/81, `--stage12-only` 2x 30/30.
- **Doku:** CONTRACTS "12b-4d", ACCEPTANCE, README-Checkliste, AGENTS, memory.

## 2026-11-17 - Stufe 12b-4c Mesh/Austausch: Grenzen, Triangulation, SVG-Einheiten, degenerierte Kanten (Tag `stage-12b4c-2026-11-17`)

194 Tools, Bridge 0.11.0, Paket 0.1.0 (unveraendert). Referenzlaufzeit FreeCAD 1.1.4.

- **Geaendert (Migration, Ablehnung bisher akzeptierter Eingaben):** Mesh-Koordinaten <= 1e6 mm; `linear_deflection`
  1e-3..1e6 mm und >= 1e-4 der Bounding-Box-Diagonale, `angular_deflection` 0,05..pi (auch STL/OBJ-Export);
  `mesh_to_shape.tolerance` 1e-6..100 mm; `area_tolerance` <= 1e12; SVG-Import nur mit mm/cm/in-Breite und `viewBox`
  (Inkscape-Dateien `unsupported_feature`). Schema: `MeshCoordinate/MeshLinear/MeshAngle/MeshSewing/MeshAreaTolerance`.
- **Behoben:** Koordinaten ab 1e8 mm loesten eine Access Violation im Mesh-Kern aus; `linear_deflection` 1e-6 blockierte die
  GUI; SVG ohne absolute Einheit oeffnete einen modalen Dialog (GUI blockiert); `mesh_from_shape` meldete bei sehr groben
  Toleranzen Erfolg mit defektem Netz (jetzt `triangulation_failed`); STEP-Import von Kugeln scheiterte an degenerierten
  Kanten (`undefined curve type`, jetzt Kurventyp `degenerated`).
- **Tests:** neues Gate `--stage12b-mesh-only` (2x je 772 Aufrufe, 35 Netze; Defekt-/Reparatur-/Triangulationsorakel,
  STEP AP214/AP242, STL/OBJ-Facettenorakel, DXF/SVG, Reopen + zweiter Edit); ein neuer nativer und ein neuer Hosttest.
  Host 59/59, nativ 80/80, `--stage12-only` 2x 30/30.
- **Doku:** CONTRACTS "12b-4c", COVERAGE N21, ACCEPTANCE, README-Checkliste, AGENTS, memory.

## 2026-11-17 - Stufe 12b-4b Draft: Platzierung, Grenzen, Bogen, Arrays (Tag `stage-12b4b-2026-11-17`, Commit `3882ca8`)

194 Tools, Bridge 0.11.0, Paket 0.1.0 (unveraendert). Referenzlaufzeit FreeCAD 1.1.4.

- **Geaendert (Migration, Ablehnung bisher akzeptierter Eingaben):** Draft-Groessen 1e-6..1e8 mm, Textgroesse bis
  1e6 mm, Koordinaten/Spacing/Center/Label-Ziel je Komponente <= 1e9 mm; Bogen-Sweep >= 0,001 Grad. Schema:
  `DraftPoint`/`DraftLength`/`DraftTextSize` (Mesh unveraendert).
- **Behoben:** `draft_create_element` `wire` ignorierte `position`/`quaternion` (Ursache: `Draft.make_wire` wendet die
  inverse Platzierung auf globale Punkte an); Bogen mit Sweep nahe 0 wurde Nulllaenge/Vollkreis; Radius 1e300
  scheiterte erst bei der JSON-Ausgabe, Position 1e300 meldete Erfolg; Bogen-Endwinkel 360 wurde als 0 gelesen.
- **Tests:** neues Gate `--stage12b-draft-only` (2x je 1767 Aufrufe, 50 Elemente, 17 Polar-/13 Ortho-Orakelfaelle,
  Undo/Redo, Reopen + zweiter Edit); ein neuer nativer und ein neuer Hosttest. Host 58/58, nativ 79/79,
  `--stage12-only` 30/30.
- **Doku:** CONTRACTS "12b-4b", COVERAGE N20, ACCEPTANCE, README-Checkliste, AGENTS, memory.

## 2026-11-17 - Stufe 12b-4a Assembly-Gelenkvarianten (Tag `stage-12b4a-2026-11-17`)

194 Tools, Bridge 0.11.0, Paket 0.1.0 (unveraendert). Referenzlaufzeit FreeCAD 1.1.4. 12b-4 in 4a-4d geteilt.

- **Neu (additiv):** `assembly_set_joint.clear_limits` entfernt einzelne Limits (`length_min`, `length_max`,
  `angle_min`, `angle_max`); bisher war ein gesetztes Limit nicht mehr entfernbar.
- **Geaendert (Migration, Ablehnung bisher akzeptierter Eingaben):** `subelement1/2`, `vertex1/2` nur leer oder
  `FaceN`/`EdgeN`/`VertexN` (N>=1); Positionen/Offsets mit Betrag > 1e6 mm abgelehnt.
- **Behoben:** Muellname (`Foo`) wurde als Connector akzeptiert; Offset 1e300 meldete Erfolg ohne Wirkung.
- **Dokumentiert (nativ, unveraendert):** Solver erzwingt Limits nicht; Orientierungszweig bleibt erhalten
  (gespiegelte gueltige Loesung nach grossen Offset-Rotationen moeglich).
- **Tests:** neues Gate `--stage12b-assembly-only` (2x je 1598 Aufrufe, 21 Assemblies, Orakel fuer Offsets,
  Undo/Redo, Reopen); ein neuer nativer und ein neuer Hosttest. Host 57/57, nativ 78/78, `--stage12-only` 30/30.
- **Doku:** CONTRACTS "12b-4a", COVERAGE N18, ACCEPTANCE, README-Checkliste, AGENTS, memory.

## 2026-11-13 - Stufe 12b-3 Part: Primitive, Booleans, Dress-ups, Transformationen, N14/N15 (Tag `stage-12b3-2026-11-13`)

194 Tools, Bridge 0.11.0, Paket 0.1.0 (unveraendert). Referenzlaufzeit FreeCAD 1.1.4. Lokal committet und getaggt, Push durch den Benutzer.

- **Geaendert (Migration, Ablehnung bisher akzeptierter Eingaben; Benutzerentscheidung 2026-11-13):**
  Primitive nur mit Masse > 0 (Zylinder `0 < angle <= 360`, Torus `radius2 <= radius1`, Kegel nicht beide
  Radien 0); Booleans mit >= 2 verschiedenen Operanden, leere Ergebnisse (cut verbraucht Basis, common ohne
  Volumen) mit Rollback abgelehnt; `part_fillet`/`part_chamfer` nur revisionsgepruefte Kanten ohne Duplikate
  (Batch-Schritte unveraendert), Radius/Fase > 0; `rotate_object` Nullachse, `mirror_object` unbekannte
  Ebene und `scale_object` Faktor <= 0 oder > 1e6 abgelehnt; `part_shell` nur eine zusammenhaengende Shell,
  `part_loft` `closed` ab 3 Sektionen, Nullvolumen-/Nullflaechen-Ergebnisse abgelehnt; `part_sweep`
  `transformed` nur fuer tangentenstetige Pfade; `part_offset_shape` `join=tangent` mit `unsupported_feature`
  (nativ nie ausfuehrbar, Schema bleibt).
- **Geaendert (Migration, Ergebnis aendert sich):** `part_sweep` `round`/`right_corner` waren vertauscht;
  jetzt `right_corner` = Gehrung (20 pi), `round` = Rundecke (20 pi - (4-pi)/3).
- **Behoben:** Primitive mit Height/Angle <= 0 meldeten Erfolg mit Standardform (fehlgeschlagener Recompute
  "Invalid" behaelt alte Shape; `_shape_result` prueft jetzt den Status), Angle 361 wurde still gekappt;
  `part_split` scheiterte bei schraeger Ebene (Schneidblatt nicht um `plane_origin` zentriert);
  `part_repair` meldete `changed=true` fuer unveraenderte Shapes; native Fehler ohne Ursache
  ("BRep_API: command not done") nennen jetzt die Ursache.
- **Neu (additiv):** Ergebnisfelder `position`/`quaternion` (set_placement, rotate_object), `part_volumes`
  (part_split), `native_fix_reported` (part_repair); Schema-Grenzen mit Einheit; Capabilities `part_modeling`.
- **Tests:** neues MCP-Gate `tests/mcp_smoke.py --stage12b-part-only` (je Lauf 5290 Aufrufe, 152 Negativfaelle,
  352 Objekte, analytische Orakel, Undo/Redo je Mutation, FCStd-Reopen + zweite Aenderung); sechs neue native
  Tests `test_stage12b_part_*`, ein neuer Hosttest. Ergebnis auf frischen GUIs: Host 56/56, nativ 77/77,
  `--stage12-only` 30/30, `--stage12b-sketcher-only` 2x, `--stage12b-partdesign-a-only` 2x,
  `--stage12b-partdesign-b-only` 2x, `--stage12b-part-only` 2x. Offen/nur nativ: Frenet gegen Standard auf
  verdrilltem 3D-Pfad und ungueltige BRep fuer `part_validate`.
- **Doku:** CONTRACTS "12b-3", COVERAGE I27-I31/N14-N15, ACCEPTANCE, README-Checkliste, AGENTS-Kurzstatus, memory.

## 2026-11-12 - Stufe 12b-2b PartDesign Hole/Dress-ups/Muster/MultiTransform/edit_feature (Tag `stage-12b2b-2026-11-12`)

194 Tools, Bridge 0.11.0, Paket 0.1.0 (unveraendert). Referenzlaufzeit FreeCAD 1.1.4. Lokal committet und getaggt, Push durch den Benutzer.

- **Geaendert (Migration, Ergebnis aendert sich):** `partdesign_thickness` `direction` war
  invertiert; jetzt `inside` = Wand nach innen (Aussenmass unveraendert), `outside` = nach aussen.
- **Geaendert (Migration, Ablehnung bisher akzeptierter Eingaben):** Fillet/Chamfer/Thickness/Draft
  nur revisionsgepruefte Auswahlen (keine nackten `EdgeN`/`FaceN`), keine Duplikate, Basis muss der
  Body-Tip sein, Features ohne Volumenwirkung werden abgelehnt; Draft `0 < |angle| < 90`, Pull-
  Richtung nur Kante, Neutralebene planare Flaeche/Datumebene; Hole braucht ein Solid, `thread_type`
  nur ISO/UTS, `thread_pitch` nur ISO; Pattern `occurrences` 2..100 und MultiTransform <= 100
  Instanzen; MultiTransform-Schritte mit Pflichtfeldern je Typ, fremde Felder abgelehnt;
  `edit_feature` lehnt modusfremde Parameter ab und rollt bei ungueltigem Folgefeature/Tip zurueck.
- **Behoben:** Gewindeloch ueberschrieb `diameter` mit dem Kernloch der Gewindegroesse; Draft mit
  `pull_selection` scheiterte stets (Aufloesung nach der Mutation); `occurrences=1000` stuerzte die
  GUI ab, 200 ueberlappende Kopien blockierten sie; `edit_feature` meldete Erfolg bei ungueltigem
  Folgefeature, Profilwechsel von Revolution/Groove behielt die Achse der alten Skizze;
  `second_length` griff bei LinearPattern; Schema-Dekorator ergaenzte Einheit/Beschreibung nicht
  fuer Parameter mit Grenzen.
- **Neu (additiv):** `partdesign_draft` `plane_selection`; `edit_feature` Parameter `value`
  (Thickness); Ergebnisfelder `diameter`/`depth`/`depth_type`/`cut_type`/`thread` (Hole) und
  `originals`/`occurrences` (Muster); Schema-Grenzen (`gt=0`, `ge=2`, `le=100`) mit Einheit;
  Ursachen in Fehlermeldungen ("radius ... may be too large"); Capabilities-Felder.
- **Tests:** neues MCP-Gate `tests/mcp_smoke.py --stage12b-partdesign-b-only` (je Lauf 7018 Aufrufe,
  216 Negativfaelle, 41 Bodies, analytische Orakel, Undo/Redo je Mutation, FCStd-Reopen +
  zweite Aenderung); vier neue native Tests `test_stage12b_partdesign_*`, drei Alttests angepasst.
  Ergebnis: Host 55/55, nativ 71/71, `--stage12-only` 30/30, `--stage12b-sketcher-only` 2x,
  `--stage12b-partdesign-a-only` 2x, `--stage12b-partdesign-b-only` 2x (je 7018 Aufrufe).
- **Doku:** CONTRACTS "12b-2b", COVERAGE I23-I26/N11-N13, ACCEPTANCE, README-Checkliste,
  AGENTS-Kurzstatus, memory.
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
