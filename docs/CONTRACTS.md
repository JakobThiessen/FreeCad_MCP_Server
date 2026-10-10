# MCP-Vertrag 1.0: Stufen 2 bis 11

Stand: 2026-10-10. Implementierte Stufen 2 bis 11 und Teilnachweis 12a aus
[AGENTS.md](../AGENTS.md); Gesamtabnahme Stufe 12 bleibt offen.
Teststand und offene Gates: [memory.md](../memory.md).
Dieser additive Vertrag umfasst Schemas, Referenzen, Transaktionsbesitz,
Vorschau und begrenzte Batchausfuehrung. Die Alt-API bleibt dokumentiert.

## Stufe 12: Teilnachweis 2026-10-10

Normalmodus: `execute`/`execute_python` lehnen mit `raw_python_disabled` ab;
private, fremde oder importierte RPC-Ziele mit `rpc_not_allowed`, unzulaessige
Jobziele mit `job_operation_not_allowed`. Nur exakt der Prozess-Opt-in
`FREECAD_MCP_ALLOW_RAW_PYTHON=1` aktiviert freien Entwicklercode. Keine Sandbox.
113 Negativchecks je Lauf pruefen direkte RPC-, MCP-, Job-/Batch- und
Expression-/Spreadsheetpfade. Native Spreadsheet-Zellen koennen `=import os`
als maskierten Literaltext speichern; dies ist keine Ausfuehrung. Ausfuehrbare
Funktionsausdruecke werden abgewiesen. Zulaessige Texte sind nicht generell verboten.

`capture_view` erhaelt jetzt die Orientierung des vorher aktiven Fremddokuments
explizit und pausiert dessen Kameraanimation waehrend des GUI-Wechsels.
Native Assembly-Gelenke erhalten bei Erzeugung ihren `ViewProviderJoint`, damit
FCStd-Restore/zweiter Edit/Recompute keinen numerischen Proxyplatzhalter aufruft.
API/Schemas und Versionen bleiben 0.11.0/0.1.0; geladenen Code per Hash pruefen.
Neue Dateien profitieren vom Fix; eine Migration bereits fehlerhaft gespeicherter
Gelenk-ViewProvider ist nicht implementiert und bleibt offen.

30 vorhandene MCP-Gates bestanden auf GUI 1.1.1; daraus folgt keine vollstaendige
V-Abdeckung. Der genaue Restumfang und isolierte Installationsteil stehen in
[COVERAGE.md](COVERAGE.md). Gesamtabnahme und Benutzerfreigabe bleiben offen.

## Werkzeuge und Referenzen

### Mesh und Austausch: 11b/11c auf FreeCAD 1.1.1 geprueft

Sieben additive Werkzeuge, insgesamt 194 registrierte Tools; Bridge 0.11.0 und
Paket 0.1.0 unveraendert. ContractResponse, explizite Dokument-/Objekt-Names,
GUI-Executor, keine freie Codeausfuehrung oder neue Batchoperationen.
mesh_editing/structured_exchange gelten nur fuer die gepruefte GUI 1.1.1;
andere Patches, insbesondere 1.1.4 fuer Stufe 11, sind ungeprueft.

| Werkzeug | Eingaben und Ergebnis |
| --- | --- |
| mesh_create | 1..100000 Dreiecke mit je drei endlichen XYZ-mm-Punkten; natives Mesh::Feature und Diagnose. |
| mesh_inspect | Facetten/Punkte/Komponenten, globale BBox, Flaeche/Volumen, Abschluss/Orientierung, doppelte/degenerierte Facetten, Rand-/Nonmanifoldkanten, Normalen, Selbstschnitte und ungueltige Punkte. |
| mesh_from_shape | Absolute lineare Abweichung in mm, Winkel in rad bis pi, Relative=False; globale statische Triangulation mit angewandten Optionen. |
| mesh_repair | Duplikate/degenerierte Facetten entfernen, native Normalenkorrektur; max_hole_edges 0..10000, 0 deaktiviert Lochfuellung; Flaechentoleranz in mm2, require_closed; Diagnose vor/nach, entfernte Facetten und Grenzen. |
| mesh_to_shape | target shape/solid, positive mm-Toleranz; valide statische facettierte BRep. Solid nur fuer eine geschlossene, konsistent nach aussen orientierte Komponente ohne die diagnostizierten Defekte. |
| exchange_export | Explizite eindeutige Auswahl 1..100 Names; absoluter Pfad mit passender Endung, diskriminierte Optionsobjekte, overwrite=False. |
| exchange_import | Explizites Zieldokument, absoluter Pfad, Format und mm-Annahme; neue Referenzen, gezielte Geometrie/Metadaten und Verlustwarnungen. |

Mesh-Reparatur ersetzt das Original erst nach erfolgreicher Zielpruefung und
laeuft in einer eigenen Undo-Transaktion. Nonmanifold, ungueltige Punkte und
Selbstschnitte sind ausserhalb des Reparaturvertrags. Keine allgemeine Heilungs-
oder Reverse-Engineering-Zusage. Konvertierungen sind statisch, ohne
parametrische Quellabhaengigkeit. Parent-/Mesh-Placement geht genau einmal in
globale Messung, Konvertierung und Export ein. Native Mesh.Volume ist auf der
geprueften Version unsigned; Orientierung nutzt signiertes Facettenvolumen.
Strukturierte Fehler koennen additiv error.diagnostics enthalten.

STEP verlangt step_schema AP214/AP242; AP214IS/AP242DIS und mm werden intern
gesetzt und bestehende native Einstellungen auch bei Fehlern restauriert.
Der wirkliche FILE_SCHEMA-Header wird geprueft, kein stiller Downgrade.
Geprueft: zwei unterschiedlichfarbige Links, Labels, globale Placements,
8000 mm3 je Solid und ein Container mit zwei Kindern je Schema. App::Part und
einfache Dokumentgruppen werden als statische native Baugruppenknoten exportiert.
Uniforme geerbte Objekt-RGB sind nachgewiesen; per-Face-Paletten und eigene
Link-Farbueberschreibungen sind ungeprueft. Featurebaum, externe Linkidentitaet,
Expressions, Constraints und Gelenke gehen verloren und werden nicht versprochen.

STL verlangt encoding ascii/binary; OBJ importiert/exportiert Dreiecksmeshes.
Beide erlauben absolute linear_deflection/angular_deflection in mm/rad,
Defaults 0.1/0.5. Einheiten sind explizit mm, da Meshdateien keine verlaessliche
Einheit tragen. Keine Materialien, Texturen, Farben oder Baugruppen zugesagt.
DXF/SVG: Linien, offene/geschlossene Polylinien, Kreis/Bogen in globalem XY,
Z=0. DXF nutzt native Kantensortierung zur statischen Wire-Rekonstruktion;
Quellsegmentierung/Labels gehen verloren. SVG normalisiert die native XML-
Huelle auf mm und CAD-Koordinaten; kreisfoermige native Ellipsen werden nur
bei gleichen Halbachsen innerhalb 1e-7 mm als Kreis erkannt. Keine echte
Ellipse-/Spline-/3D-/Text-/CSS-/Bild-/Layout-Roundtripzusage.

Import maximal 64 MiB und 1000 erzeugte Objekte; Mesh maximal 100000 Facetten.
Fehlerhafte Imports rollen die eigene Dokumenttransaktion zurueck. Export
verweigert fremde offene Dokument-/Anwendungstransaktionen, arbeitet in einer
eigenen temporaeren Kopie und veraendert nicht die Quellobjekte. App-/GUI-
Aktivdokument und Auswahl werden restauriert. Staged Datei im Zielverzeichnis,
atomare No-Clobber-Publikation bzw. expliziter Replace; Fehler hinterlassen
keine neue Zieldatei. Dateien sind nicht per Dokument-Undo rueckgaengig.
Legacy export_step/export_stl/export_obj bleiben kompatibel; explizite neue
Formatoptionen laufen ueber exchange_export, nicht ueber deren native Defaults.

### Draft: Teilstufe 11a auf FreeCAD 1.1.1 geprueft

Fuenf additive Werkzeuge verwenden `ContractResponse`, explizite Dokumente,
den GUI-Executor und eigene Dokumenttransaktionen. `draft_modeling=true` gilt
nur mit GUI auf der geprueften Patchversion 1.1.1; `options.draft` beschreibt
Varianten und Grenzen. Kein neuer Release: insgesamt 194 Tools, Bridge 0.11.0/Paket 0.1.0.

| Tool | Vertrag |
| --- | --- |
| `draft_create_element(doc_name, spec, name="DraftElement")` | Native Linie, offener/geschlossener Wire, Rechteck, Kreis, Bogen, Text oder Custom-Label; diskriminierter `kind`, keine freien Methoden oder Codefelder. `name` setzt das Label; den nativen internen Name aus der Antwort fuer Folgeaufrufe verwenden. |
| `draft_edit_element(doc_name, obj_name, spec)` | Vollstaendige Spezifikation derselben Art; Identitaet und Parametrik bleiben erhalten. Weggelassene optionale Werte werden auf Defaults gesetzt, kein partieller Patch. Abhaengige strukturierte Arrays werden nach Recompute validiert. |
| `draft_create_array(doc_name, base_name, spec, name="DraftArray")` | Native nichtverschmolzene Ortho-/Polararrays einer gueltigen, recomputeten gleichdokumentigen Shape; Quellsichtbarkeit bleibt erhalten. Quellen ohne Shape (z.B. Text) unzulaessig. |
| `draft_edit_array(doc_name, obj_name, spec)` | Vollstaendige Spezifikation derselben Arrayart, ohne Quellenwechsel. |
| `draft_inspect(doc_name, obj_name)` | Gezielte native Referenz/Art, Placement, Geometriekennwerte oder Text sowie Quellenreferenz/Instanzzahl; kein Recompute. Globale analytische BBox ueber `optimalBoundingBox(False, False)`. |

Koordinaten/Einheiten: alle Laengen und Textgroessen in mm; elementlokale
XYZ-Punkte werden durch `placement.position` (dokumentglobal, Default Null)
und normiertes Quaternion XYZW (Default Identitaet) transformiert. Label-
`target_point`, Array-Zentrum und Array-Achse sind dokumentglobal. Nur endliche
echte Zahlen, keine Booleans. Linie verlangt zwei verschiedene Punkte; Wire
2..256 (geschlossen mindestens 3), ohne doppelte Nachbarpunkte oder explizit
wiederholten Abschluss. Rechteckseiten/Radius/Textgroesse strikt positiv.
Bogen: Grad, `0 <= start_angle < end_angle <= 360`, Sweep kleiner als 360.
Text/Custom-Label: 1..32 nichtleere Zeilen bis je 4096 Zeichen, Defaultgroesse
3.5 mm; Label verlangt einen Zielpunkt. Native ViewObject.FontSize fuer beide.

Ortho: drei ganzzahlige XYZ-Anzahlen je 1..1000, Produkt hoechstens 1000;
signierte Achsabstaende, fuer wiederholte Richtungen nicht null. Polar: Anzahl
1..1000, Winkel `(0,360]` Grad, nichtnuller beliebiger XYZ-Achsenvektor. Beide
bleiben native parametrische Arrays mit `Fuse=false` und ohne Link-Modus;
Quellenaenderungen propagieren. Draft-Mutationen aktivieren voruebergehend nur
ihr Zieldokument und restaurieren App-/GUI-Aktivdokument und GUI-Auswahl nach
Transaktion und GUI-Update. Fremde Dokument-/Anwendungstransaktionen werden
abgelehnt, nicht uebernommen.

Bearbeiten/Inspektion sind auf die mit diesen Werkzeugen erzeugten nativen
Objekte begrenzt (`MCPDraftKind`, fuer Arrays `MCPDraftSource`, schreibgeschuetzt).
Fehlende/gewechselte Quelle liefert `draft_reference_lost`; keine stille
Neuzuordnung. Referenzen sind interne Names, keine UUIDs: identisch benannte
Ersetzung ist nicht erkennbar. Loeschen nutzt unveraendert `delete_object`
bzw. `preview_delete`/`delete_objects`; abhaengige Quellen nicht implizit
kaskadierend loeschen. Diese Altwerkzeuge koennen MCP `isError=true` liefern;
Draft-Domainfehler sind strukturierte `ContractResponse`-Fehler. Keine neuen
Batchoperationen. Kein vollstaendiger Draft-Befehlskatalog oder Dynamic-Label-
Ausdrucksvertrag. Nachweis: native Geometrie, XYZ-/Polarachsen X/Y/Z, GUI-
Isolation, zweimal echter MCP-Normalmodus; Artefakte in [memory.md](../memory.md).
Der historische 11a-Nachweis prueft FCStd; die separate 11b/11c-Abnahme steht in ACCEPTANCE und memory.md.

### TechDraw: A5 unter FreeCAD 1.1.1 und 1.1.4 abgenommen

Vierzehn additive Tools verwenden `ContractResponse` und den GUI-Executor:

| Tool | Vertrag |
| --- | --- |
| `techdraw_list_templates()` | Mitgelieferte SVG-Namen relativ zum nativen Templates-Verzeichnis, einschliesslich Unterordnern. |
| `techdraw_create_page(doc_name, template, name="Page")` | Explizites Dokument; benannte Vorlage oder vertrauenswuerdiger absoluter SVG-Pfad. Relative Pfade bleiben im Templates-Verzeichnis; SVG verlangt positive explizite mm-Breite/-Hoehe bis 2000 mm. Native DrawPage/DrawSVGTemplate, Massstab 1. |
| `techdraw_create_view(doc_name, page_name, source_names, direction, x, y, scale=1, name="View")` | Native DrawViewPart; 1..32 eindeutige gleichdokumentige Shape-Quellen; nichtnuller dokumentglobaler Richtungsvektor. Papiermittelpunkt x/y in mm vom linken unteren Eck; positiver Papier-/Modell-Massstab. |
| `techdraw_inspect_page(doc_name, page_name)` | Gezielte Referenzen, Papier, Template-Texte, Ansichten, Quell-/Projektions-Boundingboxen, Kantenanzahl und Warnungen; kein Recompute. |
| `techdraw_update_page(doc_name, page_name)` | Expliziter Recompute und nativer Projektionsabschluss, danach Inspektion. |
| `techdraw_set_layout(doc_name, page_name, view_name=null, x=null, y=null, scale=null, rotation=null, texts=null)` | Ansicht muss zur Seite gehoeren; Papiermittelpunkt innerhalb Blatt, Rotation in Grad, positiver Massstab. Ohne Ansicht nur Seitenmassstab bzw. bekannte Template-Schriftfeldschluessel; 1..100 Texte bis je 4096 Zeichen. Benutzerdefinierte Ansichtsmasstaebe bleiben unabhaengig vom Seitenmassstab. |
| `techdraw_export_page(doc_name, page_name, path, format, overwrite=false)` | Nur native PDF-/SVG-Ausgabe einer validierten nichtleeren Seite; absoluter formatpassender Pfad, vorhandener Elternordner. Ausgabe im Zielverzeichnis zwischengespeichert und validiert, danach No-Clobber-Hardlink bzw. explizites `os.replace`. |
| `techdraw_create_projection_group(doc_name, page_name, source_names, direction, x, y, scale=1, name="ProjectionGroup")` | Native First-angle-Gruppe Front/Top/Right; Kinder liefern absolute Papierpositionen. Quellenvertrag wie Einzelansichten. |
| `techdraw_create_section(doc_name, page_name, base_view, origin, normal, x, y, scale=1, name="Section")` | Gleichseitige Basisansicht; Ursprung dokumentglobal in mm, nichtnuller Normalenvektor senkrecht zur Basisblickrichtung; nativer orthogonaler Schnitt. |
| `techdraw_create_detail(doc_name, page_name, base_view, anchor, radius, x, y, scale=2, name="Detail")` | Native Detailansicht; Anchor XY in unskalierten Basisansichts-mm mit Y nach unten, positiver Clipradius in Modell-mm. Native Clipkontur hat in den Fixtures 1 Prozent Zugabe. |
| `techdraw_list_geometry(doc_name, page_name, view_name)` | Ausgegebene native Edge0/Vertex0-Indizes inklusive verdeckter Geometrie und Kreismittelpunkten, Revision, Laenge/Radius/Zentrum/Punkte; unskalierte Ansichts-mm, Y nach unten. Anders als 1-basierte Modell-Subelemente. |
| `techdraw_create_dimension(doc_name, page_name, kind, selections, x, y, name="Dimension")` | length/distance/distance_x/distance_y/diameter/radius/angle; 1..2 ausgegebene DrawingSelections derselben Ansicht mit aktueller Revision. Kreis fuer Durchmesser/Radius, zwei Geraden fuer Winkel. Native projizierte References2D, Arbitrary=false; Zahlenwert in mm bzw. Grad. |
| `techdraw_create_annotation(doc_name, page_name, text, x, y, size=3.5, name="Annotation")` | 1..32 nichtleere Zeilen bis je 4096 Zeichen; Papierposition/Textgroesse in mm. Bearbeiten typisiert ueber set_properties: Text und TextSize. |
| `techdraw_create_leader(doc_name, page_name, view_name, points, name="Leader")` | 2..32 XY-Wegpunkte in ansichtslokalen Papier-mm, Y nach oben; expliziter gleichseitiger LeaderParent. Bearbeiten typisiert ueber WayPoints als XYZ-Vektorliste. |

Der Vertrag meldet `techdraw_pages` und nur auf den geprueften GUI-Patchversionen
1.1.1 und 1.1.4 `techdraw_drawings=true`; `tested_versions` nennt genau diese
beiden Versionen. Die frische 1.1.1-10b/A5-Abnahme ist separat dokumentiert;
andere Patchversionen und Betrieb ohne GUI erhalten keine 10b-Zusage.
Bridge-API 0.11.0 und Paketversion bleiben unveraendert; dieser
Arbeitsbaum ist kein neuer Release und kein Update der Standardinstallation.

Mutationen nutzen vorhandene Dokumenttransaktionen. Eine bereits aktive fremde
Anwendungstransaktion wird auch bei einem anderen Zieldokument abgelehnt.
Nach Commit/Rollback wird nur die beim eigenen `openTransaction` erfasste,
noch unveraenderte globale Transaktions-ID geschlossen. Auch leere Updates
duerfen keine eigene globale ID fuer spaetere GUI-Recompute-/Redraw-Aufrufe
hinterlassen. Fremde IDs werden weder uebernommen noch geschlossen.
Fehlende Vorlage und
ungueltige Eingaben liefern strukturierte Fehler und eigenen Rollback.
`MCPSourceNames` erhaelt erwartete Quellnamen im FCStd; geaenderte/entfernte
Source-Verknuepfungen liefern `drawing_reference_lost`. Wiederverwendete Namen
sind keine UUID-Identitaet; manuell erstellte Ansichten ohne diese Provenienz
und andere als die oben genannten Ansichtstypen liefern `unsupported_feature`.
Nicht aktualisierte Quellen/Ansichten liefern `geometry_not_ready` bzw.
`drawing_not_ready`; es gibt keine Neuzuordnung verlorener Modellreferenzen.

Exakte native HLR laeuft im GUI asynchron. Der interne Abschluss nutzt zwei
Waits auf FreeCADs globalen Qt-Threadpool, je maximal 10 Sekunden, mit
GUI-Ereignisverarbeitung ohne Benutzereingaben. Quellenmutationen werden vor
dem eigenen Commit nachgefuehrt. Das kann auch andere native Pooljobs abwarten;
es ist weder isolierte Jobsteuerung noch eine harte Gesamtzeit-/Abbruchgarantie.
Kernelarbeit und ein moeglicher Rollback bleiben nicht sicher abbrechbar.

Die frueheren Transaktionsreste nach Quellen-Undo bzw. PDF sind im vollstaendigen
MCP-Doppelrun nicht mehr reproduzierbar. Die native Spur zeigte nach Undo eine
erneut geoeffnete alte `MCP: update_page`-ID; der eigene globale Abschluss
behebt den Rest, ohne den Fremdtransaktionsschutz zu umgehen. Bestehende Dateien
bleiben ohne `overwrite=true` geschuetzt; Dateiveroeffentlichung und
Dokumentrollback sind getrennt, bereits publizierte Dateien werden nicht
automatisch entfernt. Auf Dateisystemen ohne Hardlink-Unterstuetzung kann
No-Clobber-Publikation mit `file_write_failed` scheitern.

Dimensionen persistieren erwartete References2D, nativen Typ und eine geordnete
Geometrie-Rangsignatur der Kanten/Punkte/Kreiszentren/-radien. Verlorene Referenzen,
Arbitrary, Typ/Messmodus und geaenderter LeaderParent: drawing_reference_lost;
geaenderte Projektionsnachbarschaft: drawing_reference_stale. Keine Neuzuordnung;
konservative Ablehnung kann auch sinnvolle Aenderungen treffen. Neu erzeugen
erst nach expliziter Auswahl. 48->58->59 und FCStd-Reopen sind belegt, keine
universelle Topologieidentitaet. projected_bbox_mm ist unskaliert; gedruckte
Groesse ist Boundingbox mal Scale. Manuelle Kindpositionen via set_layout
deaktivieren AutoDistribute, damit Recompute das Layout nicht ueberschreibt.
Text-/Leader-/FormatSpec-Edits nutzen typisierte Eigenschaften; feste Zahlen
duerfen keine Modellbindung ersetzen. Export lehnt auch fremde globale
Transaktionen in anderen Dokumenten ab und erhaelt deren ID/Dateien.

Keine automatische Blattbelegung/Ueberlappungspruefung;
nur der Ansichts-Mittelpunkt wird auf Blattgrenzen geprueft. A5 besteht auf beiden
geprueften Versionen je zweimal 125 frische MCP-Aufrufe, Einseiten-A4-PDF/SVG, fuenf vermessene Konturen, sechs
native Masse und visuelle Pflichttextpruefung. Der feste Renderer in
`tests/mcp_smoke.py --stage10b-only` braucht lokal PyMuPDF im Host, nicht im
Server/FreeCAD. Konturen: 0,5 mm Strichtoleranz; Papier: 0,15 mm PDF-Rundung.
Keine Pixelidentitaet/identische Schriftfamilie beider nativen Exporter zugesagt.
`tests/mcp_smoke.py --stage10a-only --stage10a-render` benoetigt fuer den
optionalen Render-Gate PyMuPDF in der Host-Testumgebung, nicht im Server oder
FreeCAD. Rasterkonturen werden mit 0,8 mm Strichbreiten-/Rastertoleranz geprueft,
Papierabmessungen mit 0,15 mm PDF-Rundungstoleranz. Siehe
[ACCEPTANCE.md](ACCEPTANCE.md) und [memory.md](../memory.md).

### Versionsaudit: Bridge 0.11.0

- `execute`/`execute_python` sind standardmaessig gesperrt, Code
  `raw_python_disabled`. Einzig `FREECAD_MCP_ALLOW_RAW_PYTHON=1` in der
  FreeCAD-Prozessumgebung aktiviert den nicht sandboxed Entwicklermodus.
  Registrierung bleibt erhalten; Clients muessen Fehler pruefen.
  `get_capabilities` meldet diesen Zustand wahrheitsgemaess. Lokale Clients
  sind weiterhin eine Vertrauensgrenze; es gibt keine Authentifizierung.
- Nicht lokal definierte oder private RPC-Ziele liefern `rpc_not_allowed`.
  Jobkapazitaet wird vor Queue-Einreichung geprueft: `job_capacity` startet
  keinen unerfassten Auftrag. Bereits laufende Jobs bleiben unabbrechbar.
- RPC `get_version` erhaelt die Patchversion; `get_capabilities` weiterhin
  alle vorhandenen Buildfelder.
- `techdraw_scrub_edges(doc_name, edges, name="ScrubbedEdges")` verlangt
  1..256 `SubelementSelection`-Kanten aus demselben expliziten Dokument.
  Revisionen und dokumentglobale Transformation werden vor Ausfuehrung
  geprueft. Native API `TechDraw.scrubEdges` muss vorhanden sein, sonst
  `unsupported_feature`; kein Python- oder geometrischer Ersatzpfad.
  Quellen bleiben unveraendert. Ergebnis ist ein unabhaengiger Part-Compound
  mit `reference`, `input_edges`, `output_edges`, `source_names` und
  `parametric=false`. Undo/Redo und eigener Transaktionsrollback gelten.
  Die native API bereinigt Flaechenraender und darf offene/lose Endstuecke
  entfernen; dies wird im MCP-Schema und in `warnings` benannt. Eingangsgeometrie
  wird explizit kopiert, weil die native API interne Shapes veraendern darf.
  Keine Zusage einer geometrischen Vereinigung oder bestimmter Segmentzahlen.
  Ausgabe ist keine Seite, Projektion oder parametrische Zeichnung.
- `techdraw_scrub_edges` ist ein runtime-geprueftes Featureflag.
  `draft_modeling` und `mesh_editing` bleiben `false`; TechDraw siehe oben.
  Keine Abnahme der Stufen 11/12; Details in [Notice.md](../Notice.md).

- `get_capabilities()` liest FreeCAD-Version inklusive vorhandener Buildfelder,
  Bridge-API-Version, installierte MCP-Server-/SDK-Version, GUI-Verfuegbarkeit,
  registrierte Workbenches und explizite Featureflags. Unbekannte Paketversionen
  lauten `unknown`. Workbench-Praesenz garantiert keine einzelne API-/Enum-Option.
- `resolve_reference(doc_name, obj_name=null)` verlangt einen nichtleeren internen
  Dokumentnamen. Optionaler Objektname ist ebenfalls ein nichtleerer interner Name.
  Keine Suche nach Label/Dateipfad, kein aktives Dokument als Ersatz, keine
  Aktivierung, kein Recompute und keine Mutation. Typ und Label werden gezielt
  ausgegeben; keine unbeschraenkte Property- oder Geometrieliste.
- Referenzdaten: `{"document": "Doc", "object": "Box"}` bzw.
  `{"document": "Doc"}`. Im typisierten Antwortfeld `references` kann ein
  fehlendes Objekt als `null` serialisiert sein. Zwei Dokumente duerfen denselben
  Objektnamen enthalten; der Dokumentname bestimmt die Aufloesung eindeutig.
- Referenzen sind aktuelle Namensabfragen, keine persistenten Identitaeten.
  Nach Schliessen/Loeschen und Wiederverwendung eines Namens ist eine neue
  Aufloesung notwendig. Keine Erkennung wiederverwendeter Namen zugesagt;
  Revisionsgepruefte Subelementauswahl ist additiv in Stufe 4 verfuegbar (unten).

## Antworten und Fehler

Die neuen Vertragstools haben ein MCP-`outputSchema` und liefern `structuredContent` sowie
denselben JSON-Inhalt als Text fuer Clients ohne strukturierte Ergebnisauswertung:

```json
{
  "contract_version": "1.0",
  "status": "success",
  "data": {"reference": {"document": "Doc"}, "label": "Doc", "type": "App::Document"},
  "references": [{"document": "Doc", "object": null}],
  "warnings": [],
  "error": null
}
```

Bei Domaenen-/Verbindungsfehlern: `status="error"` und
`error={code,message,cause,references,retryable,state,rollback_error}`.
`data=null` bei Ablehnung vor Ausfuehrung; Batchlaufzeitfehler liefern in `data`
zusaetzlich die Schrittstatus. Solche gueltigen
Vertragsantworten haben MCP-`isError=false`; Aufrufer muessen `status` pruefen.
Schemafehler (fehlende Pflichtfelder, falscher Typ, leere Referenz) werden vom
MCP-SDK vor dem RPC-Aufruf mit `isError=true` abgelehnt. Diese Protokollfehler
haben kein zugesagtes eigenes `ContractResponse`-Format.

| Code | Bedeutung |
| --- | --- |
| `invalid_arguments` | Ungueltige Argumente in der Bridge; MCP-Schemapruefung kann vorher ablehnen |
| `document_not_found` | Expliziter interner Dokumentname ist nicht geoeffnet |
| `object_not_found` | Objekt fehlt im expliziten Dokument |
| `rpc_not_allowed` | RPC-Modul-/Funktionsname vom Eingangsschutz abgelehnt |
| `execution_timeout` | GUI-Auftrag wartend verworfen oder bereits laufend; Ergebniszustand unbekannt |
| `operation_failed` | Sonstiger Bridgefehler; keine pauschale Rollbackzusage |
| `transaction_conflict` | Fremde ausstehende Dokument- oder Anwendungstransaktion; vor Mutation abgelehnt |
| `invalid_batch` | Batchstruktur, Typen, Grenzen, Operation oder Ergebnisreferenzen ungueltig |
| `dependency_conflict` | Batchloeschziel wird referenziert; keine implizite rekursive Loeschung |
| `transport_error` | Verbindungs-/XML-RPC-Fehler; keine automatische Wiederholung |
| `legacy_error` | Alte Bridge liefert nur Text; Ursache bzw. erforderliches Update aus Meldung ermitteln |

`retryable` ist konservativ `false`. `state="unchanged"` fuer explizite
Vorvalidierungsfehler, `rolled_back` nach erfolgreichem eigenen Abort, sonst
`unknown`. Ein Rollbackfehler steht in `rollback_error`. Insbesondere bedeutet
ein Timeout weder sicheren Abbruch noch sicheren Rollback. `warnings=[]` bei den
beiden lesenden Tools. Fehlerreferenzen werden auch im Antwortfeld wiederholt.

XML-RPC behaelt `{"result": ...}` bzw. `{"error": "Text"}`; strukturierte
Funktionsfehler ergaenzen `error_details`. Alte Clients koennen weiterhin den
Text lesen. Der neue Client wirft `FreeCADRemoteError`, eine Unterklasse von
`RuntimeError`, mit `.code` und `.details`; alte Bridges werden weiter gelesen.
GUI-Futures erhalten die urspruengliche Ausnahme statt eines Textwrappers.
Unklassifizierte Altoperationen erhalten nur allgemeine Codes, keine erfundene
dedizierte Geometrie-/Solverdiagnose. Raw-Python-/Status-Altpfade behalten ihr
bisheriges Fehlerformat.

## Einheiten und Koordinaten

Zielvertrag: Laenge mm, Flaeche mm^2, Volumen mm^3, Winkel Grad;
Modellkoordinaten dokumentglobal, Sketch-Geometrie im lokalen XY-System der
Skizze. Neue geometrische Werkzeuge muessen ihr Bezugssystem und ihre Einheiten
im jeweiligen Schema benennen. Die beiden neuen Abfragen enthalten keine
geometrischen Eingabeparameter und konvertieren keine Einheiten.

Bestandsparameter werden nicht still konvertiert. Insbesondere bleiben
`sketch_add_arc.start_angle/end_angle` und `sketch_add_ellipse.angle` in rad;
Sketch-Winkelconstraints bleiben Grad. Mesh-Winkelabweichung ist intern rad.
Placement/Move/Rotate arbeiten im Elternsystem (bei Objekten auf Dokumentebene
dokumentglobal), Sketch-Geometrie lokal XY. Die Registrierung versieht jeden
Altparameter mit Beschreibung und geometrische Groessen mit `x-unit` und
`x-coordinate-system`; Screenshot-Abmessungen sind px. JSON-Schemas behalten
Pflichtfelder, Typen und Defaults; optionales null ist explizit.
Geometrische Varianten werden weiterhin in ihren Fachstufen abgenommen.

## Transaktionen und Batch

`execute_batch(steps, atomic=true, preview=false)` akzeptiert 1..100 Schritte,
maximal 65536 UTF-8-Bytes fuer das JSON der Schritte. Nur diese Operationen:
`part_box`, `part_cylinder`, `part_sphere`, `part_cone`, `part_torus`,
`move_object`, `set_placement`, `boolean_cut`, `part_fillet`, `part_chamfer`,
`delete_object`. Die begrenzte Liste wird in Capabilities ausgegeben;
keine beliebigen RPC-Funktionen oder Python-Skriptsprache.

```json
{
  "steps": [
    {"id": "box", "operation": "part_box", "doc_name": "Doc",
     "arguments": {"length": 20, "width": 10, "height": 5}},
    {"id": "move", "operation": "move_object", "doc_name": "Doc",
     "arguments": {"obj_name": {"$ref": "box"}, "dx": 5}}
  ],
  "atomic": true,
  "preview": false
}
```

Jeder Schritt hat genau `id`, `operation`, `doc_name`, `arguments`.
IDs sind eindeutige ASCII-Identifier mit fuehrendem Buchstaben, maximal 64
Zeichen. Argumente sind die Parameter des jeweiligen Werkzeugs ohne doc_name;
keine stillen String-/Bool-zu-Zahl-Konvertierungen. Nichtendliche Zahlen,
negative/Null-Pflichtabmessungen und ungueltige Kantenselektoren werden abgelehnt.
Objektnamenargumente akzeptieren `{"$ref":"fruehere_id"}` und erhalten deren
Ergebnisfeld `name`. Nur rueckwaerts, nur dasselbe Dokument, kein Verweis auf
Loeschresultate; keine Pfadsprache, Forward-/Zyklusreferenzen oder Codeauswertung.

Der gesamte Auftrag wird vor Mutation strukturell validiert, einschliesslich
aller Dokumente und fremder ausstehender Transaktionen. Laufzeitfehler wie
nicht vorhandene Objekte, ungeeignete Topologie und Kernelversagen koennen erst
bei Ausfuehrung auftreten. Leere/ungueltige Partformen zaehlen als Fehler.

- `atomic=true`: genau ein bestehendes Dokument, eine eigene Transaktion und
  ein Undo-Eintrag. Fehler nimmt alle Schritte zurueck; fruehere Ergebnisse
  sind nicht weiterverwendbar. Sichtbarkeit wird innerhalb der eigenen
  Transaktionsgrenze wiederhergestellt, nicht durch neue Aenderungen nach Abort.
- `atomic=false`: mehrere explizite Dokumente erlaubt, Transaktion je Schritt;
  beim ersten Fehler stoppen. Fruehere Erfolge bleiben bestehen und sind je
  Dokument einzeln undo-faehig. Kein verteiltes Rollbackversprechen.
- Ergebnis `data.status`: `preview`, `succeeded`, `rolled_back`, `partial` oder
  `error`; je Schritt `planned`, `succeeded`, `failed`, `rolled_back`, `unknown`
  oder `not_executed`. Betroffene Referenzen und Fehler werden ausgegeben.
  Nach Rollback sind fruehere `data` und Ergebnisreferenzen entfernt.
- `preview=true`: gleiche Struktur-/Dokument-/Transaktionspruefung, geplante
  Auswirkungen und explizite Ziele, keine CAD-Operation, keine Temporaergeometrie.
  Keine geometrische Simulation, Erfolgsgarantie oder gespeicherte Bestaetigung.
  Ausfuehrung validiert neu; volle abhaengigkeitsbasierte Loeschvorschau folgt
  in Stufe 3. Batchloeschung lehnt referenzierte Ziele ab.
- Datei-I/O, Dokumenterzeugen/-schliessen/-wechsel, Undo/Redo, verschachtelte
  Batches und freie Codepfade sind in allen Batches ausgeschlossen.

Auch einzelne strukturierte Modelliermutationen verwenden eigene Transaktionen.
Eine fremde ausstehende Dokumenttransaktion wird nicht uebernommen, committed
oder abgebrochen; auch Undo/Redo/Save/Close werden dann abgelehnt. FreeCADs
`HasPendingTransaction` bezeichnet eine Transaktion mit ausstehenden Aenderungen;
ein blosses leeres `openTransaction` reserviert dort noch keinen solchen Status.
Interne Batch-Unteraufrufe teilen nur die explizit eigene Transaktion.
Ergebnisse werden vor Commit auf JSON-Serialisierbarkeit geprueft. Nach
Loesch-Rollback kann FreeCAD die interne Objektaufzaehlung anders ordnen;
Objektidentitaeten und Inhalt werden erhalten, eine Listenreihenfolge ist nicht
zugesagt. Referenzen duerfen nicht ueber Listenpositionen definiert werden.

Dateien sind eine getrennte Grenze: Alt-Save/Export behalten ihr bisheriges
Verhalten und koennen bestehende Ziele ueberschreiben; sie sind nicht durch
Dokument-Undo geschuetzt. Fuer bestehende Dateien ist ausserhalb dieser Alt-API
vorher explizite Zustimmung erforderlich. Die sicheren Datei-Workflows in den
folgenden Fachstufen muessen diese Migration umsetzen; kein atomarer Batch kann
diese Altpfade aufrufen. Import liest Dateien innerhalb einer Dokumentmutation,
rollt aber niemals die Quelldatei zurueck. Raw-Python bleibt ein eigener Altpfad.

## Migration und Grenzen

### Stufe 9: Native Assembly

Bridge-API **0.10.0**, **167 Tools**. Die acht additiven Werkzeuge
`assembly_create`, `assembly_add_component`, `assembly_set_grounded`,
`assembly_create_joint`, `assembly_set_joint`, `assembly_set_component_pose`,
`assembly_inspect` und `assembly_check_collisions` liefern `ContractResponse`.
Dokument-, Assembly-, Komponenten- und Gelenknamen sind explizit. Externe
Komponenten verlangen gespeicherte Quell- und Assembly-Dokumente; `App::Link`
erhaelt das Quellplacement mit `LinkTransform=true`. Die Quelldatei muss
separat gespeichert und verfuegbar bleiben.

Unterstuetzte native Gelenke sind Fixed, Revolute, Slider, Cylindrical und
Ball mit relativen DoF 0/1/1/2/3. Referenzen sind komponentenverwurzelte native
`PropertyXLinkSub`-Werte. Revolute/Cylindrical akzeptieren Winkelgrenzen in Grad,
Slider/Cylindrical Laengengrenzen in mm. Nicht mitgesendete Felder einer
partiellen Gelenkaenderung bleiben unveraendert. XYZ-Euler-Eingaben werden auf
FreeCADs Yaw(Z)-Pitch(Y)-Roll(X)-Konstruktor abgebildet.

`assembly_inspect` meldet exakte Gesamt-DoF nur fuer einen vollstaendig
verbundenen, azyklischen Baum unter genau einer GroundedJoint. Schleifen,
unverbundene Komponenten, mehrere Fixierungen und unbekannte Gelenktypen liefern
keine erfundene Zahl. Eine weitere Fixierung in einem bereits fixierten aktiven
Gelenkbaum wird als `assembly_unsolved` transaktional abgelehnt. Diskrete Posen
koennen mit `solve=true` nativ geloest oder mit `solve=false` exakt gesetzt
werden; letzteres meldet ausdruecklich, dass danach nicht geloest wurde und
begruendet keine dynamische Simulation.

Kollisionen werden paarweise am aktuellen diskreten Zustand aus BRep-Abstand
und positivem Schnittvolumen geprueft. Es gibt keine kontinuierliche
Bewegungs-, Fertigungs- oder Sicherheitszusage. FCStd erhaelt Links, Gelenke,
Limits und Placements bei verfuegbaren Quellen. STEP exportiert ausgewaehlte
Komponentensolids und meldet explizit den Verlust von Featurehistorie,
Constraints und Assembly-Gelenken.

### Stufe 8a: Auftraege und begrenzte Uebersichten

Bridge-API **0.9.0**, **159 Tools**. `start_batch_job` reiht ausschliesslich
den bestehenden strukturierten `execute_batch`-Vertrag ein und gibt sofort eine
prozesslokale UUID zurueck. `get_job` unterscheidet `queued`, `running`,
`succeeded`, `failed`, `cancelled` und `unknown`; Ergebnislesen ist idempotent
und fuehrt den Batch nicht erneut aus. Fortschritt ist `null`, solange FreeCAD
keinen belastbaren Wert liefert. Bis zu 256 Jobs werden gespeichert; bei voller
Belegung werden nur abgeschlossene Eintraege verdraengt.

`cancel_job` verhindert die Ausfuehrung eines noch wartenden GUI-Futures.
Bereits laufende GUI-/Kernelarbeit meldet `cancel_not_supported` und wird nicht
als abgebrochen ausgegeben. Nach Wiederverbindung mit demselben FreeCAD-Prozess
bleibt die UUID abfragbar. Eine unbekannte UUID, insbesondere nach Prozessverlust,
liefert `unknown` mit der Aufforderung, den Dokumentzustand vor einem neuen
Mutationsversuch zu inspizieren. Es gibt keine Jobpersistenz ueber Prozessneustart.

`list_objects_page` liefert fuer ein explizites Dokument `offset`, `limit`,
`total`, `has_more` und hoechstens 256 knappe Objekteintraege. Die Reihenfolge
ist keine persistente Identitaet. `capture_view` bleibt auf 64..2048 Pixel je
Achse und hoechstens 100 Hervorhebungen begrenzt. Der alte `get_status`- und
`list_objects`-Rueckgabevertrag bleibt aus Kompatibilitaetsgruenden bestehen.

8a ist implementiert und lokal sowie ueber echten MCP-Transport geprueft. Das
vollstaendige Stufe-8-Gate bleibt wegen der A1-A3-Gesamtworkflows und weiterer
kontrollierter Prozessverlust-/Timeout-Abnahmefaelle offen.

### Stufe 7: Part und Flaechen

Bridge-API **0.8.0**, **155 Tools**. N14 ergaenzt `part_wire`, `part_face`,
`part_shell`, `part_solid`, `part_extrude`, `part_revolve`, `part_loft` und
`part_sweep`. Wire-Kanten koennen revisionsgepruefte Stufe-4-Auswahlen sein;
ihre Reihenfolge ist verbindlich. Solid-Extrusion/-Revolution verlangt ein
geschlossenes planares Profil. Face normalisiert Lochorientierungen, akzeptiert
aber nur geschlossene, koplanare und innerhalb des Aussenwires liegende Loecher.
Shell wird nur bei tatsaechlicher Geschlossenheit zu genau einem Solid.

N15 ergaenzt `part_validate`, `part_section`, `part_split`, `part_offset_2d`,
`part_offset_shape`, `part_refine`, `part_sew` und `part_repair`. Split verlangt
genau einen Schneidkoerper oder eine Ebene aus globalem Punkt/Normalenvektor und
mindestens zwei Ergebnis-Solids. Offset-Join ist arc/tangent/intersection.
Validierung ist lesend; Refine, Sewing und Shape-Fix erzeugen neue Features mit
Vorher-/Nachherbericht. Sewing-/Reparaturtoleranz ist positiv und hoechstens
1 mm; nicht reparierbare Formen schlagen kontrolliert fehl. FreeCAD 1.1
`Shape.sewShape` verbindet exakt koinzidente Flaechen, schloss im verifizierten
Probeaufbau aber auch einen 0,005-mm-Spalt bei 0,01 mm Eingabetoleranz nicht.
Als enger deterministischer Fallback darf `part_sew` genau sechs planare,
nahezu rechteckige und achsparallele Flaechen zu einem Quader rekonstruieren:
jede Flaeche muss einer von zwei Stuetzeebenen pro Achse entsprechen und jede
Ecke innerhalb der Eingabetoleranz an den ermittelten Quadergrenzen liegen.
Die Antwort nennt `healing_mode=axis_aligned_planar_hexahedron`; sonst bleibt
`native_sewing`. Es gibt keine universelle Reparatur-, Fertigungs- oder
Festigkeitszusage.

Die neuen Part-Bildungs-, Offset- und Reparaturfeatures sind absichtlich
statische, nachvollziehbar mit `SourceNames` markierte Shape-Ableitungen; sie
recomputen bei spaeterer Quellaenderung nicht parametrisch. Bestehende native
Part-Boolesche und Part-Dress-ups bleiben parametrisch und liefern zusaetzlich
Eingabe-/Ausgabe-Qualitaetsdiagnose. Alle Mutationen laufen weiter im
GUI-Executor-Transaktionsrahmen; leere, ungueltige oder typwidrige Ergebnisse
werden vor Commit abgewiesen.

### Stufe 6: PartDesign

Bridge-API **0.7.0**, **139 Tools**. Neu sind `partdesign_datum`,
`partdesign_multi_transform` und `partdesign_edit_feature`; bestehende
PartDesign-Werkzeuge erhalten die in COVERAGE N10-N13 vereinbarten Varianten.
Datum-Supports, Up-to-face-Ziele und Pullrichtungen verwenden revisionsgepruefte
Stufe-4-Auswahlen und werden vor jeder Mutation aufgeloest.

Pad/Pocket unterstuetzen Mass, bis erste/bis Flaeche, Pocket durch alles sowie
reversed, symmetric und zwei Laengen. Revolution/Groove akzeptieren Origin-
oder Datumachsen und zwei Winkel. Pipe bleibt ein konstantes Profil, bietet
ausgewaehlte EdgeN-Pfade, Standard/Frenet und transformed/right/round. Hole,
Chamfer, Thickness, Draft und Pattern bilden die in N12/N13 aufgefuehrten
Optionen ab. MultiTransform ist eine geordnete Kette aus Linear, Polar und
Mirrored; Eingabelisten und unbekannte Schrittfelder werden vor RPC abgewiesen.

Featurebearbeitung ist absichtlich auf freigegebene Profile und Parameter
begrenzt, validiert die Ergebnisform und erhaelt den Body-Tip. Gewinde bleiben
native Hole-Metadaten ohne modellierte Helix; variable Mehrprofil-Pipes und
beliebige Propertybearbeitung sind nicht Teil dieses Vertrags. Exakte
Laufdaten und Artefakte stehen in [memory.md](../memory.md).

### Stufe 5: Sketcher

Bridge-API **0.6.0**, **136 Tools**, 19 neue Werkzeuge in
[sketcher_ops.py](../freecad_addon/freecad_ai_bridge/sketcher_ops.py).
`sketch_info` liefert Geometrien, Constraints, Construction, treibend/referenz,
aktiv/inaktiv, Freiheitsgrade sowie Konflikt-, Redundanz- und Teilredundanz-IDs.
Mutationen pruefen den Solver im selben GUI-Thread-Transaktionsrahmen; Fehler
rollen auf den exakten Vorzustand zurueck und nennen bekannte Constraint-IDs.

Neu sind Geometrie bewegen/Construction setzen/loeschen; Constraint-Wert und
-Modus setzen/loeschen; Linienlaenge, Punkt-Punkt-X/Y, Durchmesser,
Punkt-auf-Objekt und Linienwinkel zur Achse. Laengen sind mm, Winkelconstraints
Grad; bestehende Bogen-/Ellipsenwinkel bleiben Radiant. Geometriepunkte und
Zeichenoperationen verwenden Sketch-lokales XY.

Externe Geometrie akzeptiert genau eine revisionsgepruefte Kante aus demselben
Dokument; nach jeder Mutation muss die Auswahl neu abgefragt werden. Attachment
unterstuetzt `PartDesign::Plane` (`ObjectXY`) oder revisionsgepruefte planare
Flaechen (`FlatFace`) mit XYZ-Offset und X/Y/Z-Rotation sowie explizites Loesen.
Trim und Extend sind auf Linien/Kreisboegen begrenzt; FreeCAD 1.1 erlaubt beim
Trim kein `include_axes=true`. Fillet gilt fuer Linien/Kreisboegen. Copy/Clone
und Mirror akzeptieren hoechstens 100 eindeutige lokale Geometrieindizes; keine
beliebige Spline-Edit-Suite oder automatische Reparatur verlorener Supports.

Abnahme und exakte Laufdaten: [memory.md](../memory.md).

### Stufe 4: Auswahl, Messung und Bild

Bridge-API **0.5.0**, **116 Tools**, neun neue Werkzeuge in
[geometry_ops.py](../freecad_addon/freecad_ai_bridge/geometry_ops.py).
Testnachweise und Abnahmestand: [memory.md](../memory.md).

| Teil | Werkzeuge |
| --- | --- |
| 4a | `list_subelements`, `select_subelement`, `resolve_subelement` |
| 4b | `measure_distance`, `measure_angle`, `check_interference`, `highlight_subelements`, `get_view_state`, `capture_view` |

`list_subelements(doc_name,obj_name,kind,filters,...)`: `kind` face/edge/vertex,
AND-verknuepfte Filter geometry_type, position, bbox, normal, axis, radius,
area, length. Position ist geometrischer Schwerpunkt, bei Vertex der Punkt;
BBox verlangt vollstaendige Einbettung in min/max. Radius/Flaeche/Laenge sind
Intervalle mit min und/oder max. Globale Dokumentkoordinaten in mm, Flaeche
mm^2, Winkel Grad; verschachtelte Placements und App::Links beruecksichtigt.
Normalen sind orientiert und nur fuer planare Flaechen definiert; Achsen sind
unorientierte analytische Achsen bzw. Tangenten gerader Kanten. Nicht vorhandene
Merkmale sind null und passen nicht zu einem entsprechenden Filter.
Typen: plane/cylinder/cone/sphere/torus/bspline_surface, line/circle/ellipse/
bspline_curve/bezier_curve, vertex/other. Kein universeller Radius fuer freie
Kurven oder Ellipsen, keine einzelne konstante Normale fuer gekruemmte Flaechen.

Standardtoleranz 0.001 in mm bzw. mm^2 fuer Flaechenintervalle, Winkeltoleranz
0.001 Grad. Nichtendliche Werte, Nullrichtungsvektoren, ungueltige Intervalle
und unbekannte Filter werden abgewiesen. `limit` 1..256, `offset` >=0;
maximal 10000 Subelemente pro Abfrage, total zaehlt alle Treffer. Pagination
gilt nur innerhalb derselben Revision. `select_subelement` verlangt exakt
einen Treffer: `selection_empty` bzw. `selection_ambiguous`, keine Rangheuristik.
Fehlende/defekte Shape: `invalid_geometry`; Touched/Invalid: `geometry_not_ready`.
Abfragen recomputen nicht heimlich.

Jeder Treffer enthaelt `selection={document,object,revision,subelement}`.
Revision ist ein opaker, pro Sitzung/Dokument erzeugter Token samt Zaehler.
Native Objektanlage/-loeschung/-aenderung, Recompute, Undo/Redo invalidieren
konservativ die Auswahlen des gesamten Dokuments, auch bei gleicher Topologie
oder nach Undo zum gleichen geometrischen Zustand. Close/reopen und Wieder-
verwendung desselben Dokument-/Objektnamens geben alten Tokens keine neue
Gueltigkeit. Kein persistenter Topological-Naming-Vertrag und keine automatische
Neuzuordnung: nach `stale_selection` geometrisch neu abfragen. Ein fehlendes
Dokument bleibt `document_not_found`. Kamera und GUI-Markierung recomputen nicht.

Die sechs vorhandenen Dress-up-Tools Part-Fillet/-Chamfer und PartDesign-
Fillet/-Chamfer/-Thickness/-Draft akzeptieren in edges/faces zusaetzlich diese
Auswahlobjekte. Alle Tokens, Besitzer und Subelementtypen werden vor Anlage
eines Folgefeatures im selben GUI-Aufruf validiert. Fehler lassen keine
Teilfeatures zurueck. **Alte Strings/Part-Integer bleiben ohne Revisionsschutz**;
auch Draft plane_name und generische Property-LinkSubs sind weiterhin Altpfade.
Die elf Batchoperationen behalten ihre bisherigen Selektoren und Allowlist.

`measure_distance` akzeptiert ganze Objekte `{document,object}` im aktuellen
Zustand oder vollstaendige Subelementauswahlen. Beide Ziele muessen dasselbe
Dokument nutzen, sonst `coordinate_system_mismatch`; keine stillschweigende
Gleichsetzung verschiedener Dokumentkoordinatensysteme. Kernel-Minimalabstand
zwischen endlichen BReps, bis zu 32 naechste Punktpaare, Gesamtanzahl und
Trunkierungsflag. `measure_angle` verlangt gerade Kanten/planare Flaechen:
Linie-Linie, Ebene-Ebene und Linie-Ebene; kleinster unorientierter Winkel
0..90 Grad, keine Drehrichtung oder Reflexwinkel. Andere Typen werden mit
`unsupported_geometry` abgewiesen.

`check_interference` verlangt ganze Objekte mit geschlossenen Solids, keine
Flaechen-/Kantenauswahl oder gemischte Solid/Flaechenformen. Es liefert Abstand
und Schnittvolumen, nicht nur Boolean. Standard: V > 1e-6 mm^3 ist Interferenz;
sonst Abstand <= 0.001 mm Kontakt, sonst getrennt. Beide Toleranzen explizit
aenderbar und im Ergebnis enthalten; `within_contact_tolerance` unabhaengig
vom Interferenzflag. Nur statischer diskreter Zustand, keine kontinuierliche
Kollisions-, Fertigungs- oder Festigkeitszusage. Altes `measure` bleibt erhalten.

`highlight_subelements` validiert 0..100 eindeutige Tokens vor dem Ersetzen
der Zielauswahl; leere Liste loescht nur die Auswahl dieses Dokuments. Keine
implizite Sichtbarkeitsaenderung, kein Dokument-Undo. Ungueltige Auswahl behaelt
vorherige Markierungen. `get_view_state` liest Kameraquaternion, Auswahl und
bis zu 256 explizite Objekte mit Visibility/ShapeColor/Transparency. Native
ShapeColor kann RGBA liefern; fuer set_color die ersten drei Kanaele verwenden.
Darstellung mit bestehenden Settern wiederherstellen. RGB verlangt endliche
Werte 0..1; Transparency bleibt auf 0..100 geklemmt und gibt nun den tatsaechlich
gesetzten Wert zurueck. Dies korrigiert die alte Antwort bei Grenzwerten.

`capture_view` adressiert ein Dokument unabhaengig vom aktiven Dokument,
64..2048 Pixel je Achse und sieben Presets isometric/front/back/top/bottom/
left/right. Fit aller sichtbaren Objekte, kein Recompute; vorher bei Bedarf
`recompute_document`. selections=null erhaelt Markierung, [] leert sie,
sonst validierte neue Markierung. Native Kamerapresets koennen Auswahl leeren;
die Bridge stellt sie vor dem Rendern dokumentuebergreifend wieder her.
Fuer zuverlaessiges Rendern wird das Zieldokument temporaer aktiviert; danach
werden vorheriges aktives Dokument und Auswahl wiederhergestellt. Kameraanimation
wird fuer die Aufnahme deaktiviert und danach zurueckgesetzt, damit PNG und
ausgegebenes Kameraquaternion den Sollwinkel statt einen Zwischenstand zeigen.
Kamera des anderen Dokuments bleibt erhalten. Native saveImage-Ausgaben koennen
GUI-Auswahlhervorhebungen ausblenden; Markierungszustand separat mit
get_view_state pruefen, keine farbige PNG-Hervorhebung zugesagt.
Antwort: ContractResponse als **JSON-Text plus nativer MCP-PNG-Inhalt**, kein
automatisches outputSchema fuer die gemischte Inhaltsliste. Fehler liefern nur
den JSON-Vertragstext. Alte screenshot/set_view/fit_view-Signaturen unveraendert;
deren Recompute-/Aktivdokumentverhalten gilt nicht fuer capture_view.

### Stufe 3: Dokumente und Parameter

Bridge-API **0.4.0**, insgesamt **107 Tools**. Die 22 neuen Tools benutzen
`ContractResponse`, explizite `doc_name`/interne Objektnamen und den GUI-Executor.
Sie erweitern nicht die elf Batchoperationen. Neue Modellmutationen erhalten
eine eigene Transaktion, Recompute und Pruefung auf `Invalid`-Objektzustaende
vor Commit. Fehler rollen eigene Aenderungen zurueck; eine bereits defekte
Dokumentstruktur kann weitere Aenderungen konservativ verhindern.

| Bereich | Neue Tools |
| --- | --- |
| Dokument | `inspect_document`, `activate_document`, `recompute_document`, `save_document_safe`, `close_document_safe` |
| Container | `create_container`, `set_container_members`, `set_body_tip` |
| Properties | `get_properties`, `set_properties` |
| Parameter | `get_expressions`, `set_expression`, `create_spreadsheet`, `read_spreadsheet`, `set_spreadsheet_cells`, `set_spreadsheet_alias` |
| Struktur | `rename_object`, `copy_object`, `create_link`, `get_dependencies`, `preview_delete`, `delete_objects` |

`inspect_document` liest Datei, GUI-Modified, Aktivzustand, Pending-Transaktion,
Objektzustaende, Mitglieder und Tips ohne Recompute. Aktivieren ist nicht undo-bar.
Gruppen/Body-Mitglieder werden als vollstaendige geordnete Namensliste ersetzt
(max. 100, keine Duplikate/Zyklen); leere Liste gruppiert aus. Bodies akzeptieren
Sketcher-Skizzen und PartDesign-Features; keine implizite Uebernahme aus anderem
Body. Vor Entfernen des Tips diesen umsetzen oder mit null leeren. Ein neuer
Tip muss PartDesign-Feature desselben Bodys sein. `rename_object` aendert nur
Label, nie Name (max. 256 Zeichen).

`get_properties` liest maximal 256 ausgewaehlte Properties mit Typ, nativen
Statusnamen, Schreibbarkeit, Einheit, Enum-Auswahl und Wert. Unbekannte Typen
liefern `supported=false`, `writable=false`, `value=null`, keinen Stringersatz.
Freigegebene native Typnamen stehen in Capabilities: Bool/Integer/Float/String,
Enumeration, Integer-/FloatConstraint, Quantity und Laenge/Abstand/Winkel/
Flaeche/Volumen/Geschwindigkeit/Beschleunigung/Druck/Kraft, Vector, Placement,
Link/LinkSub sowie native Bool-/Integer-/Float-/String-/Vector-/Placement-/
Link-/LinkSub-Listen. Keine beliebigen dynamischen Properties oder Methoden.

`set_properties` akzeptiert 1..100 Werte, Listen jeweils max. 256 Eintraege:

- Skalare behalten ihre JSON-Typen; Bool ist keine Zahl, NaN/Infinity unzulaessig.
- Quantity: `{"value":2,"unit":"cm"}`; native Einheitenumrechnung, Ausgabe
  `{"value":20,"unit":"mm"}`. Zusammengesetzte Basiseinheiten z.B. `mm*s^-2`.
- Vector: `[x,y,z]` in mm; Placement: `{"position":[x,y,z],"quaternion":[x,y,z,w]}`
  im Elternsystem, normiertes Quaternion. Listen enthalten dieselben Strukturen.
- Link: `{"document":"Doc","object":"Box"}` oder null. LinkSub:
  `{"reference":{"document":"Doc","object":"Box"},"subelements":["Face1"]}`
  oder null. Property-Links sind gleichdokumentig, existent und zyklusfrei.
  Subelemente werden aktuell aufgeloest, sind noch keine revisionsfesten Referenzen.
- Read-only/Immutable, native Constraint-Clamping, ungueltige Enums/Einheiten,
  ungueltige Referenzen und expression-getriebene Direktzuweisungen werden
  abgewiesen. Group/Tip/Origin/ExpressionEngine/Label/LinkedObject sind verwaltet;
  dafuer die dedizierten Tools verwenden. Schreibbarkeitsmetadaten beziehen
  sich auf Property-Status/Typ; bestehende Expressions separat abfragen.

Expressions verwenden native arithmetische Formeln, Einheiten und gleichdokumentige
Objekt-/Zell-/Aliasreferenzen, `+ - * / ^` und Klammern. Keine Funktionsaufrufe,
Makros, Python oder dokumentuebergreifenden Formeln. Propertypfade unterstuetzen
Komponenten und Indizes, z.B. `Placement.Base.x`, `Constraints[0]`; native
Zielkompatibilitaet wird beim Setzen geprueft. null entfernt die Expression.
Ungueltige Referenzen, Zyklen und Recompute-Fehler fuehren zu Rollback.

Spreadsheet: Zellen A1..ZZ99999, Bereiche max. 256 Zellen, Inhalte max. 4096
Zeichen. `read_spreadsheet` liefert Inhalt, ausgewerteten Skalar/Quantity und
Alias. `set_spreadsheet_cells` setzt eine Map aus Zelle zu Rohtext; fuehrendes
`=` ist Formel, null leert. Aliase sind native eindeutige Identifier; null
entfernt sie. Native reservierte Namen wie `W` werden abgewiesen. Benutzer
bestaetigte am 2026-09-16 fuer A1 `LengthParam/WidthParam/HeightParam/WallParam`
anstelle `L/W/H/t`; Geometrie und Sollwerte unveraendert.

Kopien verwenden rekursives natives Kopieren im selben Dokument, einschliesslich
referenzierter Parametertabellen. Verbleibende Quellenreferenzen verursachen
Rollback, keine angeblich unabhaengige Kopie. App::Link selbst wird nicht als
unabhaengige Kopie akzeptiert; seine Quelle kopieren. Links sind lokal oder
extern; fuer externe Links muessen **beide Dokumente vorher gespeichert** sein.
Quelldateien separat speichern/erhalten, betroffene externe Dokumente explizit
recomputen. Kein verteilter Undo-/Rollbackvertrag. Assembly-Gelenke folgen spaeter.

`get_dependencies` liefert OutList/InList und transitive Folgeobjekte.
`preview_delete` erweitert Wurzelobjekte um Abhaengige und Containerbesitz
(Mitglieder/Origin/OriginFeatures). Die Vorschau aendert nichts und simuliert
keine Geometrie. `delete_objects` verlangt exakt diese aktuelle vollstaendige
Menge als `confirmed_objects`; geaenderte Menge oder externe Abhaengige fuehren
zur Ablehnung. Native Nebenloeschungen werden vor Commit gegen die Menge geprueft.
**Migration:** Das alte `delete_object` behaelt Signatur/Ergebnis, lehnt jetzt
aber referenzierte Ziele oder Ziele mit eigenen Unterobjekten ab. Fuer diese
Faelle Vorschau plus bestaetigte Mengenloeschung verwenden.

Sichere Dateien: `save_document_safe` verlangt absoluten .FCStd-Pfad bzw.
bereits gespeichertes Dokument. Jede existierende Datei, auch beim normalen
Save, verlangt `overwrite=true`. Verzeichnisziele, fehlende Elternverzeichnisse
und von anderem offenen Dokument belegte Pfade werden abgewiesen. Nach Erfolg
wird GUI-Modified zurueckgesetzt. Bei Schreibfehler: `file_write_failed`,
`state=unknown`, moeglicher Artefaktpfad in Meldung; **kein Datei-Rollback**.
`close_document_safe` verweigert ungespeicherte Aenderungen ohne
`discard_changes=true` und verweigert offene externe Abhaengige auch mit Discard.
Fremde Pending-Transaktionen bleiben geschuetzt. Alte Save/Close behalten ihre
Signaturen und ihr ungeschuetztes Altverhalten; neue Workflows migrieren auf
die `_safe`-Tools. Strukturierter Exportschutz ist in Stufe 11 ueber exchange_export implementiert; Legacy-Exports bleiben unveraendert.

Neue Fehlercodes: `recompute_failed`, `file_exists`, `file_write_failed`,
`unsaved_changes`, `property_not_found`, `property_read_only`,
`unsupported_property`, `invalid_enum`, `invalid_unit`, `invalid_reference`,
`expression_driven`, `invalid_expression`, `invalid_alias`, `dependency_cycle`,
`confirmation_required`; bestehende Referenz-/Transaktionsfehler bleiben.

Installation: Das neue `document_ops.py` zusammen mit allen Bridge-Dateien
aktualisieren und MCP-Server neu starten; keine automatische Aenderung der
Benutzersitzung. Workspace-Abnahme: `tests/mcp_smoke.py --stage3-only`, zwei
unabhaengige Laeufe mit JSON-Transkripten/FCStd/STEP/STL im ausgegebenen TEMP-Pfad.
Parameterteil von A1 verwendet hier Part-Box/Cut; vollstaendig bestimmte
Sketcher-/PartDesign-Referenzaufgabe bleibt Stufen 5/6/8 vorbehalten.

### Historische Migration Stufe 2

82 Altwerkzeuge behalten Namen, Signaturen, optionale Dokumentdefaults und
Ergebnisformen; dazu kommen drei Tools (85 insgesamt). Bestehende Aufrufer
muessen sich fuer die Migration nicht gleichzeitig umstellen. Neue Workflows
uebergeben explizite Dokumentnamen und benutzen zurueckgegebene interne Namen.
Neue Vertragsantworten gelten fuer die drei neuen Tools; Alttools behalten
ihre Text-/Bildantworten. Additive Bridgefehler sind in beiden Pfaden gleich
klassifiziert, der alte MCP-Textpfad bleibt absichtlich kompatibel.

Bridge-API `0.3.0` bezeichnet dieses Protokoll, nicht die Distributionsversion
des MCP-Servers (aktuell `0.1.0`). Host-Paketversion und Bridge-API werden separat
ausgewiesen. MCP-SDK mindestens `1.27.1` fuer die hier geprueften strukturierten
Antworten; nach Update Abhaengigkeiten mit `pip install -e .` aktualisieren.
Addon-Dateien inklusive `contracts.py`, `batch.py`, `transactions.py` muessen gemeinsam aktualisiert
und geladen werden; danach MCP-Server neu starten, damit die Toolliste erneuert
wird. Eine alte Bridge bleibt fuer alte Tools nutzbar, bietet aber die neuen
Operationen nicht. Kein automatisches Installieren/Reload/Neustarten der
Benutzersitzung. Workspace-Testinstanz: [start_bridge.FCMacro](../tests/start_bridge.FCMacro).

Capabilities melden `atomic_batch`, `multi_document_batch`,
`mutation_preview` und `consistent_transactions` fuer den beschriebenen
Umfang als `true`. Die Variantenliste bezeichnet implementierte Bridge-Optionen,
keine pauschale native API-Garantie fuer andere FreeCAD-Versionen.
`raw_python_enabled=true` beschreibt ehrlich den noch vorhandenen Altpfad;
Normalmodusumstellung bleibt Stufe 12. FEM, CAM und BIM werden nicht aktiviert.

Pruefkriterien: [ACCEPTANCE.md](ACCEPTANCE.md). Aktueller Abnahmestatus und
reproduzierbare Testbefehle stehen in [memory.md](../memory.md).
