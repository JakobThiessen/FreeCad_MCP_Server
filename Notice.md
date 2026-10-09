# MCP-Server-Audit und FreeCAD 1.1.4

Stand: 2026-10-09. Workspace-Bridge **0.11.0**, MCP-Vertrag **1.0**,
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

Das ist **kein TechDraw-Zeichnungsworkflow**. Seiten, Templates, Ansichten,
Projektionen, Schnitte, Details, Masse und PDF/SVG-Export bleiben TODO.

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
