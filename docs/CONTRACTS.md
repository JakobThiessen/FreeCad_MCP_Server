# MCP-Vertrag 1.0: Stufen 2 bis 4

Stand: 2026-09-16. Implementierte Stufen 2 bis 4 aus [agent.md](../agent.md).
Teststand und offene Gates: [memory.md](../memory.md).
Dieser additive Vertrag umfasst Schemas, Referenzen, Transaktionsbesitz,
Vorschau und begrenzte Batchausfuehrung. Die Alt-API bleibt dokumentiert.

## Werkzeuge und Referenzen

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
| `transaction_conflict` | Fremde ausstehende Dokumenttransaktion; vor Mutation abgelehnt |
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
die `_safe`-Tools. Exportschutz bleibt Aufgabe von Stufe 11.

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
