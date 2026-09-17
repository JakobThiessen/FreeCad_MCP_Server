# Abdeckungsmatrix: strukturierter FreeCAD MCP Server

Stand: 2026-09-17. **Umfang vom Benutzer bestaetigt; Stufen 1-5 abgenommen, keine Gesamtabnahme.**
Grundlage: [Plan](../agent.md), [Audit vom 2026-09-15](AUDIT.md),
[Projektgedaechtnis](../memory.md).

## Leseregeln und Zielplattform

- Ziel aller Kernzeilen: FreeCAD 1.1 unter Windows, lokale GUI-Bridge und
  echter MCP-stdio-Transport. Andere Versionen/Betriebssysteme sind nicht zugesagt.
- `vorhanden`: dedizierter strukturierter Pfad fuer die genannten Ist-Varianten.
- `teilweise`: strukturierter Teil vorhanden, vereinbarte Varianten fehlen.
- `fehlt`: kein dedizierter strukturierter Pfad im untersuchten Workspace.
- `getestet`: separater Nachweis mit Datum, Umgebung und begrenztem Testumfang;
  kein Synonym fuer vollstaendige Abnahme. Historische Tests sind als H markiert.
- `ausgeschlossen`: kein Bestandteil der Kernabnahme; CAM/BIM nur nach Freigabe.
- R = lesen, W = Dokument/Ansicht aendern, F = Datei-I/O, C = Verbindung/Steuerung.
  Mehrere Kennzeichen sind moeglich. Alle Parameterangaben bezeichnen den
  aktuellen Bestand, sofern sie nicht ausdruecklich als Ziel bezeichnet sind.
- Jede Funktionszeile erhaelt Zielstufe und messbaren Pruefauftrag. Die zugehoerigen
  Referenzaufgaben und gemeinsamen Regeln werden in Stufe 1 separat festgelegt.

## Evidenz und Grenzen

Geprueft werden die Registrierung in
[server.py](../src/freecad_mcp/server.py), die oeffentlichen Funktionen der
[Dokumentoperationen](../freecad_addon/freecad_ai_bridge/operations.py),
[Sketcher-Operationen](../freecad_addon/freecad_ai_bridge/sketcher_ops.py),
[PartDesign-Operationen](../freecad_addon/freecad_ai_bridge/partdesign_ops.py),
[Part-Operationen](../freecad_addon/freecad_ai_bridge/part_ops.py),
[Ansicht/Austausch](../freecad_addon/freecad_ai_bridge/view_ops.py) sowie der
[RPC-Dienst](../freecad_addon/freecad_ai_bridge/rpc_server.py).

Die vorhandenen [Vertragstests](../tests/test_tool_contracts.py) vergleichen
Weiterleitungsziele und Argumentnamen per AST, die oeffentlichen `*_ops.py`-
Funktionen mit MCP-Zielen, die Registrierung von fuenf ergaenzten Tools und
MCP-Bildinhalte. Das ist kein geometrischer Variantenbeweis und prueft nicht
automatisch alle Runtime-Rueckgaben oder das gesamte generierte JSON-Schema.

Der [historische Audit](AUDIT.md) meldet 82 registrierte Tools, 11 lokale Tests,
23 FreeCAD-Integrationstests und einen MCP-Smoke-Test. Diese Zahlen gelten
nicht als neuer Live-Lauf. Das bestehende Schraubstockmodell entstand durch
Python und ist kein Nachweis fuer einen strukturierten Referenzworkflow.

Der RPC-Dienst bietet weiterhin `execute`; `execute_python` ist deshalb keine
Loesung fuer fehlende Matrixfunktionen. Abschaltung samt indirekten RPC-Pfaden
ist Ziel von Stufe 12, nicht Gegenstand einer Implementierung in Stufe 1.

## Aktueller Nachweis

Stufe 5 technisch abgenommen am 2026-09-17: 19 additive Tools, **136 Tools**,
Bridge **0.6.0**. N08/N09 und die Sketcher-Anteile I05-I17 sind im
dokumentierten Umfang umgesetzt. **K5:** 33 lokale Tests. **I5:** 36 native
GUI-Tests, darunter drei Stufe-5-Tests. **M5:** zweimal 52 strukturierte
MCP-Aufrufe mit zwei unabhaengigen FCStd-Roundtrips. Gehaeuse- und Flanschprofil
erreichen DoF 0 ohne Block-Constraint, bleiben nach Massaenderung editierbar;
Konflikte rollen auf den exakten Vorzustand zurueck. Externe Kante, planare
Flaechenbefestigung, Trim, Extend, Fillet, Copy und Mirror sind nativ geprueft.
Vertrags-, Stufe-4-, Stufe-3- und Bestands-MCP-Regressionslaeufe bestanden.
Frische GUI-Bridge auf Port 9886; genaue Daten in [memory.md](../memory.md).
Keine Vorwegnahme Stufe 6; Installation unveraendert.

Stufe 4a/4b technisch abgenommen am 2026-09-16: neun additive Tools, **116 Tools**,
Bridge **0.5.0**. Auswahl-/Revisions- und Mess-/Ansichtsvertrag in
[CONTRACTS.md](CONTRACTS.md). **K4:** 32 lokale Tests bestanden.
**I4:** 33 native Tests auf frisch gestarteter FreeCAD-Instanz, darunter fuenf
Stufe-4-Tests fuer Filter/Revision/Topologie-/Namenswechsel, Container/Links,
alle sechs Auswahlverbraucher, analytische Messungen und Ansichtsisolation.
**M4:** zweimal 113 strukturierte MCP-Aufrufe, zwei Dokumente, Datei-Roundtrip,
Markierung/Darstellungs-Roundtrip, sieben Ansichten. 14 PNGs mit 800x600 Pixeln
pixelgeprueft, finale Isometrie/Draufsicht visuell bestaetigt. Native Preset-
Blickrichtungen geprueft; GUI-Auswahl ist kein garantiertes farbiges PNG-Overlay.
Stufe-2-Vertragslauf, zweimal 121 Stufe-3-Regressionsaufrufe und Bestands-Smoke
ebenfalls bestanden. Frischer Port 9883, genaue Artefakte in [memory.md](../memory.md).
Keine Gesamtabnahme A1-A5 oder Vorwegnahme Stufe 5; Installation unveraendert.

Stufe 3 am 2026-09-16 technisch abgeschlossen: **107 Tools**, Bridge **0.4.0**,
22 neue Werkzeuge in [document_ops.py](../freecad_addon/freecad_ai_bridge/document_ops.py).
**K3:** 30 lokale Tests; **I3:** 28 native Integrationstests, darunter vier
Stufe-3-Tests mit 29 Property-Typen, Expressions, Container-/Kopier-/Loeschvarianten
und Transformationen. **M3:** zweimal 120 protokollierte strukturierte MCP-Aufrufe,
Gehauseparameter mit Volumen 32088/38328/49536 mm^3, Undo/Redo/Rollback,
Kopie/Links, Dateisperrfehler, FCStd reopen und STEP/STL-Ausgabe. Stufe-2-MCP-
Vertragsregression und Bestands-Smoke ebenfalls bestanden. Frische FreeCAD-
Instanz auf Port 9879; exakte Berichte in [memory.md](../memory.md).
Parameterteil A1 mit Part-Box/Cut, Body/Tip separat geprueft; keine vorgezogene
Abnahme vollstaendig bestimmter A1-Skizzen/PartDesign-Features (Stufen 5/6/8).
Native Aliasabweichung vom Benutzer bestaetigt; sichere Save/Close als additive
Werkzeuge, Alt-Loeschschutz als dokumentierte Migration in CONTRACTS.

Historischer Abschluss Stufe 2:

Stufe 2 am 2026-09-16 abgeschlossen (K2F/M2F/I2F): **85 Tools**, drei neue
Werkzeuge `get_capabilities`, `resolve_reference`, `execute_batch`.
Feldmetadaten fuer alle Eingabeparameter, explizite Fehler-/Migrationsregeln,
eigene Transaktionen, nichtmutierende Vorschau und Batch mit elf erlaubten
Operationen. Vollstaendige Grenzen: [CONTRACTS.md](CONTRACTS.md).
**28/28 lokale Tests** (0.654 s), **24/24 FreeCAD-Integrationstests** (4.788 s),
erweiterter MCP-Vertragslauf mit allen elf Batchoperationen und Bestands-Smoke
bestanden. FreeCAD 1.1.1 Build 20260414, Bridge-API 0.3.0, MCP 1.27.1,
Python 3.10.11; frische Workspace-Bridge Port 9877. N01/N02 im dokumentierten
Infrastrukturumfang abgenommen; keine Vorwegnahme spaeterer Fachvarianten.
Benutzerinstallation nicht aktualisiert. Fehlerfunde, Korrekturen und exakte
Laufbefehle im [Protokoll](../memory.md).

Historischer Zwischenstand 2a vor der abschliessenden Implementierung:

Stufe-2a-Teilfortschritt am 2026-09-16 (K2/M2): **84 Tools**, zwei neue lesende
Werkzeuge `get_capabilities` und `resolve_reference`, 81 direkte Weiterleitungen.
Versionierter additiver Vertrag und Migrationsgrenzen: [CONTRACTS.md](CONTRACTS.md).
17 lokale Tests bestanden (0.886 s); echter MCP-stdio-Vertragstest mit zwei
Dokumenten, gleichen Objektnamen, Schema-/Referenzfehlern und Cleanup bestanden.
FreeCAD **1.1.1**, Build 20260414, Bridge-API 0.2.0, MCP 1.27.1, Python 3.10.11,
Workspace-Testbridge Port 9876. Bestehender MCP-Smoke ebenfalls bestanden.
Keine Vollabnahme von N01/N02: Alt-Schematransformation und 2b bleiben offen.
Installation nicht aktualisiert; Details und Startfehler im [Protokoll](../memory.md).

Historischer Stufe-1-Nachweis vom selben Datum, vor Implementierung von 2a:

- `python -m unittest discover -s tests -p "test_tool_contracts.py" -v`:
  **4/4 bestanden**, 0.405 s; im Aufruf wurde der venv-Interpreter explizit benutzt.
- `asyncio.run(server.mcp.list_tools())`, Signaturen und AST-Ziele abgeglichen:
  **82 eindeutige registrierte Tools**, **79 direkte `_call`-Weiterleitungen**.
- Oeffentliche CAD-Funktionen: `operations` 8, `sketcher_ops` 26,
  `partdesign_ops` 17, `part_ops` 15, `view_ops` 14, zusammen **80**.
  79 direkte Ziele plus `operations.get_document_state` ueber den Status-RPC.
- `connect`, `get_status`, `execute_python` verwenden den Connection-Client
  statt `_call`. Eine im Editor angebotene Tool-Liste ist nicht massgeblich
  fuer den aktuellen Workspace-Server.
- Keine Verbindung zu FreeCAD, kein neuer CAD-/MCP-Transport-Live-Lauf,
  keine Aenderung an Installation oder Benutzerdokumenten.

Nachweiskuerzel fuer die folgenden Tabellen:

| Kuerzel | Vorhandener Nachweis und seine Grenze |
| --- | --- |
| K | Lokaler Stufe-1-Vertragstest wie oben; keine Geometrieabnahme. |
| K2 | 17 lokale Tests vom 2026-09-16; Schema-/Fehler-/Referenz-/GUI-Regressionen fuer den implementierten 2a-Teil. |
| M2 | Echter MCP-stdio-Test `--contracts-only` plus Bestands-Smoke am 2026-09-16; zwei Dokumente/Fehler/Geometriezustand/Cleanup, kein Batch-/Vorschau-/vollstaendiger Transaktionsnachweis. |
| K2F | Finaler Stufe-2-Lauf: 28 lokale Tests, einschliesslich aller Parametermetadaten, Batchgrenzen/Referenzen/Typen, Transaktionsbesitz und Rollback. |
| M2F | Finaler MCP-stdio-Vertragslauf: alle elf Batchoperationen, Vorschau, atomarer Erfolg/Undo/Redo/Rollback, Vorvalidierung, Mehrdokument-Teilstatus, Loeschschutz/-Rollback und Cleanup; Bestands-Smoke ebenfalls bestanden. |
| I2F | 24 FreeCAD-Integrationstests auf 1.1.1, einschliesslich fremder ausstehender Transaktionen in zwei Dokumenten; alle bestanden. |
| K4 | 32 lokale Tests am 2026-09-16; neue Auswahl-/Messschemas, Weiterleitungen, native MCP-Bildinhalte und Bestandsregression. |
| I4 | 33 native Integrationstests auf FreeCAD 1.1.1, darunter fuenf Stufe-4-Tests; exakte Grenzen im aktuellen Nachweis. |
| M4 | Zweimal 113 strukturierte MCP-Aufrufe auf frischer Bridge 0.5.0/9883, 14 pixelgepruefte Bilder; weitere Stufe-2/3-/Bestandsregression bestanden. |
| K5 | 33 lokale Tests am 2026-09-17; Stufe-5-Schemas/Weiterleitungen, dynamische Wert-Einheit und Bestandsregression. |
| I5 | 36 native GUI-Integrationstests auf FreeCAD 1.1.1, darunter drei Stufe-5-Tests; alle bestanden. |
| M5 | Zweimal 52 strukturierte Stufe-5-MCP-Aufrufe auf Bridge 0.6.0/9885 mit FCStd save/reopen; Vertrags-/Stufe-3/4-/Bestandsregression auf 9886 bestanden. |
| H-I | [Integrationstests](../tests/freecad_integration.py), 23 Tests historisch am 2026-09-15 bestanden; konkrete `test_`-Suffixe stehen in den Zeilen. |
| H-M | [MCP-Smoke](../tests/mcp_smoke.py), historisch bestanden: Box/Part-Fillet, Messen, Undo/Redo, STEP/STL/OBJ, PNG und Python-Namensraum. |
| H-U | [Executor](../tests/test_gui_executor.py) und [Verbindung/Sicherheit](../tests/test_connection_security.py), historisch bestanden; nicht erneut ausgefuehrt. |
| H-D | [Demo-Pruefung](../tests/verify_model.py), historisches Python-Modell; kein strukturierter End-to-End-Nachweis. |
| - | Kein dedizierter Test fuer diese Zielfunktion gefunden. |

## Inventar der vorhandenen Werkzeuge

Alle Zeilen beziehen sich auf FreeCAD **1.1/Windows**. `K` gilt fuer die
Weiterleitungsargumente aller direkten Ziele; die drei Sonderpfade sind
gesondert bezeichnet. Funktionen mit gemeinsamem Status werden gruppiert,
aber jedes registrierte Tool ist ausgeschrieben. Bei mehreren Namen sind
Tool und Addon-Ziel jeweils in derselben Reihenfolge zugeordnet.

Zielmodule: O = `freecad_ai_bridge.operations`, S = `freecad_ai_bridge.sketcher_ops`,
D = `freecad_ai_bridge.partdesign_ops`, P = `freecad_ai_bridge.part_ops`,
V = `freecad_ai_bridge.view_ops`. Ein Zielname ohne neuen Modulbuchstaben
uebernimmt den Modulbuchstaben derselben Zelle.

Gemeinsame Parameter: `doc_name=None` meint meist das aktive Dokument;
`obj_name`/`base_name`/`sketch_name` sind interne Namen, keine stabilen
Topologiereferenzen. Erzeuger haben meist `name`; Default und Pflichtfelder
sind in der verlinkten Serversignatur nachpruefbar. `None` wird vor `_call`
entfernt. Laengen sind derzeit implizit mm, Winkel meist Grad, Ausnahme
Sketch-Bogen und Ellipsendrehung: Radiant. Parameterlisten unten nennen die
fachlichen Varianten; gemeinsame Namen/Dokumentparameter gelten zusaetzlich.

Die Spalte Pruefkriterium ist ein **zukuenftiger** Auftrag nach den gemeinsamen
Regeln G und Variantentests V aus [ACCEPTANCE.md](ACCEPTANCE.md), kein Testresultat.
Zielstufe bezeichnet die Vervollstaendigung/Abnahme dieser Funktion, nicht den
Zeitpunkt ihrer erstmaligen Implementierung. Jede Variante benoetigt V.

| ID | Registrierte Tools -> Addon-Ziele | Art; Ist-Parameter/Varianten | Status; Nachweis | Zielstufe | Pruefkriterium / fehlender Anteil |
| --- | --- | --- | --- | --- | --- |
| I01 | `connect` -> Client `connect`/RPC `ping`, `get_version`; `get_status` -> RPC/O.`get_document_state` | C/R; host=127.0.0.1, port=9875; alle offenen Dokumente | teilweise; H-U, H-M (Sonderpfade) | 2 | Zwei Dokumente unterscheiden; Versions-/Faehigkeitsmerkmale und begrenzte Statusantwort fehlen (N01/N16). |
| I02 | `create_document`, `open_document`, `save_document`, `close_document` -> O.`create_document`, `open_document`, `save_document`, `close_document` | W/F; name, path; Save/Save As; close verlangt name | Altpfad erhalten; K3/I3/M3 fuer ergaenzten Workflow | 3 | G-Dateizyklus abgenommen; Aktivieren, Dirty-State und Schutz ueber I02a/N03. Alt-Save/Close nicht als sicher ausgeben. |
| I02a | `inspect_document`, `activate_document`, `recompute_document`, `save_document_safe`, `close_document_safe` -> document_ops | R/W/F; explizite Dokumentnamen, overwrite/discard opt-in | vorhanden/getestet K3/I3/M3 | 3 | N03 erfuellt; Alt-Save/Close bleiben kompatibel, sichere Migration ueber neue Tools. |
| I03 | `list_objects`, `inspect_object` -> O.`list_objects`, `inspect_object` | R; Dokument, Objekt; Basisdaten, Boundingbox, teils in Strings serialisierte Properties | teilweise; K, H-M (list) | 3 | N04: Typ/Einheit/Schreibbarkeit erhalten; unbekanntes Objekt und zwei gleich benannte Objekte in verschiedenen Dokumenten. |
| I03a | `get_properties`, `set_properties` -> document_ops | R/W; typisierte Auswahl/Map, Status/Einheiten/Enums | vorhanden/getestet K3/I3/M3 | 3 | N04 erfuellt fuer 29 explizit freigegebene native Typen; Alt-inspect behaelt seine Stringausgabe. |
| I04 | `delete_object` -> O.`delete_object` | W; obj_name; jetzt nur unreferenzierte Blaetter | vorhanden/getestet K3/I3/M3 plus Stufe-2-Regression | 3 | Referenzierte Ziele ablehnen; Vorschau und bestaetigte Mengenloeschung mit Rollback ueber N06. |
| I05 | `create_sketch` -> S.`create_sketch` | W; XY/XZ/YZ, offset=0, optional body_name; kann ohne Dokument eines anlegen | teilweise; K, H-I `sketch_plane_offsets` | 5 | Alle Ebenen/Offsets; Body ist Container, kein Flaechen-Attachment; N09 ergaenzen. |
| I06 | `sketch_add_line`, `sketch_add_rectangle` -> S.`add_line`, `add_rectangle` | W; x1/y1/x2/y2; construction=False; Rechteck mit Coincident/H/V | vorhanden; K, H-I `sketch_degrees_of_freedom_and_lock`, `symmetric_pad` (Rechteck indirekt) | 5 | Endpunkte und Rechteckflaeche exakt; N08 liefert Bearbeiten/Loeschen, degeneriertes Rechteck ablehnen. |
| I07 | `sketch_add_circle`, `sketch_add_arc` -> S.`add_circle`, `add_arc` | W; cx/cy/radius; Bogen start_angle/end_angle in rad; construction | vorhanden; K, H-I `additive_loft` (Kreis indirekt); Bogen ohne eigenen Live-Test | 5 | Radius, Bogenendpunkte und Sweep-Winkel; Radius <= 0 ablehnen. |
| I08 | `sketch_add_ellipse`, `sketch_add_bspline` -> S.`add_ellipse`, `add_bspline` | W; cx/cy/major_radius/minor_radius/angle(rad); points=[[x,y],...], construction | teilweise; K | 5 | Ellipsenachsen; B-Spline interpoliert Punkte mittels `interpolate`, keine freie Pol-/Knotensteuerung trotz Docstring. Zusaetzlich N08, keine NURBS-Vollabdeckung. |
| I09 | `sketch_add_point`, `sketch_add_polygon`, `sketch_add_slot` -> S.`add_point`, `add_polygon`, `add_slot` | W; x/y; points und close=True; Slot x1/y1/x2/y2/radius; construction | vorhanden; K, H-I `slot_is_closed_and_constrained` | 5 | Punktlage, offener/geschlossener Polygonzug; Slotflaeche = 2*r*Mittelpunktsabstand + pi*r^2; zu wenige Punkte/Slotlaenge 0 ablehnen. |
| I10 | `sketch_info` -> S.`get_sketch_info` | R (ruft Solver); sketch_name; Geometrie/Constraints, DoF, FullyConstrained, Solverstatus | teilweise; K, H-I `sketch_degrees_of_freedom_and_lock` (Statushelper) | 5 | Nullwerte, vollstaendige Referenzen und Konflikt-/Redundanz-IDs fehlen (N08); DoF vor/nach Aenderung pruefen. |
| I11 | `sketch_constrain_coincident`, `sketch_constrain_tangent` -> S.`add_constraint_coincident`, `add_constraint_tangent` | W; zwei geo_idx; Coincident mit zwei point_idx; Tangent ohne oder mit beiden point_idx | vorhanden; K; kein eigener Live-Test beider Wrapper | 5 | Zusammenfallende Punkte; Tangentenwinkel 0; nur ein point_idx muss im Zielvertrag Fehler sein. |
| I12 | `sketch_constrain_perpendicular`, `sketch_constrain_parallel`, `sketch_constrain_equal` -> S.`add_constraint_perpendicular`, `add_constraint_parallel`, `add_constraint_equal` | W; geo_idx1/geo_idx2; Linien bzw. gleiche Laenge/Radius | vorhanden; K | 5 | 90/0 Grad bzw. gleiche Laengen/Radien; inkompatible Typen ablehnen. |
| I13 | `sketch_constrain_symmetric` -> S.`add_constraint_symmetric` | W; zwei Geometrie-/Punktpaare, sym_geo, sym_point optional: Linie/Punkt | vorhanden; K; kein dedizierter Live-Test in der aktuellen Testsuite | 5 | Beide Symmetrievarianten mit bekannten Spiegelkoordinaten; Audit-Zusammenfassung allein ersetzt keinen Test. |
| I14 | `sketch_constrain_horizontal`, `sketch_constrain_vertical` -> S.`add_constraint_horizontal`, `add_constraint_vertical` | W; geo_idx einer Linie | vorhanden; K | 5 | delta-y bzw. delta-x = 0; falscher Geometrietyp. |
| I15 | `sketch_constrain_lock`, `sketch_constrain_block` -> S.`add_constraint_lock`, `add_constraint_block` | W; geo_idx/point_idx fixiert aktuelle Punktlage; Block geo_idx | vorhanden; K, H-I `sketch_degrees_of_freedom_and_lock`, `lock_point_at_origin`; Block ohne eigenen Live-Test | 5 | Lock an Ursprung/Achse/freiem Punkt, Block beseitigt Element-DoF; Bearbeitung durch Entsperren (N08). |
| I16 | `sketch_constrain_distance`, `sketch_constrain_distance_x`, `sketch_constrain_distance_y` -> S.`add_constraint_distance`, `add_constraint_distance_x`, `add_constraint_distance_y` | W; Punkt-Punkt/value; einzelner Punkt/value relativ Ursprung X/Y | teilweise; K | 5 | Gemessene Sollabstaende; fehlende Linienlaenge, Punkt-Punkt-X/Y und Referenzmasse in N08. |
| I17 | `sketch_constrain_angle`, `sketch_constrain_radius` -> S.`add_constraint_angle`, `add_constraint_radius` | W; geo_idx1/geo_idx2/angle(Grad); geo_idx/radius | teilweise; K | 5 | Winkel/Radius nach Aenderung; Durchmesser und Linienwinkel zur Achse in N08. |
| I18 | `partdesign_body` -> D.`create_body`; alternativ `create_container(kind=body)` -> document_ops | W; name | vorhanden/getestet K3/I3/M3 | 3 | Body per MCP, Mitgliedschaft/Tip-Verwaltung mit Fehlerfaellen und Origin-/Loesch-Undo ueber N03 geprueft. |
| I19 | `partdesign_pad`, `partdesign_pocket` -> D.`pad`, `pocket` | W; sketch_name/length/reversed; Pad symmetric; Pocket through_all | teilweise; K, H-I `symmetric_pad`, `linear_pattern` (Pocket indirekt) | 6 | Analytische Extrusionsvolumen; fehlende Endbedingungen/beidseitige Optionen N10. |
| I20 | `partdesign_revolution`, `partdesign_groove` -> D.`revolution`, `groove` | W; sketch_name, angle=360, axis H/V/N, reversed | teilweise; K | 6 | Voll-/Teilrotation und Gegenrichtung; beliebige Bezugsachse/beidseitige Winkel N11; ungueltige Achse nicht still ersetzen. |
| I21 | `partdesign_loft`, `partdesign_subtractive_loft` -> D.`loft`, `subtractive_loft` | W; >=2 sketch_names, solid=True, ruled; closed nur additiv | teilweise; K, H-I `additive_loft`, `completed_subtractive_loft`, `loft_rejects_unsupported_shell_before_creation` | 6 | Kegelstumpfvolumen additiv/subtraktiv; ruled, closed additiv separat; solid=False bleibt abgelehnt; Profilwechsel N11. |
| I22 | `partdesign_sweep`, `partdesign_subtractive_pipe` -> D.`sweep`, `subtractive_pipe` | W; sketch_name/spine_name; solid=True nur additiv; gesamtes Spine-Objekt | teilweise; K, H-I `additive_sweep`, `completed_subtractive_pipe` | 6 | Gerade und geknickte Pfade; Subkanten/Orientierung/Transition fehlen (N11); kein PartDesign-Shell. |
| I23 | `partdesign_hole` -> D.`hole` | W; sketch_name, diameter, depth, threaded=False, thread_type ISO/UTS, thread_size=M6 | teilweise; K, H-I `completed_threaded_hole` (ISO M6x1.0) | 6 | Blind/Durchgang/Senkung und explizite Gewindeauswahl N12; UTS derzeit nicht live belegt. |
| I24 | `partdesign_fillet`, `partdesign_chamfer` -> D.`fillet`, `chamfer` | W; base_name, edges=[EdgeN], radius bzw. size konstant | teilweise; K | 6 | Ausgewaehlte Kanten und Groesse nach Bearbeitung; robuste Auswahl N07; weitere Fasenvariante N12. |
| I25 | `partdesign_thickness`, `partdesign_draft` -> D.`thickness`, `draft` | W; base_name/faces, value bzw. angle und plane_name; Draft-Neutralebene effektiv Pflicht | teilweise; K, H-I `completed_draft` | 6 | Wanddicke/Entformungswinkel; fehlende Thickness-Optionen N12; leere/ungueltige Flaechenauswahl und unmoegliche Dicke. |
| I26 | `partdesign_linear_pattern`, `partdesign_polar_pattern`, `partdesign_mirrored` -> D.`linear_pattern`, `polar_pattern`, `mirrored` | W; feature_name; X/Y/Z, length/occurrences; X/Y/Z, angle/occurrences; XY/XZ/YZ | teilweise; K, H-I `linear_pattern`, `polar_pattern`, `mirrored` (Y, Z, YZ) | 6 | Alle Achsen/Ebenen, Kopienanzahl und Volumen; Mehrfachoriginale/Transformationen N13. |
| I27 | `part_box`, `part_cylinder`, `part_sphere`, `part_cone`, `part_torus` -> P.`make_box`, `make_cylinder`, `make_sphere`, `make_cone`, `make_torus` | W; x/y/z/name; length/width/height; radius/height/angle; radius; radius1/radius2/height; radius1/radius2 | vorhanden; K, H-M (Box), H-D; keine dedizierten Live-Tests aller Primitiven | 7 | Analytische Volumen/BBox fuer alle fuenf sowie Teilzylinder; ungueltige Dimensionen kontrolliert. |
| I28 | `boolean_fuse`, `boolean_cut`, `boolean_common` -> P.`boolean_fuse`, `boolean_cut`, `boolean_common` | W; obj_names bzw. base_name/tool_name, name | teilweise; K | 7 | Zwei ueberlappende Boxen mit bekannten Vereinigungs-/Differenz-/Schnittvolumen; leere/null/ungueltige Ergebnisse diagnostizieren (N15). |
| I29 | `part_fillet`, `part_chamfer` -> P.`part_fillet`, `part_chamfer` | W; obj_name, edges=[1 oder Edge1,...], radius bzw. size konstant | teilweise; K, H-I `completed_part_dressups_remain_parametric`, H-M (Fillet) | 7 | Parametrik bleibt nach Basisaenderung; mehrdeutige/veraltete Auswahl N07, unmoegliche Radien N15. |
| I30 | `set_placement`, `move_object`, `rotate_object` -> P.`set_placement`, `move_object`, `rotate_object` | W; x/y/z, rx/ry/rz (X dann Y dann Z); dx/dy/dz; axis_x/y/z und angle | vorhanden/getestet K3/I3 | 3 | Bekannter Punkt nach Placement-Rotation X/Y/Z/Kombination und inverser Bewegung geprueft; Elternkoordinatenvertrag N02. |
| I31 | `scale_object`, `mirror_object` -> P.`scale_object`, `mirror_object` | W; factor (uniforme statische Shape-Kopie), name; plane XY/XZ/YZ (Part::Mirroring) | vorhanden; K | 7 | Faktor 2 ergibt achtfaches Volumen, Original unveraendert; alle Spiegelebenen, unbekannte Ebene ablehnen. Kein parametrisches Scale zugesagt. |
| I32 | `screenshot`, `set_view`, `fit_view` -> V.`get_screenshot`, `set_view`, `fit_all`; additiv `capture_view`, `highlight_subelements`, `get_view_state` -> geometry_ops | R/W; neue Aufnahme explizit dokumentgezielt, 64..2048 px, sieben nichtanimierte Ansichten, GUI-Auswahl separat | vorhanden/getestet K4/I4/M4 | 4b | N07 abgenommen: richtige Blickrichtung/Dimensionen, sichtbare Geometrie, fremde Kamera/Aktivdokument/Auswahl erhalten. Alt-Screenshot recomputet weiterhin; neue Aufnahme nicht. |
| I33 | `set_visibility`, `set_color`, `set_transparency` -> V.`set_visibility`, `set_color`, `set_transparency`; lesen via `get_view_state` | W/R; explizites Objekt; r/g/b endliche Werte 0..1; transparency integer, geklemmt 0..100 mit tatsaechlichem Rueckgabewert | vorhanden/getestet K4/I4/M4 | 4b | Lesen/Setzen/Wiederherstellen sowie negative/obere Grenzwerte und ungueltige Farben geprueft. |
| I34 | `export_step`, `export_stl`, `export_obj` -> V.`export_step`, `export_stl`, `export_obj` | F/R; path, obj_names=None: sichtbare Endergebnisse; leere Liste Fehler; Mesh linear=0.1 mm, angular=0.5 rad, Relative=False fest | teilweise; K, H-I `export_step_roundtrip`, `export_stl_and_obj_roundtrip`, `export_empty_selection_fails`, `export_hidden_body_is_excluded`, H-M | 11 (Basis 8) | G-Dateiregeln und N21; Optionen/Metadaten fehlen; STEP-Solids und Mesh-Volumen vergleichen, keine Body-Duplikate. |
| I35 | `import_step`, `import_stl` -> V.`import_step`, `import_stl` | W/F; path, doc_name | teilweise; K; H-I liest STEP/Mesh direkt, prueft nicht diese Importwrapper | 11 | MCP-Import in frisches Dokument, Einheit/Objekte/Diagnose; OBJ-Import und weitere Formate N21. |
| I36 | `measure` -> V.`measure_object`; additiv `measure_distance`, `measure_angle`, `check_interference` -> geometry_ops | R; Volumen/Flaeche/BBox/Schwerpunkt, endlicher BRep-Minimalabstand, kleinste unorientierte Linien-/Ebenenwinkel, statische Solid-Interferenz | vorhanden/getestet K4/I4/M4 | 4b | Box 10*20*30: V6000/A2200/Schwerpunkt(5,10,15), Abstand5, Kontakt V0, Ueberlappung V3000, 0/90-Grad-Winkel und Toleranzkontakt bestanden. Keine Masse ohne Dichte. |
| I37 | `undo`, `redo` -> V.`undo`, `redo` | W; doc_name | teilweise; K, H-I `rpc_undo_redo_and_rollback`, H-M | 2 | Transaktions-/Mehrdokumentregeln N02; Dateien sind nicht per Undo rueckgaengig. |
| I38 | `execute_python` -> Client/RPC `execute` -> Executor `_execute_code` | C/W/F; code, freie Python-Ausfuehrung | ausgeschlossen als CAD-Ausweg; H-U, H-M (Sonderpfad) | 12 | Normalmodus deaktiviert auch direkte/indirekte RPC-Codepfade; kein Sandbox-Versprechen (N22). |

### RPC- und interne Infrastruktur

Die fuenf exponierten Dienstmethoden in `FreecadRPCService` sind `ping`,
`get_version`, `get_document_state`, `execute_function` und `execute`.
`execute_function(module,function,args_json)` ist der strukturierte Dispatcher;
`execute` fuehrt freien Code aus. Diese Methoden sind keine fuenf weiteren
MCP-Tools und werden nicht zu den 80 CAD-Funktionen addiert.

`start_server`/`stop_server`, `GuiExecutor` sowie
[security.py](../freecad_addon/freecad_ai_bridge/security.py) mit
`check_command`, `check_module`, `resolve_function` sind Infrastruktur, keine
CAD-Tools. Allowlist und Herkunftspruefung erlauben nur passende oeffentliche
Funktionen der fuenf CAD-Module. Der GUI-Executor gruppiert bestimmte Mutationen
in vorhandenen Dokumenten in Transaktionen, uebernimmt jedoch keine bereits
offene Transaktion. Er kann wartende Auftraege verwerfen, laufende nicht sicher
stoppen. Einheitlicher Batch-/Job-/Dateitransaktionsvertrag fehlt.

## Fehlende Zielanteile und begrenzte Varianten

Diese Zeilen ergaenzen I01-I38, nicht eine beliebige Workbench-Vollabdeckung.
Neue Tool-Namen werden hier **nicht** als bereits bestehende API festgelegt.
Auch hier gilt FreeCAD 1.1/Windows; alle Zielparameter sind bestaetigter Zielumfang.
Keine passende dedizierte Testsuite fuer die neuen Anteile vorhanden (`-`),
sofern nicht anders angegeben. Positive und negative Kriterien gelten je
aufgezaehlter Variante nach V; nicht bloss je Sammelzeile.

| ID | Funktion und verbindlich vorgeschlagene Varianten/Parameter | Art | Status; bisheriger Nachweis | Zielstufe | Pruefkriterium |
| --- | --- | --- | --- | --- | --- |
| N01 | Version/Capabilities, Schemas, strukturierte Fehler: FreeCAD/Bridge/MCP-Version, Featureflags, Eingaben/Einheiten, betroffene Referenzen, Warnungen/Fehlercode | R/C | vorhanden/getestet K2F/M2F; additive Migration und genaue Grenzen in CONTRACTS | 2 | Abgenommen: Versions-/Workbench-/implementierte Optionsmerkmale, Pflichtfelder/Defaults/Metadaten, neue strikte Schemas, Serialisierung, Fehler und Alt-Kompatibilitaet. Native Fachvarianten bleiben ihren Zielstufen zugeordnet. |
| N02 | Explizite Dokument-/Objektreferenzen; Koordinaten; Mutationstransaktionen; Vorschau; erlaubte Batches mit Ergebnisreferenzen, maximal 100 Schritte; ein Dokument atomar, dokumentuebergreifend expliziter Teilstatus, Datei-I/O nicht im atomaren Batch | R/W/C | vorhanden/getestet K2F/M2F/I2F; elf erlaubte Batchoperationen, statische Vorschau laut CONTRACTS | 2 | Abgenommen: Erfolg/Mittelfehler/Undo/Redo/Rollback, gleiche Namen in zwei Dokumenten, fremde ausstehende Transaktionen, Vorvalidierung, 100-Schritt-/Payloadgrenze, Datei-/Lifecycle-Ausschluss. Keine Geometriesimulation oder Dateitransaktion zugesagt. |
| N03 | Dokument aktivieren/recompute/Dirty-State; Body/Gruppe anlegen, Mitglieder und Tip lesen/setzen; sichere Close-/Save-As-Regeln | R/W/F | vorhanden/getestet K3/I3/M3 | 3 | Abgenommen: zwei Dokumente, Tip/Mitgliedschaft, Dirty-/Dateisperr-/Ueberschreibschutz, Save/reopen. Sichere Werkzeuge additiv; Altverhalten dokumentiert. |
| N04 | Typisierte Properties lesen/setzen: Bool, Integer, Float, String, Enumeration, Quantity, Vector, Placement, Link/LinkSub und native Listen; Metadaten Typ/Einheit/Schreibbarkeit/Auswahlwerte; explizite freigegebene Typen, keine Methodenaufrufe | R/W | vorhanden/getestet K3/I3/M3 | 3 | Abgenommen fuer 29 native Typen laut Capabilities: Roundtrip, Fehler/Rollback, Read-only/Enum/Einheit/Referenz/Constraint-Clamping. Unbekannte Typen nur Diagnose. |
| N05 | Spreadsheet erstellen, Zellenbereiche lesen/setzen/leeren, Aliase setzen/entfernen; Expressions lesen/setzen/entfernen und Abhaengigkeiten auflisten; arithmetische Formeln mit Einheiten/Zell- und Objektverweisen | R/W | vorhanden/getestet K3/I3/M3 | 3 | Abgenommen: A1-Parameterteil, Recompute, Doppelalias/Referenz/Zyklus/ungueltige Innenmasse mit Rollback. Keine Makros/Funktionsaufrufe; native-kompatible Aliase freigegeben. |
| N06 | Label umbenennen (interner Name stabil), unabhaengige Objektkopie, App::Link im/zwischen Dokumenten, Gruppieren/Ungruppieren; In-/Out-Abhaengigkeiten, Loeschvorschau und explizites Loeschen einer bestaetigten abhaengigen Menge | R/W | vorhanden/getestet K3/I3/M3 | 3 | Abgenommen: rekursive Kopie inkl. Expressionsquelle unabhaengig, Links propagieren vor/nach reopen, Container/Zyklen/Origin-Loeschmenge/Undo. Externe Abhaengige blockieren Loeschen. |
| N07 | Flaechen/Kanten/Vertices auflisten und kombinierte Filter: Typ, Position/BBox, Normalen-/Achsenrichtung, Radius, Flaeche/Laenge; Toleranz, Trefferzahl, Dokumentrevision; Highlight und dokumentgezielte Ansicht; Minimalabstand, Linien-/Ebenenwinkel, Schnittvolumen und Kontakt/Interferenz | R/W | vorhanden/getestet K4/I4/M4; neun Tools in geometry_ops, Vertrag in CONTRACTS | 4a/4b | Abgenommen: analytische Fixtures, 0/1/mehrere Treffer, Topologie-/Namenswechsel, Undo/Redo/reopen, sechs revisionsgepruefte Dress-up-Verbraucher, Messungen/Ansichtsisolation. GUI-Markierung separat vom nativen PNG; nur statische diskrete Kollision. |
| N08 | Geometrie/Constraints inspizieren, aendern/loeschen; Construction umschalten; treibend/Referenz und aktiv/inaktiv; zusaetzlich Linienlaenge, Punkt-Punkt-X/Y, Durchmesser, Punkt-auf-Objekt, Linienwinkel zur Achse; Diagnose DoF, Konflikte/Redundanzen mit IDs | R/W | vorhanden/getestet K5/I5/M5 | 5 | Abgenommen: Gehaeuse/Flansch DoF=0 ohne Block, Massaenderung bleibt editierbar; Konfliktrollback erhaelt den exakten Vorzustand. Keine beliebige Spline-Edit-Suite. |
| N09 | Externe Geometrie projizieren/verknuepfen/entfernen; Sketch-Attachment an Datum oder planare Flaeche mit Offset/Rotation; Trimmen, Verlaengern, Verrunden fuer Linien/Kreisboegen, Spiegeln/Kopieren einer Sketch-Auswahl | R/W | vorhanden/getestet K5/I5/M5 | 5 | Abgenommen fuer revisionsgepruefte Kanten, `FlatFace`/`ObjectXY`, Trim/Extend/Fillet/Copy/Mirror. FreeCAD 1.1: Trim ohne Achsen; keine automatische Reparatur verlorener Supports. |
| N10 | Datumebene/-achse/-punkt: explizites Placement oder planare/zylindrische Referenz, Attachment-Offset; Pad/Pocket: Mass, bis erste/bis Flaeche; Pocket durch alles; einseitig umgekehrt, symmetrisch, zwei unabhaengige Laengen | R/W | teilweise (I19); K/H-I Pad | 6 | Jede Endbedingung separat, Basisflaeche verschieben aktualisiert Ende; leere/mehrdeutige Zielflaeche ablehnen; gueltiger einzelner Body-Solid. |
| N11 | Revolution/Groove: Voll-/Teilwinkel, einseitig/reversed/symmetrisch/zwei Winkel, Sketch-/Datumachse; Loft additiv/subtraktiv ruled/glatt, closed nur additiv; Pipe additiv/subtraktiv mit ausgewaehlten Pfadkanten, konstantem Profil, Standard/Frenet-Orientierung, transformed/right/round Transition; Profile/Parameter nachtraeglich ersetzen | R/W | teilweise (I20-I22); K/H-I Teilmenge | 6 | Je Option gueltiges Referenzfixture, analytische Rotation/gerades Pipevolumen; unsupported Kombinationen vor Erstellung melden; kein Mehrprofil-/variabler Querschnitts-Pipe zugesagt. |
| N12 | Hole: blind/durchgehend, einfach/zylindrisch gesenkt/kegelig gesenkt, Senkdurchmesser/-tiefe/-winkel, unthreaded oder ISO metrisch/UNC mit expliziter Groesse/Steigung aus Capability-Liste; Fillet konstant; Chamfer gleich/ungleiche Abstaende; Thickness innen/aussen, arc/intersection-Verbindung; Draft Neutralebene/Pullrichtung/Winkel | R/W | teilweise (I23-I25); K/H-I ISO/Draft | 6 | Je Variante Sollmasse und Bearbeitung; falsche Gewindegroesse, Senkung ausserhalb Bauteil, Selbstschnitt/zu grosse Radien kontrolliert; Gewinde metadatenbasiert/vereinfacht, keine Helixpflicht. |
| N13 | Linear-/Polarmuster, Spiegelung: mehrere Originalfeatures, Origin-/Datumachsen/-ebenen, Laenge/Winkel/Anzahl; geordnete MultiTransform-Kette aus diesen drei Typen; Featureparameter/Profile bearbeiten, Tip sichern | R/W | teilweise (I26); K/H-I je ein Basisfall | 6 | Anzahl/Lage/Volumen nach Aenderung; kombinierte Spiegel-/Linearkette; unverbundene Body-Ergebnisse und zyklische Abhaengigkeiten ablehnen. |
| N14 | Part-Extrusion/Revolution aus Draht/Flaeche mit Vektor/Laenge bzw. Achse/Winkel; Loft ruled/glatt/geschlossen und Sweep konstantes Profil Standard/Frenet, als Flaeche oder Solid; geordnete Kanten zu Draht, planare Flaeche mit Loechern, Flaechen zu Shell, geschlossene Shell zu Solid | R/W | fehlt; - | 7 | Drahtabschluss und Orientierungen, Zylinder-/Prismenvolumen; sechs Wuerfelflaechen zu einem gueltigen Solid; offene Shell darf kein scheinbarer Solid werden. |
| N15 | Boolesche Qualitaetsdiagnose; Section-Kurven, Split an Ebene/Schneidkoerper, 2D-Draht-/3D-Shape-Offset; BRep-Validierung, refine, toleranzbegrenztes Sewing/Shape-Fix mit Vorher-/Nachherbericht | R/W | teilweise (I28/I29); K | 7 | Bekannte Schnittgeometrie/Anzahl Teilvolumen und Volumenerhaltung; heilbare Luecke innerhalb Toleranz vs. nicht heilbare ausserhalb; keine universelle Reparaturzusage. |
| N16 | Jobs starten, ID/Status/Fortschritt soweit verfuegbar/Ergebnis abrufen; Timeout/Wiederverbinden, wiederholtes Ergebnislesen ohne Mutation, queued cancel; running cancel nur als unterstuetzt melden wenn tatsaechlich moeglich; paginierte Objektuebersichten und begrenzte Bildgroessen | R/W/C | teilweise (Queue/Timeout); H-U | 8 | Queued/running/erfolgreich/fehlgeschlagen/abgebrochen und Verbindungsverlust testen; keine doppelte Mutation beim Wiederholen; nach Prozessverlust Zustand unbekannt melden. Keine Persistenz laufender Jobs ueber Prozessneustart zugesagt. |
| N17 | Durchgaengige mechanische MCP-Workflows fuer Gehaeuse, Flansch, Schraubstock; strukturierte Batch-Ergebnisreferenzen und Bildrueckmeldung | R/W/F | fehlt als Gesamtworkflow; H-M/H-D sind nur Teilbelege | 8 | A1-A3 erstellen, aendern, Fehler behandeln, pruefen, speichern/oeffnen/exportieren; Protokoll ohne Codeausweg. |
| N18 | Native FreeCAD-Assembly: Komponenten/Links aus einem oder mehreren Dokumenten, fixieren/positionieren, Fixed/Revolute/Slider/Cylindrical/Ball-Gelenke; Referenzen, Limits/Offsets soweit fuer den Typ definiert, DoF/Solverdiagnose, diskrete Bewegungszustaende | R/W/F | fehlt; - | 9 | A4 plus je ein Fixture aller fuenf Gelenktypen; Fix=0, Dreh/Schub=1, Zylinder=2, Kugel=3 relative DoF; Ueberbestimmung, fehlende Quelldatei und Kollision melden; native API-Verfuegbarkeit vor Implementierung pruefen. |
| N19 | TechDraw: mitgelieferte/benannte SVG-Vorlage, Seite, Einzel-/Projektionsansichten, orthogonaler Schnitt, Detail; Laengen/Abstands-/Durchmesser/Radius/Winkelmasse, Text/Leader; Position/Massstab, Aktualisierung, PDF/SVG | R/W/F | fehlt; - | 10 | A5 plus Radius-/Winkel-/Detailfixture; Modellbezug nach Aenderung intakt, keine ueberlappenden Pflichtangaben; fehlende Vorlage/verlorene Referenz kontrolliert. |
| N20 | Draft: Linie, offener/geschlossener Wire, Rechteck, Kreis/Bogen, Text/Label mit Placement; rechteckiges Array (Anzahl/Abstaende XYZ) und Polararray (Achse/Winkel/Anzahl), bearbeiten/loeschen | R/W | fehlt; - | 11 | Elementmasse/Placement, 2x3-Array=6 Instanzen und Polararray=4; Aenderung propagiert, Anzahl 0 und kaputte Quelle ablehnen. Kein kompletter Draft-Befehlskatalog. |
| N21 | Mesh: Facetten/Komponenten/BBox/geschlossen/Orientierung/Defekte lesen; doppelte/degenerierte Facetten entfernen, Normalen korrigieren, begrenzte Loecher schliessen; Shape->Mesh mit Toleranzen, geschlossenes Mesh->Shape/Solid mit Diagnose; FCStd, STEP Import/Export, STL/OBJ Import/Export, DXF/SVG fuer vereinbarte planare Draft-Geometrie; TechDraw PDF/SVG bei N19 | R/W/F | teilweise (I34/I35); K/H-I Exportbasis | 11 | Formatvertrag X; Box mit fehlender Facette reparierbar, nichtmanifold Fixture darf nicht still Solid werden; Roundtrips mit Geometrie/Einheiten und Verlustbericht. Keine automatische Reverse-Engineering-Parametrik. |
| N22 | Normalmodus ohne freie Codeausfuehrung, Installieren/Update/MCP-Neustart, Versions-/Grenzdokumentation; optionaler Entwicklermodus nur explizit und ohne Sandboxbehauptung | C/R | teilweise (Allowlist, Anleitung); H-U | 12 | A1-A5 und alle I/N-Varianten ueber echten MCP-Transport; direkter RPC `execute` und indirekte Codeaufrufe im Normalmodus abweisen; frische Installation/Neustart pruefen. |
| X01 | FEM, Solver, Lasten, Vernetzung fuer FEM, Festigkeitsnachweise | - | ausgeschlossen | keine | Keine FEM-Anforderung/Abnahme; vorhandene Modelle/Skripte begruenden keinen Umfang. |
| X02 | CAM: Aufspannung, Werkzeuge, Werkzeugwege, Simulation, Postprozessoren | - | ausgeschlossen aus Kern; optional | 13, nicht freigegeben | Eigenen Umfang/Abnahme erst nach Benutzerauftrag; keine Maschinensicherheitszusage. |
| X03 | BIM/Arch: Bauelemente, Gebaeude, IFC, Auswertungen | - | ausgeschlossen aus Kern; optional | 14, nicht freigegeben | Eigener Auftrag und IFC-Vertrag erforderlich. |

## Stufenabgleich und bestaetigte Teilstufen

Stufe 1 liefert diese Matrix und [ACCEPTANCE.md](ACCEPTANCE.md); ihr Gate ist
die am 2026-09-16 erteilte ausdrueckliche Umfangsbestaetigung. Kein Matrixeintrag ist dadurch bereits
funktional abgenommen. Stufen 2-12 bleiben Kern, 13/14 optional, FEM draussen.

| Stufe | Matrixbezug | Begruendete Teilung und Abnahmegate |
| --- | --- | --- |
| 2 | I01/I37, N01-N02 | 2a Schemas/Referenzen/Capabilities, 2b Transaktionen/Vorschau/Batch; verhindert Vermischung von API-Migration und Mutationsverhalten. Zwei-Dokument-Test vor Abschluss. |
| 3 | I02-I04/I18/I30, N03-N06 | 3a Dokumente/Properties, 3b Spreadsheet/Expressions, 3c Kopien/Links/Abhaengigkeiten; A1-Parameterteil und G-Dateizyklus. |
| 4 | I32-I33/I36, N07 | 4a Auswahl/Revision, 4b Messung/Kollision/Bild; analytische Fixtures und Mehrdeutigkeit. |
| 5 | I05-I17, N08-N09 | 5a CRUD/Constraints/Diagnose, 5b Referenzen/Zeichenbearbeitung; A1/A2-Profile DoF=0. |
| 6 | I19-I26, N10-N13 | 6a Datum/Endbedingungen, 6b Rotation/Loft/Pipe, 6c Hole/Dress-ups/Muster; getrennte API-Risiken, A1/A2 und Variantentests. |
| 7 | I27-I29/I31, N14-N15 | 7a Part/Flaechenbildung, 7b Schnitt/Offset/Validierung/Reparatur; geschlossener Wuerfel und Negativfixtures. |
| 8 | N16-N17, I34 Basis | 8a Job-/Timeoutvertrag, 8b A1-A3 End-to-End; kein Demo-Skript als Ersatz. |
| 9 | N18 | 9a Komponenten/Links, 9b Gelenke/Solver/Bewegungszustaende; A4 und fuenf Gelenkfixtures. |
| 10 | N19 | 10a Seite/Ansichten, 10b Masse/Update/Export; A5 plus Variantenfixtures. |
| 11 | I34-I35, N20-N21 | 11a Draft, 11b Mesh, 11c Austausch; eigene Geometrie-/Informationsverlustorakel erforderlich. |
| 12 | I38, N22, alle Kernzeilen | 12a Betriebsmodus/Installation, 12b Gesamtabnahme; keine offenen Pflichtvarianten oder stillen Capability-Ausnahmen. |
| 13/14 | X02/X03 | Keine Planung/Implementierung ohne gesonderten Auftrag. |

Diese Teilung veraendert nicht die Stufenreihenfolge und startet keine Teilstufe.
Bei nicht verfuegbarer FreeCAD-1.1-API: betroffene Zeile blockiert lassen und
eine Umfangsaenderung zur Entscheidung vorlegen, nicht automatisch streichen
oder durch freie Python-Ausfuehrung ersetzen. Offene Entscheidungen stehen
zentral im [Abnahmevertrag](ACCEPTANCE.md).
