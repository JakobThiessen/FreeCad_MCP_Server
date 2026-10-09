# MCP-Server: Stufe 11 auf FreeCAD 1.1.1 geprueft

## Teilstufen 11b/11c

Stand 2026-10-09: **194 Tools**, Bridge 0.11.0/Paket 0.1.0 unveraendert.
Fuenf Mesh-Werkzeuge fuer Diagnose, begrenzte Reparatur und statische
Shape/Mesh/Solid-Konvertierung; zwei strukturierte Austauschwerkzeuge fuer
STEP AP214/AP242, ASCII/binaer-STL, OBJ und planares DXF/SVG.
54 Hosttests (3,051 s), 59 native Regressionen (27,033 s), frische reine
GUI 1.1.1 Build 20260414 und zweimal 142 echte MCP-Fachaufrufe plus je elf
Cleanup-Aufrufe bestanden, Exitcode 0 und Raw-Python aus. Reparatur/Normalen,
ganze fehlende Wand, Grenzen/Rollback, absolute Triangulation, STEP-Farben/
Labels/Linkstruktur, globale Lage und FCStd-Reopen/zweiter Edit/Reexport geprueft.
Kein Schema-Downgrade. Statische Ergebnisse und ausdrueckliche Verlustwarnungen;
uniforme geerbte RGB/einfache Hierarchie nachgewiesen, keine allgemeine
Heilung, per-Face-/Link-Farbpaletten oder andere Patchversionen zugesagt.
Eigene letzte native PID 16980 erst nach leerem Bestand beendet; danach keine
FreeCAD-Prozesse und kein Listener 9945. Standardinstallation/Benutzerdateien
unveraendert, kein Commit/Push/Tag, kein Start 12/CAM/BIM/FEM.
Nachweise `%TEMP%/freecad-stage11bc-mcp-iyc0kc7w/report.json` und genaue
Uebergabe in [memory.md](memory.md).

## Historisch: Teilstufe 11a

Stand 2026-10-09: **187 Tools**, Bridge 0.11.0/Paket 0.1.0 unveraendert.
Fuenf strukturierte native Draft-Werkzeuge fuer acht Elementvarianten und
parametrische XYZ-/Polararrays mit Bearbeitung/Inspektion. Geprueft auf eigener
FreeCAD **1.1.1 Build 20260414**: 52 Hosttests (2,977 s), 55 native Tests
(22,974 s), frische reine GUI und zweimal 182 echte MCP-Workflow-Aufrufe.
Raw-Python deaktiviert; analytische Masse/Placement, Undo/Redo, Fehlerrollback,
Quellenpropagation/-verlust, Isolation und FCStd-Reopen/zweite Aenderung bestanden.
Quellsichtbarkeit erhalten, native optimale BBox fuer rotierte Kreise.

**Keine Vollabnahme Stufe 11:** 11b Mesh und 11c erweiterter Austausch bleiben
offen, einschliesslich aller vereinbarten Reparaturen, AP214/AP242, Farben/
Struktur, ASCII/binaer-STL, OBJ-Import und planarem DXF/SVG. Draft-Capability
nur auf GUI 1.1.1; 1.1.4 fuer 11a ungeprueft. Names statt UUIDs, kein freier
Code/Befehlsersatz. Keine Installation, Commit/Push/Tag oder Stufe 12/CAM/BIM/FEM.
Eigene letzte GUI PID 30616 erst nach bestaetigt leerem Dokumentbestand beendet;
danach keine FreeCAD-Prozesse und kein Listener 9944. TEMP-Artefakte erhalten:
`%TEMP%/freecad-stage11a-mcp-qwdw1ihe/report.json`.
Vertraege, genaue Tests und naechster Einstieg: [memory.md](memory.md).

## Historisch: Stufe 10b auf 1.1.1 Abgenommen

Stand 2026-10-09: **182 Tools**, Bridge 0.11.0/Paket 0.1.0 unveraendert.
Frische Abnahme auf installierter FreeCAD **1.1.1 Build 20260414** mit eigener
TEMP-Konfiguration: 51 Hosttests (3,255 s), 52 native Tests (23,476 s), dann
neue GUI ohne Testvorlauf und zweimal 125 A5-MCP-Aufrufe mit Raw-Python false.
Voller A2/A5-Workflow mit nativen Massen, Schnitt/Detail, Bearbeiten, Undo/Redo,
FCStd-Reopen, Referenz-/Rollback-/Fremdbesitz-/Overwrite-Schutz bestanden.
PDF/SVG numerisch geprueft und alle vier finalen PNGs visuell kontrolliert.
10a-MCP-Exportregression zweimal 46 Aufrufe mit Renderern bestanden.
`techdraw_drawings=true` jetzt genau fuer 1.1.1 und 1.1.4 mit GUI; keine Zusage
fuer andere Patchversionen. Keine Geometrieaenderung fuer 1.1.1 erforderlich.
Neue Nachweise: `%TEMP%/freecad-stage10b-mcp-ymvmje2o/`,
`%TEMP%/freecad-stage10a-mcp-saoppng1/` und
`%TEMP%/freecad-stage10b-111-native-937416af052f44ea848312f8307d92ad/full.json`.
Eigene Dokumente geschlossen, eigene Prozesse beendet; 0 Listener auf 9943.
Keine Standardinstallation, Benutzerdateien oder bestehenden Aenderungen
ueberschrieben; kein Commit/Push/Tag. Stufen 11/12 weiterhin offen.
Grenzen/Vertraege und genaue Laufzeitdaten: [Uebergabe](memory.md).

## Historisch: Stufe 10 unter 1.1.4 Abgenommen

Stand 2026-10-09: **182 Tools**, Bridge 0.11.0/Paket 0.1.0 unveraendert,
unveroeffentlichter Arbeitsbaum. N19/10b und volle A5-Zeichnung auf A2 sind unter
FreeCAD **1.1.4 Build 20260928** abgenommen: 51 Hosttests, 52 native Tests
(66,479 s), frische Normalmodus-GUI mit zweimal 125 MCP-Aufrufen inkl. festen
PDF-/SVG-Rendergates; 10a-Regressionsdoppelrun je 46 Aufrufe. Projektionsgruppe,
axialer Schnitt, Detail, sechs native Masse, Radius/Winkel, Annotation/Leader,
48->58 mit Undo/Redo, FCStd-Reopen und danach 9/59 bestanden. Referenzverlust/
Umordnung, Negativrollback, Fremdbesitz und Dateiueberschreibschutz geprueft.
Beide Exporte: eine A4-Seite, richtige Konturgroessen, visuell lesbare Pflicht-
angaben ohne gefundene Abschneidung/Textueberlagerung im Abnahmeblatt.
`techdraw_drawings=true` nur auf gepruefter GUI-Patchversion 1.1.4, Raw-Python
false. Keine neue 1.1.1-10b-Abnahme, universelle Topologie-/Blattqualitaets- oder
Fertigungszusage. Artefakte `%TEMP%/freecad-stage10b-native-full.json`,
`%TEMP%/freecad-stage10b-mcp-27zfa7ex/{report.json,1/,2/}` und
`%TEMP%/freecad-stage10a-mcp-mz6fqlyb/`; TEMP ist kein dauerhaftes Releasearchiv.
Kein Commit/Push/Tag, Installationsupdate oder Eingriff in Benutzerdateien.
Stufen 11/12 **nicht gestartet**. [Vertrag](docs/CONTRACTS.md),
[Matrix](docs/COVERAGE.md), [Abnahme](docs/ACCEPTANCE.md), [Uebergabe](memory.md).

## Historischer Teilstand Stufe 10a

Stand 2026-10-09: **175 Tools**, Bridge-API weiterhin **0.11.0**, unveroeffentlichter
Arbeitsbaum. Sieben strukturierte Tools fuer native TechDraw-Seiten/Templates,
Einzelansichten, Inspektion, Update, Layout/Schriftfeld und PDF/SVG-Ausgabe.
`techdraw_pages` meldet geprueften Teilumfang 10a unter 1.1.4, `techdraw_drawings=false`.
Keine Stufe-10-/A5-Abnahme, kein Start Stufe 11/12.

Frischer Nachweis: 50 lokale Tests bestanden (2,657 s); alle 48 nativen
Regressionen bestanden (19,651 s) unter eigener FreeCAD 1.1.4 Build 20260928,
Python 3.11.14. Host .venv: Python 3.10.11/MCP 1.27.1. Der native Bericht
erfasst geladene Workspace-Modulpfade/SHA256 vor der abschliessenden reinen
Capability-/Warntextkorrektur. Der finale MCP-Lauf startet danach frisch.
Kein `execute_python` als CAD-Ausweg; Normalmodus meldet Raw-Python deaktiviert.

**10a-Gates bestanden:** Zwei vollstaendige unabhaengige MCP-Laeufe mit je
46 Aufrufen, einschliesslich Quellen-/Layout-Undo/Redo, FCStd-Save/Reopen,
zweitem Quellenedit, Referenzverlust/Undo, Negativrollback und Overwrite-Schutz.
Beide PDF-/SVG-Ausgaben gerendert und visuell kontrolliert: eine A4-Querformat-
PDF-Seite, Titelblock und drei getrennte Ansichten; Papier, Konturmassstab und
Lage numerisch mit Raster-/Rundungstoleranz geprueft. PyMuPDF 1.28.2 ist nur eine
lokale optionale Testvoraussetzung fuer `--stage10a-render`, keine Serverabhaengigkeit.
Der Fix schliesst exakt die eigene globale ID nach leeren Updates; fremde
Transaktionen bleiben unangetastet. Positionen werden nach `addView` gesetzt.

Artefakte: `%TEMP%/freecad-stage10a-native-bf2a55bbe7fd49efa1652bf2cbb52227.json`
und `%TEMP%/freecad-stage10a-mcp-eqzyan01/{report.json,1/,2/}` mit FCStd,
PDF/SVG, PNG-Renderbildern, numerischen Exportpruefungen und MCP-Transkripten.
Die Standardinstallation blieb unangetastet; keine Benutzer-FreeCAD-Sitzung
neu gestartet und keine Benutzerdateien geaendert. Kein Commit, Push oder Tag.

Naechster Einstieg: 10b Schnitt/Detail/Projektionsgruppen/modellgebundene
Masse/Annotationen und vollstaendiges A5. Vertraege und Matrix:
[docs/CONTRACTS.md](docs/CONTRACTS.md), [docs/COVERAGE.md](docs/COVERAGE.md),
[docs/ACCEPTANCE.md](docs/ACCEPTANCE.md), genaue Uebergabe [memory.md](memory.md).

## Historischer Versionsaudit

Auditstand vor Stufe 10a: 2026-10-09. Workspace-Bridge **0.11.0**, MCP-Vertrag **1.0**,
**168 registrierte Werkzeuge**. Auftrag: Serverbestand pruefen, begrenzte
Verbesserungen implementieren, Versionskompatibilitaet und offene Arbeit dokumentieren.

## Ergebnis und Grenzen

Die vorhandenen strukturierten Operationen haben MCP-Wrapper; AST-, Schema-,
Argumentweiterleitungs- und Registrierungstests bestehen. Native Regressionen
und echte MCP-Workflows bestehen unter FreeCAD 1.1.4. Die finalen nativen Tests
und der Normalmodus-Audit bestehen ebenfalls unter 1.1.1.

**Nicht alle FreeCAD-Funktionen sind implementiert.** Vollstaendige TechDraw-
Zeichnungen, Draft-Modellierung und erweiterte Mesh-Bearbeitung fehlen weiterhin.
Dieser Audit ist keine Gesamtabnahme der Roadmap und kein Beweis jeder moeglichen
Geometrie-/Parameterkombination aller 168 Tools. Die bisherigen Stufenabnahmen
und ihre Grenzen bleiben bestehen, siehe [docs/COVERAGE.md](docs/COVERAGE.md).
FEM bleibt ausgeschlossen; CAM und BIM sind nicht aktiviert.

## Implementierte Verbesserungen

### Vollstaendige Patchversion

[rpc_server.py](freecad_addon/freecad_ai_bridge/rpc_server.py) meldet ueber
`get_version` nun `major.minor.patch`, beispielsweise `1.1.4`, statt nur `1.1`.
`get_capabilities` behaelt alle vorhandenen Buildfelder. Regressionstest fuer
1.1.1 und 1.1.4 sowie echte RPC-Vergleiche mit den Capabilities bestehen.

### Normalmodus statt freier Codeausfuehrung

- XML-RPC `execute` und MCP `execute_python` sind standardmaessig gesperrt.
  Ablehnung: `raw_python_disabled`, vor GUI-Queue-Einreichung.
- Ausschliesslich `FREECAD_MCP_ALLOW_RAW_PYTHON=1` in der FreeCAD-Prozessumgebung
  aktiviert den Entwicklermodus. Fehlende Variable, `0`, `true` und `yes`
  aktivieren ihn nicht. Das MCP-Tool bleibt fuer API-Kompatibilitaet registriert.
- Capabilities melden den tatsaechlichen Zustand; Normalmodus und Entwickler-
  Opt-in sind explizit beschrieben. Der Entwicklermodus ist **keine Sandbox**.
- Indirekte RPC-Aufrufe bleiben auf oeffentliche, lokal definierte Operationen
  erlaubter Module beschraenkt. Private, importierte und fremde Ziele sind gesperrt.
  `resolve_function` liefert jetzt auch fuer importierte Ziele stabil
  `rpc_not_allowed` statt des unspezifischen `invalid_arguments`.
- Loopback ohne Authentifizierung bleibt die Vertrauensgrenze. Lokale Clients,
  Dateipfade, FCStd-Dateien und explizit aktivierter Entwicklercode muessen
  vertrauenswuerdig sein; keine Zusage eines sicheren Multiuser-Dienstes.

Implementierung in [security.py](freecad_addon/freecad_ai_bridge/security.py)
und [rpc_server.py](freecad_addon/freecad_ai_bridge/rpc_server.py).
Unit-Tests pruefen auch den Entwickler-Opt-in und den erhaltenen Textfilter.
Live-Audits pruefen direkte RPC-Codeausfuehrung, private/importierte RPC-Ziele
und MCP-Codeausfuehrung im Normalmodus auf beiden Laufzeiten.

### Jobkapazitaet vor Ausfuehrung

`start_job` prueft freie Registerkapazitaet jetzt unter dem Job-Lock, bevor
ein Future eingereicht wird. Zuvor konnte ein bereits gestarteter Auftrag bei
voller Kapazitaet abgelehnt werden, ohne dass seine ID im Register verblieb.
Abgelehnte Jobs mit `job_capacity` werden jetzt nicht eingereiht. Der gezielte
Test prueft ausbleibendes `submit_function` und unveraenderte Queue-Laenge.
Die Grenze von 256, Idempotenz und queued-only Cancellation bleiben unveraendert.
Das Register ist weiterhin prozesslokal; laufende CAD-Berechnungen sind nicht
zuverlaessig abbrechbar. Kein neuer Crash-/Lasttest mit 256 nativen Jobs erfolgt.

### Native TechDraw-Flaechenrandbereinigung

Neues strukturiertes Werkzeug `techdraw_scrub_edges` nutzt die in 1.1.4
exponierte Python-API `TechDraw.scrubEdges` direkt, ohne Ersatzgeometrie oder
`execute_python`-Fallback. Implementierung in
[part_ops.py](freecad_addon/freecad_ai_bridge/part_ops.py) und
[server.py](src/freecad_mcp/server.py).

- Explizites Dokument, 1..256 revisionsgepruefte Kanten aus demselben Dokument;
  veraltete oder dokumentfremde Auswahlen werden abgelehnt.
- Dokumentglobale Transformation ueber den vorhandenen Auswahlpfad.
- Jede Kante wird vor dem nativen Aufruf kopiert: FreeCADs Implementierung
  darf interne Shapes/Toleranzen veraendern. Quellen bleiben unveraendert.
- Ergebnis: unabhaengiger statischer Part-Compound mit Referenz, Input-/Output-
  Kantenzahl und SourceNames. Keine parametrische Abhaengigkeit und keine
  automatische Ausblendung der Quellen. Undo/Redo und eigener Rollback gelten.
- Ohne native API: `unsupported_feature`, ohne leeres Ergebnisobjekt.
  Ein natives leeres Ergebnis liefert `operation_failed`.
- **Wichtige native Grenze:** Die Funktion bereitet Flaechenraender vor und
  entfernt offene/lose Endstuecke. Sie ist keine geometrische Vereinigung.
  Das MCP-Schema und erfolgreiche Antworten mit `warnings` sagen dies explizit.

Live belegt: geschlossener Rechteckrand mit einer duplizierten Kante liefert
vier Kanten; zwei offene Linien 0..10 und 5..15 mm liefern nur das gemeinsame
5-mm-Segment. Eine duplizierte geschlossene Kreislinie bleibt einmal erhalten.
Die anfangs angenommene Ausgabe von drei Segmenten/15 mm war falsch. Diese
Annahme wurde durch native Tests widerlegt und nicht als Erfolg dokumentiert.
Der offizielle Python-Docstring alleine beschreibt die Endstueck-Pruning-Grenze
nicht; die C++-Implementierung `pruneUnconnected` und die Laufzeit tun es.

Das war **kein TechDraw-Zeichnungsworkflow**. Zum Auditabschluss waren Seiten,
Templates, Ansichten, Schnitte, Details, Masse und PDF/SVG TODO; der aktuelle
experimentelle 10a-Teilstand oben ersetzt nicht die weiterhin offene A5-Abnahme.

### Wahrheitsgemaesse Capabilities und Testharness

- `techdraw_scrub_edges` wird anhand der vorhandenen nativen API erkannt.
  `techdraw_drawings`, `draft_modeling`, `mesh_editing` sind explizit `false`.
- [tests/start_bridge.FCMacro](tests/start_bridge.FCMacro) stoppt die Bridge
  innerhalb der eigenen Testinstanz und entfernt deren geladene Python-Module,
  bevor es das Workspace-Paket neu importiert. Dadurch kann ein installiertes
  altes `contracts.py` nicht weiter die Bridge-Version 0.10.0 liefern.
  Keine Aenderung der installierten Add-on-Dateien oder fremder Prozesse.
- [tests/mcp_smoke.py](tests/mcp_smoke.py) ergaenzt `--audit-only` und prueft
  im Bestands-Smoke die Normalmodus-Ablehnung statt freie Codeausfuehrung.
  Der interne native Harness braucht keinen oeffentlichen Python-Opt-in.
- README, Vertragsdokument und Abdeckungsmatrix sind auf diese Migration und
  Grenzen aktualisiert. Bridge-Version 0.11.0 ist nicht die Paketversion 0.1.0.

## FreeCAD 1.1.4

Offizielles Release vom **2026-09-28**, letztes geplantes 1.1.x-Wartungsrelease.
Laut Release-Blog keine neuen Produktfeatures, sondern mehr als 30 Korrekturen.
Die zusaetzliche Python-API `scrubEdges` ist dennoch ein nutzbarer API-Zuwachs;
vorhandene MCP-Funktionen werden nicht als neue FreeCAD-Features ausgegeben.

Die Releasehinweise nennen zwei Dateiverarbeitungs-Sicherheitskorrekturen
(FEM-ZipSlip und VRML-Texturen), die vorherige Versionen betreffen. Deshalb ist
ein Upgrade von 1.1.1 auf 1.1.4 empfohlen, auch wenn FEM hier ausgeschlossen ist.
Der MCP-Normalmodus macht untrusted FCStd-Dateien nicht sicher.

Quellen:

- [Offizielles Release 1.1.4](https://github.com/FreeCAD/FreeCAD/releases/tag/1.1.4)
- [Release-Blog](https://blog.freecad.org/2026/09/28/freecad-1-1-4-released/)
- [API-Aenderung PR 32013](https://github.com/FreeCAD/FreeCAD/pull/32013)
- [Native Python-API](https://github.com/FreeCAD/FreeCAD/blob/1.1.4/src/Mod/TechDraw/App/AppTechDrawPy.cpp)
- [Native Flaechenrandbereinigung](https://github.com/FreeCAD/FreeCAD/blob/1.1.4/src/Mod/TechDraw/App/DrawProjectSplit.cpp)

Verwendet wurde das offizielle Windows-x86_64-py311-Portable-Archiv, getrennt
von der installierten Version. SHA256 vor dem Entpacken erfolgreich geprueft:

```text
4828741fc91ee37fafcdb97a1abacb18b04ba451ac4372d9ff7a7349b36f4d6d
```

Ein erster unvollstaendiger Download hatte eine andere Pruefsumme und wurde
nicht ausgefuehrt. Ein erneuter Download mit curl lieferte den offiziellen Wert.
Getestete Laufzeit: **1.1.4, Build 20260928**, Commit
`4fd3bf320d9566a27e60069fc8387448aaa3a094`. Vergleich: **1.1.1, Build 20260414**.
Host: Python 3.10.11, MCP SDK 1.27.1. Geprueft ist Windows GUI, nicht Linux,
macOS, Headless, aeltere Versionen oder eine kuenftige FreeCAD-2.x-Laufzeit.

## Verifizierte Ergebnisse

| Pruefung | Ergebnis |
| --- | --- |
| Finale lokale Suite `python -m unittest discover -s tests -p 'test_*.py' -v` | 44/44, 2.897 s |
| Finale native Suite 1.1.4, eigenes Testmakro, Port 9936 | 47/47, 47.484 s |
| Finale native Suite 1.1.1, eigenes Testmakro, Port 9937 | 47/47, 17.747 s |
| MCP `--audit-only`, 1.1.4 | bestanden, 168 Tools, Normalmodus, nativer API-Vertrag, Undo/Redo, FCStd-Reopen |
| MCP `--audit-only`, 1.1.1 | bestanden, 168 Tools, Normalmodus, `unsupported_feature` |
| MCP `--contracts-only`, 1.1.4 | bestanden |
| MCP Bestands-Smoke, 1.1.4 | bestanden, einschliesslich STEP/STL/OBJ, Bild und Python-Ablehnung |
| MCP `--stage8-only`, 1.1.4 | A1/A2/A3 je zweimal bestanden: 64/65/104 strukturierte Aufrufe pro Lauf |
| MCP `--stage9-only`, 1.1.4 | zweimal bestanden: je 97 strukturierte Assembly-Aufrufe |
| Editor-Diagnosen geaenderter Python-Dateien | keine gemeldeten Fehler |

Bestehende README-Markdownlint-Hinweise bleiben; kein neuer Python-Fehler wird
dadurch verdeckt. Lokale Tests nutzen Mocks, native Tests einen internen Harness,
MCP-Laeufe echten stdio/XML-RPC-Transport ohne freie Modelliercodeausfuehrung.
Die Prozessverlust-Pruefung und jeder einzelne fruehere Stage-3-bis-7-MCP-Lauf
wurden in diesem Audit nicht separat wiederholt; die native Gesamtsuite und
A1-A4 decken wesentliche Pfade daraus ab, nicht jede Variante.

Finale Berichte im temporaeren Benutzerverzeichnis:

```text
%TEMP%/freecad-audit114-final-9936.json
%TEMP%/freecad-audit111-final-9937.json
%TEMP%/freecad-audit-mcp-v4iawbt_/report.json                 (finaler 1.1.4-Audit)
%TEMP%/freecad-audit-mcp-io51wr_9/report.json                 (1.1.1-Audit)
%TEMP%/freecad-stage8-mcp-f5k2_1c0/                          (A1/A2/A3)
%TEMP%/freecad-stage9-mcp-qpmda9ei/                         (A4 Assembly)
```

Der fruehere 1.1.4-Bericht `freecad-audit-mcp-lnhih2zp` hat eine ueberholte
Beschriftung zu 15 mm/3 Kanten und ist **nicht** der finale Nachweis.
Fehlgeschlagene Zwischenlaeufe wurden behoben und erneut geprueft.
TEMP-Berichte sind keine dauerhaft archivierten Releaseartefakte.

## TODO und Groessere Umstrukturierungen

| Prioritaet | Offener Punkt | Eintritt und Abnahme |
| --- | --- | --- |
| Hoch | N19/Stufe 10: echter TechDraw-Zeichnungsworkflow | Seiten/Templates, Projektions-/Schnitt-/Detailansichten, Masse, Layout, PDF/SVG; A5, Referenzedit, FCStd-Reopen und Bild-/Exportpruefung nach AGENTS.md |
| Danach | N20/Stufe 11: Draft | Strukturierte Elemente, Texte und Arrays mit Placement/Einheiten und nativen Roundtrips |
| Danach | N21: Mesh und erweiterter Austausch | Inspektion, Reparatur, Konvertierung, weitere vereinbarte Formate; keine Behauptung universeller Mesh-Heilung |
| Hoch fuer Release | N22/Stufe 12: Installation/Gesamtabnahme | Versions-/Installationsvertrag, bewusste Add-on- und MCP-Aktualisierung, komplette abschliessende Akzeptanzmatrix; Normalmodus hier nur vorgezogen |
| Mittel | Wiederholbare Versionsmatrix/Crash-Nachweise | CI-/Portable-Harness fuer 1.1.1/1.1.4, Prozessverlust und Lastgrenzen erneut nativ pruefen, Releaseberichte dauerhaft archivieren |
| Optional | Grosse Dateien domaenenweise aufteilen | MCP-Registrierung und Testworkflows nach Domaenen modularisieren, oeffentliche Toolnamen/Schemas unveraendert; vor eigenem Refactor Auftrag und Regressionstore festlegen |

**Keine grobe Umstrukturierung durchgefuehrt.** Bestehende Operationsmodule,
Auswahlresolver, Transaktionsbesitz und ContractResponse wurden wiederverwendet.
Eine groessere Modularisierung ist eine getrennte Folgearbeit, kein notwendiger
Teil dieser Fehlerkorrekturen. Diese Entscheidung steht auch in [memory.md](memory.md).

## Migration und Uebergabe

Add-on und MCP-Workspace/Paket gemeinsam auf diesen Stand aktualisieren.
Das installierte Add-on wurde nicht automatisch ersetzt. FreeCAD und den
MCP-Client nur bewusst nach Sicherung offener Dokumente neu starten; keine
Benutzersitzung fuer ein Update ungefragt beenden. Standardport bleibt 9875.
Entwickler-Opt-in muss im FreeCAD-Prozess gesetzt sein, nicht nur beim MCP-Server.

Eigene alte Testprozesse wurden nach bestaetigt leerem Dokumentstatus beendet.
Die finale 1.1.4-Instanz PID 6104 war bei Abschluss bereits nicht mehr vorhanden;
Ursache nicht festgestellt, kein Neustart und keine nachtraegliche Erfolgsannahme.
Die finale 1.1.1-Instanz PID 12032 wurde nach leerem Status gezielt beendet.
Im Auditschritt keine Benutzerdateien, Beispielmodelle oder installierten Add-on-Dateien geaendert.
Portable Laufzeit, Testkonfigurationen und Berichte verbleiben in TEMP.

Naechster Einstieg: zuerst [AGENTS.md](AGENTS.md), [memory.md](memory.md)
und [docs/COVERAGE.md](docs/COVERAGE.md) lesen.
Fuer neue Live-Pruefungen Prozesse, Interpreter und geladenen Workspace-Code
neu feststellen. Stufe 10 nur auf expliziten Folgeauftrag implementieren.

## Nachfolgende Ordnerbereinigung

Am 2026-10-09 nach gesondertem Auftrag und ausdruecklicher Freigabe auch alle
Beispiele und Modellskripte entfernt: examples/ und models/ mit CAD-Dateien,
Exporten, Bildern, Backups, FEM-Debugskripten und Simulationsergebnissen.
Ebenso CAD-Testdateien und den ausschliesslich beispielbezogenen Modellpruefer
entfernt. Zusammen 104 Artefaktdateien (18,51 MiB), drei Cache-Ordner;
doppelte Plan-Datei und Modellpruefer zusaetzlich entfernt.

Arbeitsregeln und vollstaendiger 14-Stufen-Plan stehen zusammen in
[AGENTS.md](AGENTS.md). Verweise und README bereinigt, Ignore-Regeln fuer
Backups und versehentliche CAD-Testartefakte ergaenzt. Server, regulare Tests,
Konfiguration und Projektdokumentation bleiben erhalten. Historische Nachweise
beziehen sich teilweise auf inzwischen entfernte Beispiele.

Erneute lokale Suite nach Loeschung: **44/44 bestanden, 3,016 s**; lokale
Markdown-Links geprueft. Keine neuen nativen FreeCAD-Laeufe fuer diese
Dateibereinigung. .git, .venv, Standardinstallation und externe TEMP-Berichte
nicht bereinigt. Zum Abschluss dieser Bereinigung war noch kein Commit,
Push oder Tag erstellt.

## Git-Veroeffentlichungsauftrag

Gesonderte Freigabe am 2026-10-09: Auditverbesserungen und Bereinigung committen,
pushen und taggen. Zielbranch `origin/main`, annotierter Tag `bridge-v0.11.0`
fuer die Bridge-API; die Paketversion bleibt `0.1.0`. Erneuter Pre-commit-Lauf:
**44/44 lokale Tests bestanden, 2,329 s**. Publikationsnachweis: Remote-Branch
und aufgeloester Tag zeigen auf denselben Commit, Arbeitsbaum sauber.
