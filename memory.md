# Projektgedaechtnis: FreeCAD MCP

Zuletzt aktualisiert: 2026-09-17.
Plan: [agent.md](agent.md). Bisheriger Audit: [docs/AUDIT.md](docs/AUDIT.md).

## Aktuelle Uebergabe

- Aktueller Auftrag: **Stufe 5 Sketcher**. **Abgenommen am 2026-09-17 nach
  technischem Gate**, Umfang I05-I17/N08/N09 laut CONTRACTS. 136 Tools,
  Bridge 0.6.0, 19 neue MCP-Werkzeuge fuer Geometry-/Constraint-CRUD,
  Constraintvarianten/-modi/-diagnosen, externe Geometrie, Attachment und
  Zeichenoperationen. Details in docs/CONTRACTS.md.
- Final: **33 lokale Tests**, **36 native GUI-Tests**, **zweimal 52 Stufe-5-
  MCP-Aufrufe** mit FCStd save/reopen sowie Vertrags-, Stufe-4-, Stufe-3- und
  Bestands-MCP-Regressionslaeufe bestanden. Stufe 4 lief zweimal mit 113,
  Stufe 3 zweimal mit 121 Aufrufen. FreeCAD 1.1.1, Workspace-Bridge 0.6.0;
  Stufe-5-Transport auf 9885, finales GUI-/Regressionsgate PID 31044/Port 9886.
- Kein Benutzerprozess neu gestartet oder Dokument veraendert. Standardaddon
  und registrierter MCP-Server weiterhin nicht aktualisiert. Stufe 6 nicht gestartet.

Aktueller Startauftrag fuer den naechsten Chat:

> Lies AGENTS.md, agent.md, memory.md und docs/COVERAGE.md, ACCEPTANCE.md,
> CONTRACTS.md. Stufen 1-5 sind im dokumentierten Umfang abgenommen. Nur nach
> neuem Auftrag Stufe 6 beginnen; keine Stufe-5-Nacharbeit ohne konkreten Fehler.
> Sketcher arbeitet lokal XY; externe Geometrie und planare Attachments verwenden
> revisionsgepruefte Stufe-4-Auswahlen und muessen nach Mutationen neu abgefragt
> werden. FreeCAD 1.1 Trim unterstuetzt keine Achsen; keine beliebige Spline-Suite.
> Standardinstallation ist weiterhin alt; vor Live-Tests Interpreter, Bridge-
> Version, geladene Dateien, Prozesse und Port neu feststellen. Kein ungefragter
> Neustart/Reload der Benutzersitzung. FEM bleibt ausgeschlossen, CAM/BIM inaktiv.

Historische Uebergabe vor Stufe 4 (nicht der aktuelle Startauftrag):

- Letzter Auftrag: **CNC-Oberfraese ueber MCP modellieren**, siehe separates
  Konzeptprotokoll unten. Keine neue Roadmap-Stufe aktiviert.
- Letzter Stufenauftrag: **implementiere stufe 3**. Stufe 3 ist **Abgenommen am
  2026-09-16 nach technischem Gate**, im dokumentierten Umfang N03-N06/I30.
  Stufen 1/2 bleiben abgenommen. Stufe 4 nicht begonnen.
- 107 Tools, Bridge-API 0.4.0: 22 neue strukturierte Dokument-/Property-/
  Spreadsheet-/Expression-/Kopier-/Link-/Abhaengigkeits-/Loeschwerkzeuge.
  Einzelheiten und Migrationsgrenzen in [docs/CONTRACTS.md](docs/CONTRACTS.md).
- Finale Pruefung: 30 lokale Tests, 28 native Integrationstests, zweimal 120
  strukturierte MCP-Aufrufe fuer Stufe 3 auf frischer Instanz sowie Stufe-2-
  Vertragslauf und Bestands-Smoke bestanden. Keine freie CAD-Codeausfuehrung
  im Stufe-3-MCP-Test; interne native Harnesslaeufe separat gekennzeichnet.
- Benutzer bestaetigte native-kompatible A1-Aliase
  LengthParam/WidthParam/HeightParam/WallParam statt L/W/H/t, da FreeCAD W
  ablehnt. Mathematische Werte unveraendert. A1-Parameterteil mit Part-Box/Cut;
  vollstaendig bestimmter Sketcher-/PartDesign-Aufbau bleibt Stufen 5/6/8.
- Benutzer startet fuer jede Stufe einen neuen Chat. Nicht eigenmaechtig
  mehrere Stufen implementieren.
- Standardinstallation nicht aktualisiert; finale Workspace-Testinstanz auf
  Port 9879, PID 33952, enthaelt jetzt das CNC-Konzept. Kein bestehender Prozess durch
  diesen Chat beendet. Benutzerdokumente nicht veraendert. FEM ausgeschlossen,
  CAM/BIM nicht aktiviert.

Startauftrag fuer den naechsten Chat:

> Lies AGENTS.md, agent.md, memory.md, docs/COVERAGE.md und docs/ACCEPTANCE.md.
> Lies auch docs/CONTRACTS.md. Stufe 3 ist technisch abgenommen; nicht erneut
> implementieren. Nur auf gesonderten Auftrag Stufe 4 beginnen, Einstieg 4a
> Geometrieauswahl/Revision nach COVERAGE N07. Geometrie- und Kamerapfade
> liegen in view_ops.py/part_ops.py. Neue Dokumentoperationen: document_ops.py;
> Transaktionen: transactions.py/gui_executor.py, Batchallowlist unveraendert.
> Neue MCP-Wrapper verwenden _document_call und ContractResponse, behalten
> null fuer Entfernen von Expressions/Alias/Tip/Links explizit bei.
> Vor Live-Tests Interpreter/Prozesse/Bridge/geladenen Code neu feststellen.
> Standardinstallation ist noch alt; Update und MCP-Neustart bewusst planen,
> Benutzersitzung nicht ungefragt neu laden oder beenden. Stufe 4 nicht begonnen.

## CNC-Konzept: separater Modellauftrag vom 2026-09-16

- Benutzer bestaetigte 1200-mm-Schienen bei 1000x1000-mm-Tisch statt vollem
  1000x1000-mm-Werkzeugweg, obere X-Schienen 200 mm vertikal versetzt,
  Makita-65-mm-Huellkoerper und 150 mm Z-Hub. Antriebsmotoren ausgelassen.
- Modell ueber echte strukturierte MCP-stdio-Aufrufe aus
  [models/cnc_router_mcp.py](models/cnc_router_mcp.py), kein execute_python,
  kein direkter FreeCAD-Code zum Modellieren. Sechs SBR20-Fuehrungen:
  X/Y je 2x1200 mm, Z 2x350 mm; je zwei offene Bloecke, insgesamt zwoelf.
  Drei Spindeln (SFU2010 X/Y, SFU1605 Z), genutete Hohlprofile, Portal,
  zwei geschlitzte Makita-Klemmen und drei Schleppketten (118 Link-Glieder).
- Tisch 1000x1000x18 mm; rechnerischer Werkzeugweg X970/Y910/Z150 mm.
  Aussenhuelle in Mittelstellung ca. 1467.5x1340x935.8 mm.
  Vereinfachte Lieferantenhuellen, keine Kollisionsfahrt/Festigkeitspruefung,
  keine Fertigungsfreigabe. Befestigungsbilder, Passungen, Anschlaege,
  Schutz und Absaugung bleiben offen. Kein CAM/BIM/FEM aktiviert.
- Verifikation: SBR20UU-Probe X/Y/Z bestanden. Finaler Aufruf
  `.venv/Scripts/python.exe models/cnc_router_mcp.py --port 9879 --finalize`
  erfolgreich: 235/235 sichtbare Shapes gueltig mit positivem Volumen;
  516 Objekte einschliesslich Historie, keine Invalid-Zustaende;
  analytische Volumenpruefung Tisch und vier 1200-mm-Schienen bestanden;
  zwoelf Blocklabels sowie erste Y-Schiene Radius10/Height1200 bestaetigt.
  Keine Editor-Diagnosen im Treiber. Protokoll 1203 Eintraege einschliesslich
  rekonstruierter Bauaufrufe, nicht 1203 neue Aufrufe beim Abschluss.
- Ergebnisse unter examples/CNC_SBR20_1200: FCStd, STEP (235 Komponenten,
  1467515 Bytes), PNG (1200x900 visuell kontrolliert), JSON-Massbericht,
  Markdown-Grenzenbericht sowie .mcp.json und .export.mcp.json.
  FCStd-ZIP-Pruefung bestanden; gespeicherte Datei nicht erneut in FreeCAD
  geoeffnet. PNG nach Export/erneutem Fit fehlerfrei; erste Aufnahme hatte
  Renderartefakte und wurde ersetzt.
- Offene Laufzeitluecke: nach Aufbau/Gruppierung war HasPendingTransaction
  true; Ursprung nicht geklaert. save_document_safe und spaeter Recompute
  korrekt mit transaction_conflict blockiert. Kein Schutz umgangen und
  keine fremde Transaktion abgeschlossen. Benutzer speicherte per GUI in
  tests/CNC_SBR20_1200.FCStd; unveraenderte Kopie nach examples, SHA256-Gleichheit
  beim Abschluss geprueft. Dokument bleibt unter dem tests-Pfad geoeffnet,
  Modified=false, PendingTransaction=true. Vollautomatischer End-to-End-
  Speicherworkflow ist fuer dieses Modell daher NICHT nachgewiesen.
- Naechster Einstieg nur auf Auftrag: Lieferantendaten/Fertigungsdetails
  konkretisieren oder die automatische Transaktion mit Gruppen/Links
  isoliert reproduzieren. Benutzerprozess nicht neu starten; keine freie
  Codeausfuehrung als Umgehung. Roadmap-Stufe 4 bleibt nicht begonnen.

## Stufenstatus

| Stufe | Thema | Status |
| --- | --- | --- |
| Basis | Vorheriger Audit, Reparaturen und Demo | Historisch umgesetzt und getestet |
| 1 | Abdeckungsmatrix und Abnahmevertrag | Abgenommen am 2026-09-16; Umfang einschliesslich D1-D5 bestaetigt |
| 2 | MCP-Vertraege und Infrastruktur | Abgenommen am 2026-09-16; 28 lokale/24 CAD-Tests und beide MCP-Laeufe bestanden |
| 3 | Dokumente, Eigenschaften, Parameter | Abgenommen am 2026-09-16; 30 lokale/28 CAD-Tests, zweifacher strukturierter MCP-Lauf und Bestandsregression bestanden |
| 4 | Geometrieauswahl, Messung, Rueckmeldung | Abgenommen am 2026-09-16; 4a/4b, 32 lokale/33 CAD-Tests, zweimal 113 MCP-Aufrufe und Bild-/Bestandsregression bestanden |
| 5 | Sketcher | Abgenommen am 2026-09-17; 33 lokale/36 native GUI-Tests, zweimal 52 MCP-Aufrufe und Bestandsregression bestanden |
| 6 | PartDesign | Nicht begonnen |
| 7 | Part und Flaechen | Nicht begonnen |
| 8 | Auftraege und mechanischer Gesamtworkflow | Nicht begonnen |
| 9 | Assembly | Nicht begonnen |
| 10 | TechDraw | Nicht begonnen |
| 11 | Draft, Mesh, Austausch | Nicht begonnen |
| 12 | Gesamtabnahme und Betriebsmodus | Nicht begonnen |
| 13 | CAM | Optional; nicht freigegeben |
| 14 | BIM/Arch | Optional; nicht freigegeben |

Zulaessige Statuswerte fuer die Fortfuehrung: Nicht begonnen, In Arbeit,
Blockiert, Implementiert aber nicht vollstaendig geprueft, Abgenommen.

## Stufe 5: Abschlussprotokoll vom 2026-09-17

Umgesetzt: 19 neue MCP-Werkzeuge in `sketcher_ops.py`/`server.py` fuer
Geometriepunkte, Construction und Loeschen; Constraint-Wert, treibend/referenz,
aktiv/inaktiv und Loeschen; Linienlaenge, Punkt-Punkt-X/Y, Durchmesser,
Punkt-auf-Objekt und Achswinkel; externe Kanten, Attachment, Trim, Extend,
Fillet, Copy/Clone und Mirror. `sketch_info` liefert vollstaendige Modi,
Attachment sowie Konflikt-/Redundanz-/Teilredundanz-IDs. Fehler laufen in der
bestehenden GUI-Transaktion zurueck und nennen bekannte IDs.

Native FreeCAD-1.1-Erkenntnisse: Punktbewegung ueber `moveGeometry`, Attachment
ueber `AttachmentSupport`; planare Flaeche `FlatFace`, Datumebene `ObjectXY`;
Rotation `FreeCAD.Rotation(rz, ry, rx)` fuer X/Y/Z-Eingaben; Trim verwendet die
Zweiargumentform und lehnt `include_axes=true` vor Mutation ab. Der erste externe
Geometrieindex ist -3. Constraintmodi werden ueber `getDriving`/`getActive`
gelesen. Keine beliebige Spline-Edit-Suite oder Support-Reparatur zugesagt.

Abnahme: 33/33 lokale `unittest`-Tests in 1.453 s. 36/36 native GUI-Tests in
13.736 s, einschliesslich drei Stufe-5-Tests und aller Exportregressionen.
Echter MCP-stdio-Lauf `--stage5-only`: zwei unabhaengige Runs mit je 52
strukturierten Aufrufen und FCStd save/reopen, 136 registrierte Tools, Port 9885.
Profile Gehaeuse/Flansch DoF 0 ohne Block und nach Massaenderung editierbar;
Konfliktrollback exakt. Danach auf Port 9886 bestanden: `--contracts-only`,
`--stage4-only` (zweimal 113), `--stage3-only` (zweimal 121) und Legacy-Smoke.

Naechster Einstieg nur auf neuen Auftrag: Stufe 6 gemaess agent.md/N10-N13.
Vor Live-Tests Prozess, Port, Bridge-Version und geladene Workspace-Dateien neu
pruefen. Die aktuell agent-eigene GUI PID 31044 auf Port 9886 darf nicht als
persistenter Zustand angenommen werden. Standardinstallation blieb unveraendert;
keine Benutzersitzung und kein Benutzerdokument wurde veraendert.

## Stufe 4a/4b: Abschlussprotokoll vom 2026-09-16

Umgesetzt: geometry_ops.py mit neun neuen MCP-Tools list_subelements,
select_subelement, resolve_subelement, measure_distance, measure_angle,
check_interference, highlight_subelements, get_view_state und capture_view.
Globale mm/Grad, kombinierte Filter, begrenzte Pagination, konservative native
Dokumentrevisionen; keine stille Neuzuordnung bei Topologie-/Namenswechsel,
Undo/Redo oder reopen. Part-/PartDesign-Fillet/Chamfer sowie PartDesign-
Thickness/Draft akzeptieren Auswahlobjekte und pruefen sie vor Mutation.
Altselektoren und Batchallowlist bleiben dokumentiert ungeschuetzt/unveraendert.
Kontakt und Interferenz liefern Abstand und Schnittvolumen getrennt, nur
statisch. Ansichtsfarben/Transparenz/Visibility lesbar und wiederherstellbar;
RGB validiert, geklemmte Transparency gibt tatsaechlichen Wert zurueck.

Betroffene Dateien: neu freecad_addon/freecad_ai_bridge/geometry_ops.py;
contracts.py, operations.py, security.py, part_ops.py, partdesign_ops.py,
view_ops.py; src/freecad_mcp/server.py, schema.py; tests/test_tool_contracts.py,
freecad_integration.py, mcp_smoke.py, start_bridge.FCMacro; README, CONTRACTS,
COVERAGE, ACCEPTANCE und diese Uebergabe. Alle vorbestehenden Aenderungen erhalten.

Finale Laufzeit: Host .venv/Scripts/python.exe, Python 3.10.11, MCP 1.27.1,
Serverpaket 0.1.0, Windows 10.0.26200. FreeCAD 1.1.1 Build 20260414, Commit
0108fd4b4850cc46e625b60e53cea7a7bbe69f8d; Bridge 0.5.0; Port 9883, PID 31340.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
$env:FREECAD_TEST_PORT = '9883'
$env:FREECAD_INTEGRATION_PATTERN = 'test_*'
$env:FREECAD_INTEGRATION_REPORT = '<absolute temporary JSON report path>'
Start-Process 'C:\Program Files\FreeCAD 1.1\bin\freecad.exe' -ArgumentList 'D:\Proj\FreeCad\FreeCad_MCP_Server\tests\start_bridge.FCMacro'
.\.venv\Scripts\python.exe tests/mcp_smoke.py --stage4-only
.\.venv\Scripts\python.exe tests/mcp_smoke.py --contracts-only
.\.venv\Scripts\python.exe tests/mcp_smoke.py --stage3-only
.\.venv\Scripts\python.exe tests/mcp_smoke.py
```

- 32/32 lokale Tests, final 1.720 s. Neue strikte Schemas, Weiterleitungen,
  Subelementfehler und gemischte JSON-/native MCP-Bildantwort; Bestandsregression.
- 33/33 native Tests, 12.739 s, frischer Import. Fuenf neue Tests mit Filtern,
  gekruemmten Geometrien, Container-/Linkrotationen, Topologie-/Namenswechsel,
  sechs Auswahlverbrauchern samt stale-Rollback, analytischen Messwerten,
  Darstellungs-Roundtrip, zwei Dokumenten, sieben Sollblickrichtungen und
  Pixeltests. Bericht:
  C:/Users/jakob/AppData/Local/Temp/freecad-stage4-verified-64d148d8-702e-4f6b-bd06-e55382a21510.json
- M4 PASS: zweimal 113 protokollierte Aufrufe (ohne abschliessendes Cleanup),
  echte MCP-stdio-/GUI-Kette ohne execute_python zum Modellieren. Analytische
  Box V6000/A2200, Abstand5, Kontakt V0/Abstand0 bzw.0.0005, Interferenz V3000,
  Vertexdiagonale sqrt(1400), Linien-/Ebenenwinkel0/90, Zylinderflaeche200*pi,
  Kreislaenge10*pi; Revision/Undo/Redo/reopen, Fillet mit ausgewaehlter Kante.
  Bericht, Transkripte, FCStd/STEP und Bilder:
  C:/Users/jakob/AppData/Local/Temp/freecad-stage4-mcp-x8eaflhd/
  14/14 PNGs 800x600: je 806..1927 Modell-Stichprobenpixel im 8px-Raster;
  1/view-isometric.png und 2/view-top.png visuell korrekt, vollstaendig und
  ohne Renderartefakte. GUI-Highlight wird von saveImage nicht garantiert abgebildet.
- Stufe-2-Vertrags-/Batchregression PASS; Stufe-3-Regression zweimal 121 Aufrufe
  PASS, Artefakte C:/Users/jakob/AppData/Local/Temp/freecad-stage3-mcp-g70hfn7i/.
  Bestands-Smoke PASS (116 Tools), dessen freier Python-Namensraumtest nur
  Altpfadregression, nicht Stufe-4-CAD-Abnahme. Pylance-Syntaxpruefung bestanden;
  keine Editorfehler in geprueften geaenderten Python-Dateien.

Zwischenfehler und verifizierte Korrekturen:

1. FCStd reopen kann internen Namen vom Dateinamen ableiten. 4a-Fixture speichert
  unter Dokumentname.FCStd und beweist dadurch Wiederverwendung desselben Namens.
2. App::Link besitzt kein getGlobalPlacement/getParents. Bereits platzierte
  Link-Shape plus geometrischer Besitzer aus InList/Group; freie und im gedrehten
  Container liegende Links nativ geprueft. App::Part hat aggregierte Shape und
  ist kein geeignetes NoShape-Negativfixture.
3. FastMCP/Pydantic erzeugt kein Schema aus list[Image|str]; capture_view nutzt
  structured_output=False, JSON-Vertragstext plus nativen Bildinhalt.
4. Native Kamera/GUI-Ereignisse koennen Auswahl leeren; Wiederherstellung vor
  Rendern und nach Rueckkehr zur vorherigen Ansicht. Inaktive Views konnten
  leere PNGs liefern; gezielte temporaere Aktivierung und redraw erforderlich.
  Aktivdokument vor JEDEM GUI-Zugriff sichern. Animierte Presets erzeugten
  Zwischenansichten; Animation fuer Aufnahme deaktivieren und danach restaurieren.
  Finale Zwei-Dokument-/Pixel-/Blickrichtungs-/visuelle Gates bestanden.
5. Zusaetzliche Stufe-3-Regression traf unsaved_changes vor dependency_conflict.
  Test isoliert Abhaengigkeitsfehler mit discard_changes=True, speichert Quelle
  nach Datei-/Link-Negativworkflow erneut vor Close und aktualisiert Cleanup-Liste
  sofort nach Close. Produktionsschutz und document_ops.py unveraendert.
  Voller Zweifachlauf danach bestanden; keine Schutzfunktion umgangen.

Sitzung: Benutzerinstanz PID33952/9879 nie modelliert, neu geladen oder beendet.
Eigene Entwicklungsinstanzen 29740/9880, 26992/9881, 1552 und20648/9882 sowie
38568/9883 verwendet. Vor bewusstem Beenden stets leere Dokumente und Port/PID
geprueft. 29740/9880 spaeter nicht erreichbar, Ursache unbelegt; nicht durch
diesen Chat beendet. Finale Instanz 31340/9883 bleibt nach Cleanup offen;
abschliessende strukturierte Zustandsabfrage bestaetigt keine offenen Dokumente.
Abschliessende Prozesspruefung: PID31340 vorhanden, fruehere Benutzer-PID33952
nicht mehr vorhanden. Ursache unbekannt; kein Beenden/Neustart durch diesen Chat.
Artefakte nur TEMP; keine Benutzerdateien ueberschrieben. Standardinstallation
unveraendert, Benutzerbetrieb benoetigt bewusstes Addon-/Paketupdate und MCP-Neustart.

Verbleibende vertragliche Grenzen: keine persistenten Topologiereferenzen,
keine kontinuierliche Kollision, keine Masse ohne Dichte/Fertigungsfreigabe,
keine freie-NURBS-Auswahlanalyse ueber ausgegebene Merkmale hinaus. Alte raw
EdgeN/FaceN, Draft-Neutralebenenstrings, generische LinkSub-Properties und
Batchselektoren bleiben ohne Revision. GUI-Auswahl getrennt von PNG-Hervorhebung.
Keine offene Stufe-4-Funktionsluecke im dokumentierten Umfang; Stufe 5 nur auf Auftrag.

## Stufe 3: Abschlussprotokoll vom 2026-09-16

Umgesetzt (22 neue Tools, 107 gesamt):

- Explizite Dokumentinspektion/-aktivierung/Recompute, GUI-Modified,
  Gruppen/Body-Mitgliedschaft/Tip mit Zyklus-/Mitgliedschaftsschutz.
- Typisierte Properties fuer 29 explizit freigegebene native Typen, Metadaten,
  Einheitenkonvertierung, Listen, Link/LinkSub, Read-only-/Enum-/Referenz-/
  Constraint-Clamping-Schutz. Unbekannte Typen diagnostisch statt Stringersatz.
- Spreadsheet-Zellen/Bereiche/Aliase und native arithmetische Expressions
  lesen/setzen/entfernen; Recompute-Fehler und Zyklen rollen eigene Transaktionen
  zurueck. 256 Zellen/Listeneintraege, 4096 Zeichen pro Inhalt/Expression.
- Label-Umbenennung, rekursive unabhaengige Kopie einschliesslich Parametertabelle,
  lokale/externe App::Links, Abhaengigkeits-/Folgeobjektabfrage, Loeschvorschau
  und exakt bestaetigte aktuelle Loeschmenge inklusive Containerbesitz.
- Safe Save/Close additiv: overwrite/discard opt-in, Dateisperr-/Verzeichnis-/
  Fremddokument-/Pending-Transaktionsschutz. Dateien nicht undo-bar und keine
  Datei-Rollbackzusage. Altes delete_object jetzt mit Abhaengigkeitsschutz;
  bestehende Save/Close-Signaturen und Altverhalten unveraendert.

Betroffene Dateien: neues `freecad_addon/freecad_ai_bridge/document_ops.py`;
`operations.py`, `gui_executor.py`, `security.py`, `contracts.py`;
`src/freecad_mcp/server.py`; Tests `test_gui_executor.py`, `test_tool_contracts.py`,
`freecad_integration.py`, `mcp_smoke.py`; README, CONTRACTS, COVERAGE, ACCEPTANCE
und diese Datei. Vorbestehende uncommittete Aenderungen erhalten.

Verifikation (Host explizit `.venv/Scripts/python.exe`, Python 3.10.11,
MCP 1.27.1, Serverpaket 0.1.0, Windows 10.0.26200; FreeCAD 1.1.1,
Build 20260414, Commit 0108fd4b4850cc46e625b60e53cea7a7bbe69f8d):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
$env:FREECAD_TEST_PORT = '9879'
$env:FREECAD_INTEGRATION_REPORT = '<absolute temporary JSON report path>'
Start-Process 'C:\Program Files\FreeCAD 1.1\bin\freecad.exe' -ArgumentList 'D:\Proj\FreeCad\FreeCad_MCP_Server\tests\start_bridge.FCMacro'
.\.venv\Scripts\python.exe tests/mcp_smoke.py --stage3-only
.\.venv\Scripts\python.exe tests/mcp_smoke.py --contracts-only
.\.venv\Scripts\python.exe tests/mcp_smoke.py
```

- **30/30 lokale Tests**, 0.878 s: Schema/Weiterleitungen aller Tools,
  Nullweitergabe, strukturierte Fehler, Transaktions-/Batch-/Sicherheitsregression.
- **28/28 native Integrationstests**, **9.385 s**, frisch gestartete Instanz
  33952/9879. Vier neue Stufe-3-Tests mit 29 Property-Typen samt Roundtrip/
  Negativwert/Rollback, Einheiten, Alias-/Expressionzyklen, unabhaengiger
  Ausdruckskopie, rekursiven Kopien, Container/Origin-Loeschung und Undo,
  Rotationen X/Y/Z/Kombination und inverser Verschiebung, Dirty-/Dateischutz.
  Bericht: `C:/Users/jakob/AppData/Local/Temp/freecad-stage3-final-e78571d1-1011-42a7-849e-d54078ecdf42.json`.
- **MCP Stufe 3 PASS**, zweimal unabhaengig **120 protokollierte Aufrufe**,
  107 Tools/Bridge 0.4.0. Ausschliesslich strukturierter CAD-Aufbau, gleiche
  Namen in zwei Dokumenten, Body/Tip, A1-Parameterteil 32088/38328/49536 mm^3,
  Zyklen/ungueltige Referenz/Innenmasse mit Rollback, Undo/Redo, Kopie/Link,
  externe Links vor/nach Datei-Roundtrip, Loeschbestaetigung/Undo/Redo, Save/
  Reopen/zweite Aenderung/Export. Echter exklusiver Windows-Dateisperrtest:
  file_write_failed mit unbekanntem Dateizustand, Originalbytes unveraendert.
  Finale Berichte, Transkripte, FCStd/STEP/STL und native Backups:
  `C:/Users/jakob/AppData/Local/Temp/freecad-stage3-mcp-scvlev7m/` (report.json,
  Unterverzeichnisse 1 und 2). Cleanup ueber sichere Tools bestanden.
- **Stufe-2-MCP-Vertragsregression PASS**, alle elf Batchoperationen,
  Rollback/Teilfehler/Undo/Redo/Referenzen und Cleanup; **Bestands-Smoke PASS**.
  Dessen Python-Namensraumtest bleibt Altpfadregression, kein CAD-Abnahmeausweg.
- Keine Editorfehler in zehn geaenderten Python-Dateien. Neue Vertrags-/Matrix-
  Abschnitte ohne Markdown-Diagnosen; vorbestehende README-Warnungen belassen.

Zwischenfehler und verifizierte Korrekturen:

1. `Gui.Document.isModified()` existiert nicht; native Property `Modified`
   lesen. App-save setzt dieses GUI-Flag nicht zurueck; nach Erfolg explizit
   loeschen. Native Testfixture vor geschuetztem Edit eigene Transaktion committen.
2. `str(Unit)` ist Diagnose; Einheitensignatur mit mm/kg/s/A/K/mol/cd/deg und
   explizitem `*` serialisieren. Quantity-Eingaben nativ parsen, cm-Skalierung
   erhalten. `getEditorMode()` liefert Statusnamensliste, keine Bitmaske.
3. MCP-Legacy structuredContent ist result-Wrapper; Test liest dort Text-JSON,
   neue ContractResponse direkt. Helferparameter tool_name kollidierte mit
   boolean_cut-Argument; Testhelfer auf tool_identifier umbenannt.
4. Native Aliasablehnung fuer W: Benutzer bestaetigte alternative Aliasnamen.
   Externe Links verlangen gespeicherte Quelle UND gespeicherten Owner.
5. FreeCAD akzeptiert leeres Verzeichnis als Save-Ziel; vor Save regular-file-
   Pruefung ergaenzt, Verzeichnis und bestehende Datei bleiben unveraendert.

Laufzeit/Installation: Zu Beginn nur PID 30336 vorhanden, nicht verwendet oder
beendet. Eigene Entwicklungsinstanz PID 35528/9878 gestartet und fuer interne
native Harnesslaeufe/lesende API-Probes nachgeladen; kein strukturierter MCP-
Abnahmeaufbau ueber diesen Codepfad. Finale neue Instanz 33952/9879 mit sauberem
Modulimport. Bei Schlussabfrage existiert nur noch PID 33952; 9878 nicht mehr
erreichbar, Ursache nicht belegt. Kein Prozess wurde durch diesen Chat beendet.
Finales get_document_state auf 9879: documents={}, active_document=null.
Benutzerdokumente nicht veraendert. Testartefakte bleiben ausschliesslich TEMP.
Standardaddon/MCP-Registrierung nicht aktualisiert. Venv-Import ohne explizites
PYTHONPATH fand alten Client aus D:/Proj/FreeCad/AI_Server; Testtreiber setzen
Workspace-src explizit. Benutzerbetrieb erfordert bewusstes Paket-/Addonupdate
und MCP-Neustart, kein ungefragtes Reload der Benutzersitzung.

Offene Grenzen, keine Stufe-3-Funktionsluecken im dokumentierten Umfang:
keine generischen Methoden/dynamischen Property-Erzeuger, native Typallowlist,
keine Funktionsaufrufe oder externen Expressions, keine revisionsfesten
Topologiereferenzen, keine geometrische Aenderungssimulation, kein verteilter
Datei-/Dokumentrollback. Externe Dokumente explizit recomputen/speichern.
STEP/STL-Ausgaben hier auf Erzeugung geprueft, vollstaendiger Formatrundlauf
bleibt Stufe 11; A1-Sketcher/PartDesign-Aufbau bleibt Stufen 5/6/8.
Stufe 4 ausschliesslich nach neuem Benutzerauftrag.

## Stufe 2: Abschlussprotokoll vom 2026-09-16

Zusaetzlich zum unten historisch erhaltenen 2a-Zwischenstand:

- `schema.py`: zentrale Registrierung ergaenzt alle Parameterbeschreibungen,
  geometrische Einheiten/Koordinatensysteme, Varianten und Fehlerhinweise.
  Verifizierte Alt-Ausnahme: Ellipsenwinkel und Bogenwinkel rad, Constraints Grad;
  Placement/Move/Rotate elternlokal, Top-Level-Primitiven dokumentglobal.
- `transactions.py`: eigene Transaktion, Ablehnung fremder ausstehender
  Transaktionen, Sichtbarkeitswiederherstellung innerhalb der Transaktion,
  Abort/Rollbackstatus. Executor bindet Signaturen, prueft Referenzen, serialisiert
  Mutationsergebnisse vor Commit und schuetzt Undo/Redo/Save/Close bei Fremdbesitz.
- `batch.py` und `execute_batch`: max. 100 Schritte/65536 JSON-Bytes,
  elf explizit erlaubte Operationen, strikte Vorvalidierung, rueckwaerts gerichtete
  gleichdokumentige Ergebnisnamenreferenzen, atomarer Einzeldokument-Batch,
  nichtatomarer Mehrdokument-Teilstatus, nichtmutierende statische Vorschau.
  Datei-I/O/Lifecycle/Undo/Redo/Code/nested Batch ausgeschlossen; Loeschen nur
  unreferenzierter Blaetter. Kein Geometriesimulations-/Abbruchversprechen.
- Capabilities Bridge-API 0.3.0, Infrastrukturflags true, Limits/Allowlist und
  konkrete implementierte/fehlende Optionen. Fach-API-Varianten bleiben ihren
  Stufen zugeordnet. 82 Alttools behalten Ergebnisse/Defaults, drei neue Tools
  versionierte Antworten. Migration und Dateigrenzen in CONTRACTS.
- Part-Ergebnishelfer lehnt leere/ungueltige Formen ab: sonst erschien ein
  fehlgeschlagener Fillet auf Edge999 als Erfolg und verhinderte Rollback.

Finale Verifikation mit Host
`D:/Proj/FreeCad/FreeCad_MCP_Server/.venv/Scripts/python.exe`, Python 3.10.11,
MCP 1.27.1, Serverpaket 0.1.0, Windows 10.0.26200; FreeCAD 1.1.1,
Build 20260414, Commit 0108fd4b4850cc46e625b60e53cea7a7bbe69f8d:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
$env:FREECAD_TEST_PORT = '9877'
.\.venv\Scripts\python.exe tests/mcp_smoke.py --contracts-only
.\.venv\Scripts\python.exe tests/mcp_smoke.py
```

- **28/28 lokale Tests**, final **0.654 s**. Darunter Batch 100/101/Payload,
  Typen/Flags, unbekannte Operationen/Parameter, Forward-/Cross-Doc-Referenzen,
  einmaliger Commit, Rollback-/Teilstatus, Metadaten aller registrierten Felder.
- **24/24 FreeCAD-Integrationstests**, final **4.788 s**. Vom Workspace-Makro
  ueber optionales `FREECAD_INTEGRATION_REPORT` gestartet, bestehender
  `run_tests()`-Harness plus fremde ausstehende Transaktionen in zwei Dokumenten.
  Finaler JSON-Bericht:
  `C:/Users/jakob/AppData/Local/Temp/freecad-stage2-b737020c-5f06-4e0d-90b1-5367b27aed55.json`.
- **MCP-Vertragslauf PASS**, 85 Tools, Bridge 0.3.0, Port 9877. Kein execute_python
  oder anderer freier Code fuer CAD-Aufbau. Gleiche Objektnamen in zwei Dokumenten,
  Referenz-/Schemafehler, Vorschau ohne Mutation, Batchreferenzen, ein Undo/Redo
  fuer atomaren Batch, echter Filletfehler mittendrin, vollstaendiger Rollback,
  Vorvalidierung, Mehrdokument-Erfolg/-Teilfehler, alle elf freigegebenen
  Operationen, analytisches Cutvolumen, gueltige Formen, Loeschschutz und
  Wiederherstellung eines geloeschten Objekts. Testdokumente geschlossen.
- **Bestands-MCP-Smoke PASS**, 85 Tools: Fillet/Messen/Undo/Redo, STEP/STL/OBJ,
  natives PNG, historische Python-Namensraumregression. Letztere bleibt nur
  Alt-Kompatibilitaet, nicht strukturierter Workflowbeweis.
- Keine Editorfehler in 13 geprueften geaenderten Python-Dateien; Syntaxchecks
  fuer beide Liveharnesses bestanden. Keine volle A1-A5-/Modellabnahme behauptet.

Fehlgeschlagene Zwischenlaeufe und Korrekturen:

1. Erster neuer MCP-Lauf meldete Edge999-Fillet als Erfolg: leere Form am
   Part-Ergebnishelfer erkannt, Regressionstest ergaenzt; erneuter Lauf bestanden.
2. Erster CAD-Fremdtransaktionstest benutzte leeres openTransaction; FreeCAD
   HasPendingTransaction war false. Fixture erzeugt jetzt ausstehende Labelaenderung
   und prueft deren Erhalt plus Pending-Status ausdruecklich; bestanden.
3. Erweiterter Variantenlauf fand neue offene Transaktion nach Rollback:
   Sichtbarkeitszuweisungen nach Abort waren Ursache. Jetzt nur geaenderte Werte
   vor Abort innerhalb der eigenen Transaktion setzen. Regression und Live bestanden.
4. Loesch-Rollback veraenderte nur interne Aufzaehlreihenfolge. Snapshot nach
   internem Name kanonisiert; Identitaet/Geometrie/Sichtbarkeit unveraendert, PASS.

Weitere geaenderte Dateien in dieser Fortsetzung: `src/freecad_mcp/schema.py`
(neu), `server.py`; Addon `transactions.py`/`batch.py` (neu), `contracts.py`,
`operations.py`, `gui_executor.py`, `part_ops.py`; Tests `test_batch.py` (neu),
`test_gui_executor.py`, `test_tool_contracts.py`, `mcp_smoke.py`,
`freecad_integration.py`, `start_bridge.FCMacro`; README/CONTRACTS/COVERAGE/
ACCEPTANCE und diese Uebergabe. Bestehende sonstige Aenderungen erhalten.

Sitzung/Installation: Standardinstanz PID 36344 (9875) und vorherige Testinstanz
PID 32320 (9876) unangetastet. Eigene neue Instanzen 22020 und 15196 auf 9877
fuer frisch geladenen Code ersetzt; vor Beenden leer bzw. ausschliesslich
Harness-Dokumente nachgewiesen. PID 15196 nach fehlgeschlagenem Cleanup mit
Stop-Process verworfen, keine Benutzerdateien betroffen. Finale Instanz
**30336**, Start **19:54:00**, Port **9877**, bleibt nach bestandenem Cleanup
ohne Testdokumente offen. Temporaere Smoke-Exporte entfernt; JSON-Testberichte
liegen im TEMP-Verzeichnis. Makro liest optional FREECAD_TEST_PORT (Default 9876)
und FREECAD_INTEGRATION_REPORT. Variablen beim naechsten Start bewusst setzen.
Keine Addoninstallation oder laufende Standard-MCP-Registrierung aktualisiert;
fuer Benutzernutzung vollstaendiges Addonupdate und MCP-Neustart erforderlich.

Abnahme: Stufe-2-Gates laut agent.md und N01/N02 im dokumentierten Umfang
erfuellt. Grenzen bleiben sichtbar: statische Vorschau, begrenzte Batchallowlist,
Alt-Dateiueberschreibverhalten ausserhalb Batch, kein verteilter Rollback,
Namensreferenzen nicht persistent/topologisch revisionsfest, Raw-Python noch
vorhanden. Diese Regeln sind keine stillschweigende Zusage spaeterer Fachstufen.
Stufe 3 nicht begonnen; nur auf neuen Auftrag starten.

## Stufe 2a: Historischer Zwischenstand vom 2026-09-16

Umgesetzt:

- Zwei additive MCP-Tools (jetzt 84): `get_capabilities`, `resolve_reference`.
  Strikte nichtleere Namen; kein Label-/Aktivdokument-Fallback. Versionierte
  Pydantic-Antwort mit Schema, structuredContent, identischem JSON-Text,
  Status/Daten/Referenzen/Warnungen/Fehler. Domainfehler im Vertragsstatus,
  Schemafehler als MCP isError; siehe CONTRACTS.
- Capabilities liefern FreeCAD-Build, Bridge-API 0.2.0, Server-/SDK-Versionen,
  Workbench-Inventar, Einheiten/Koordinaten-Grundvertrag und ehrliche Flags:
  Batch/Vorschau/konsistente Transaktionen false, Raw-Python true.
- GUI-Ausnahmen behalten Typ/Code; RPC behaelt error-Text fuer alte Clients
  und ergaenzt error_details. Client liest alte und neue Antworten und wirft
  FreeCADRemoteError als RuntimeError-Unterklasse. Kein stiller Retry.
- Neue Reads ohne Recompute/GUI-Update/Transaktion. Explizite Namensaufloesung
  ist keine persistente oder topologisch revisionsgesicherte Referenz.
- MCP-Mindestabhaengigkeit 1.27.1 (tatsaechlich gepruefte structured-output API).
  Keine Distributionsversionsanhebung und kein Update der Benutzerinstallation.
- Bestehender Smoke-Harness erhaelt `--contracts-only`, ohne execute_python
  oder anderen freien Code fuer CAD-Aufbau. Test erzeugt zwei eigene Dokumente
  mit SameBox und 1000/2000 mm^3, prueft Referenzen/Fehler/Zustand und Cleanup.

Betroffene Dateien: `src/freecad_mcp/server.py`, `connection.py`,
`freecad_addon/freecad_ai_bridge/contracts.py` (neu), `operations.py`,
`gui_executor.py`, `rpc_server.py`; `tests/test_connection_security.py`,
`test_gui_executor.py`, `test_tool_contracts.py`, `mcp_smoke.py`;
`pyproject.toml`, `README.md`, `docs/CONTRACTS.md` (neu), `docs/COVERAGE.md`,
`docs/ACCEPTANCE.md`, `memory.md`. Vorherige uncommittete Aenderungen erhalten.

Aktuelle Tests, aus Repository-Root, jeweils explizit mit
`D:/Proj/FreeCad/FreeCad_MCP_Server/.venv/Scripts/python.exe`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_connection_security.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_gui_executor.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_tool_contracts.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python.exe -m py_compile tests/mcp_smoke.py
.\.venv\Scripts\python.exe tests/mcp_smoke.py --contracts-only
.\.venv\Scripts\python.exe tests/mcp_smoke.py
.\.venv\Scripts\python.exe -m pip check
```

- Erste gezielte Laeufe: 7 Verbindungstests (0.005 s), 3 GUI-Tests (0.502 s),
  7 Vertragstests (0.562 s) bestanden. Gesamtlauf: **17/17**, **0.886 s**.
- Syntaxcheck bestanden; Editor meldet keine Fehler in zehn geaenderten
  Python-Dateien. Bestehende README-Markdownwarnungen ausserhalb des geaenderten
  Bereichs nicht bereinigt. Neue Vertragsdatei ohne Markdown-Diagnosen.
- Vertrags-Livetest: zuerst zweimal connect fehlgeschlagen; bei lesender
  Diagnose WinError 10061, erste Testinstanz war wieder beendet. Kein CAD-Aufbau
  in den gescheiterten Laeufen. Mit per Start-Process neu gestarteter Instanz
  **PASS**, 84 Tools, structuredContent/JSON-Text, zwei Dokumente/identischer
  Objektname, Fehlercodes/Schema-Negativfaelle, identischer Zustand und Volumen,
  Cleanup bestanden. Keine freie CAD-Codeausfuehrung im Vertrags-Livetest.
- Bestands-Smoke **PASS**: stdio/RPC, Part-Fillet, Messen, Undo/Redo,
  STEP/STL/OBJ, natives MCP-PNG, historischer Python-Namensraumtest. Letzterer
  nur Altpfadregression, kein Nachweis fuer strukturierte CAD-Referenzaufgaben.
- `pip check`: **No broken requirements found.** Kein neuer Lauf der 23
  FreeCAD-Integrationstests oder der Modellabnahme; alte Ergebnisse historisch.

Verifizierte Laufzeit: Host Python **3.10.11**, MCP SDK **1.27.1**, Serverpaket
**0.1.0**, Windows **10.0.26200**. Live FreeCAD **1.1.1**, Build
`20260414 (Git shallow)`, Commit `0108fd4b4850cc46e625b60e53cea7a7bbe69f8d`,
Builddatum `2026/04/14 22:09:59`; Bridge-API **0.2.0**, Vertrag **1.0**.
Workspace-Bridge mit unveraendertem `tests/start_bridge.FCMacro`, Port **9876**;
geladener neuer Vertrag ueber Live-Capabilities und Fehlerpfad nachgewiesen.

Sitzung: erste Prozessabfrage leer, spaeter Standardinstanz PID 36344 mit Port
9875 und erste Testinstanz PID 31304 mit Port 9876. Letztere verschwand; Ursache
nicht belegt. Neu gestartet: **PID 32320**, Startzeit **19:29:25**, via
`Start-Process` mit Workspace-Makro. Kein Prozess durch diesen Chat beendet;
Standardinstanz nicht verwendet. Test-GUI bleibt offen, beide Vertragstest-
Dokumente und Smoke-Dokument geschlossen, temporaere Exporte entfernt.
Keine bleibenden CAD-Artefakte erzeugt, keine Benutzerdateien geaendert.
Prozess-/Portzuordnung im naechsten Chat neu pruefen, nicht voraussetzen.

Offene Gates: feldweise Alt-Schemas/Einheiten/Koordinaten, konkrete Options-
Capabilities statt allein Workbench-Praesenz; vollstaendiges 2b mit
Transaktionsbesitz/Vorschau/Batch, validierten Ergebnisreferenzen, Teilstatus,
Rollback/Undo/Redo bei zwei Dokumenten und fremden Transaktionen, Datei-I/O-
Abgrenzung. Keine vollstaendige Stufe-2-Abnahme und kein Start von Stufe 3.

## Stufe 1: Historisches Ergebnis und Pruefprotokoll vom 2026-09-16

Umgesetzt:

- 82 tatsaechlich lokal registrierte MCP-Tools vollstaendig inventarisiert,
  79 direkte Weiterleitungen und drei Sonderpfade unterschieden. 80 oeffentliche
  CAD-Addon-Funktionen: operations 8, sketcher_ops 26, partdesign_ops 17,
  part_ops 15, view_ops 14. Dokumentstatus ist die zusaetzliche indirekte Funktion.
- 38 Bestandszeilen I01-I38, 22 Ausbauzeilen N01-N22 und drei Ausschlusszeilen
  X01-X03, jeweils mit Status, Art, Varianten/Parametern, FreeCAD-Zielversion,
  Testevidenz/-luecke, Zielstufe und Pruefkriterium. Historische Tests nicht als
  aktuellen Live-Lauf ausgegeben. `vorhanden` und `getestet` sind getrennt.
- Fuenf Referenzaufgaben mit Erstellen/Bearbeiten, Undo/Redo, Negativfaellen,
  Speichern/Schliessen/Oeffnen, weiterer Aenderung und Export definiert:
  Gehaeuse, Welle/Flansch, idealisierter Schraubstock, Gelenkbaugruppe, Zeichnung.
- Gemeinsame numerische Toleranzen, Variantenpruefungen, Datei-/Batch-/Jobregeln,
  Format- und Informationsverlustvertrag sowie Stufen-/Normalmodusgates definiert.
- Begruendete Teilstufen fuer 2-12 vorgeschlagen; keine Reihenfolgeaenderung,
  keine Teilstufe gestartet. Keine API-Aenderung umgesetzt.

Betroffene Dateien dieses Chats: nur `docs/COVERAGE.md`, `docs/ACCEPTANCE.md`
und `memory.md`. Bestehende uncommittete Code-/Demoaenderungen erhalten.

Aktuelle Verifikation (aus Repository-Root, ohne FreeCAD-Verbindung):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_tool_contracts.py" -v
```

- Ergebnis: **4 Tests bestanden**, Laufzeit 0.405 s. Geprueft: Weiterleitungsziele
  und Argumentnamen, oeffentliche `*_ops.py`-Funktionen, fuenf ergaenzte
  Registrierungen und gemocktes natives MCP-Bild. Keine Geometrieabnahme.
- Einmaliger lesender Python-Pruefblock per PowerShell-Here-String an
  `.\.venv\Scripts\python.exe -`: `asyncio.run(server.mcp.list_tools())`,
  `inspect.signature` und AST-Auswertung der Workspace-Dateien.
  Ergebnis: **82 Tools, 79 direkte Ziele, 80 oeffentliche CAD-Funktionen**;
  Interpreter **Python 3.10.11**, absolut
  `D:/Proj/FreeCad/FreeCad_MCP_Server/.venv/Scripts/python.exe`.
- Zweiter einmaliger lesender Pruefblock, gleicher Interpreter: Markdown-
  Inventarnamen gegen reale Registrierung, eindeutige IDs, lokale Links,
  ASCII-Text, A1-A5-Ueberschriften und analytische Volumen geprueft.
  Erster Lauf fand einen Dokumentations-Rechenfehler: Gehaeuse L=100/t=3
  hat 38328 statt 40328 mm^3. Wert korrigiert und denselben Check erweitert
  erneut ausgefuehrt: **PASS**, 82 Tools genau einmal, 63 eindeutige Funktions-IDs,
  Links/ASCII gueltig, A1-A5 vorhanden, A1/A2/A3-Volumen nachgerechnet.
- Abschliessender lesender Pruefblock fuer alle drei Dokumente: **PASS** fuer
  lokale Links, ASCII, konsistente Tabellenspalten und Stufe 2 weiterhin
  `Nicht begonnen`. Markdown-Diagnose fand anfangs zwei fehlende finale
  Zeilenumbrueche in den neuen Dokumenten; diese wurden ergaenzt.
- Die einmaligen Pruefbloecke sind im Chat-Toolprotokoll, kein neuer Testharness
  im Repository angelegt. Kein kompletter lokaler 11-Test-Lauf, kein neuer
  FreeCAD-Integrationstest, MCP-stdio-Smoke oder Modelltest: reine Dokumentations-
  stufe, keine funktionale Aenderung; solche Ergebnisse bleiben historisch.

Erfuellte Stufe-1-Lieferkriterien: Bestandsinventar, begrenzte Variantenmatrix,
messbarer Abnahmevertrag, Referenzaufgaben, sichtbare Luecken/Ausschluesse,
Stufenabgleich und Uebergabe. **Abnahmegate erfuellt: Benutzerbestaetigung von
D1-D5 am 2026-09-16 durch Antwort "ja" auf die Umfangsfrage.** Stufe 2 bleibt
unbeauftragt und nicht begonnen. Nur Freigabestatus und Uebergabe in den drei
Dokumenten aktualisiert; keine funktionalen Aenderungen oder neuen CAD-Tests.

Bestaetigte Entscheidungen und verbleibende technische Punkte
(Details in ACCEPTANCE D1-D6):

- D1: Kernumfang/Teilstufen und fuenf idealisierte Referenzen bestaetigt;
  historische 17-Koerper-Demo ist bewusst kein Pflichtminimum.
- D2: Fuenf native Gelenktypen, TechDraw-Varianten, begrenztes Draft/Mesh und
  Formate FCStd, STEP AP214/AP242, STL, OBJ, planares DXF/SVG, Zeichnungs-PDF/SVG.
  Native API-/Enum-Verfuegbarkeit und STEP-Farb-/Strukturerhalt noch nicht live
  belegt; fehlende Pflichtvariante blockieren, nicht still streichen.
- D3: Numerische Toleranzen, diskrete statische Kollisionspruefung, vereinfachte
  Gewinde und Ausschluss von Fertigungs-/Festigkeitszusagen bestaetigt.
- D4: Maximal 100 Batchschritte; Einzeldokument atomar, mehrere expliziter
  Teilstatus; Dateien separat; kein garantierter Abbruch laufender Kerneljobs.
- D5: Normalmodus ohne freie Codepfade, dokumentierte Alt-API-Migration;
  konkrete Schemas/Fehlercodes in Stufe 2, optionale Entwicklermodusentscheidung
  spaetestens Stufe 12. Bestaetigung ist noch kein Implementierungsauftrag.
- D6 ist vorgegeben: FEM ausgeschlossen, CAM/BIM nicht aktiviert.

Installation/Laufzeit/Dateien: Kein FreeCAD-Prozess gestartet, verbunden,
beendet oder neu geladen; keine Addon-Installation geaendert. Keine Testdokumente
oder CAD-Exportdateien erzeugt; bestehende offene Benutzerdokumente nicht
inspiziert oder veraendert. Aktueller GUI-/Bridge-Zustand bleibt unbekannt.

## Bereits umgesetzte Ausgangsbasis

Aus dem vorherigen Implementierungschat, ausfuehrlich in `docs/AUDIT.md`:

- Urspruenglich 77 registrierte Tools; nach Ergaenzung 82. Die alte README-
  Angabe von 84 war falsch. Nicht mit vollstaendiger API-Abdeckung verwechseln.
- Neue Tools: subtraktiver Loft/Pipe, Part-Fillet/-Chamfer und OBJ-Export.
- RPC-Allowlist fuer oeffentliche, im Addon definierte Funktionen; Loopback-
  Bindung, Socket-Timeout und Server-Cleanup verbessert.
- Frischer gemeinsamer Python-Namensraum je Skriptaufruf; Futures verwerfen
  abgelaufene noch nicht gestartete GUI-Auftraege.
- Transaktionen fuer strukturierte Modellieroperationen in bestehenden
  Dokumenten, Undo/Redo/Rollback und Fix fuer geschlossene Dokumentwrapper.
- Sketcher: echte Freiheitsgrade, Punktfixierung, XZ/YZ-Offsets,
  Liniensymmetrie und tangential verbundene parametrische Langloecher.
- PartDesign: symmetrische Pads, Loft/Pipe-API, Achsen/Ebenen fuer Muster,
  Gewindebohrungen, Draft-Neutralebene, Featurefehler und Tip-Sichtbarkeit.
- Part: parametrische Kantenfeatures und richtige X/Y/Z-Rotationszuordnung.
- Export: MeshPart-Triangulation, sichtbare Endergebnisse ohne Body-Duplikate,
  leere Auswahl als Fehler und STEP/STL/OBJ-Roundtrips.
- Screenshots: richtiges Dokument, native MCP-Bilder, temporaere Dateien und
  aktualisierter GUI-Zustand vor Kamera-Fit.

Diese Verbesserungen nehmen Stufe 2 bis 8 teilweise vorweg, erfuellen aber
nicht automatisch deren wesentlich breitere Abnahmekriterien.

## Historisch verifizierte Tests

Letzter dokumentierter funktionaler Pruefstand: 2026-09-15 im Audit und
vorherigen Implementierungschat. In diesem Planungsauftrag nicht erneut
ausgefuehrt. Bei spaeteren Aenderungen aktuelle Ergebnisse neu eintragen.

- 11 lokale unittest-Tests erfolgreich.
- 23 FreeCAD-Integrationstests erfolgreich.
- Echter MCP-stdio-Smoke-Test erfolgreich; 82 Tools registriert.
- Modelldatei erneut geoeffnet: 17 gueltige Einzelkoerper und 18 vollstaendig
  bestimmte Skizzen; STEP: 17 gueltige Solids; STL: geschlossen, 12.254 Facetten.
- Modell-STEP relative Volumenabweichung: ca. 2.45e-7;
  STL relative Volumenabweichung: ca. 5.51e-4.
- Nicht jedes bestehende Tool hat einen eigenen Live-Test. Vertragspruefung
  aller Weiterleitungen ist keine geometrische Vollabnahme aller Varianten.

Vorhandene Befehle, aus dem Repository-Root:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python tests/mcp_smoke.py
```

Der Smoke-Test erwartet standardmaessig die isolierte Bridge auf Port 9876;
der Port ist ueber `FREECAD_TEST_PORT` aenderbar. Interpreter und Abhaengigkeiten
vor Ausfuehrung neu feststellen, nicht aus alten Terminalangaben ableiten.

Live-Testprogramme innerhalb der FreeCAD-GUI, absolute Pfade anpassen:

```python
import runpy
result = runpy.run_path("D:/Proj/FreeCad/FreeCad_MCP_Server/tests/freecad_integration.py")["run_tests"]()
result = runpy.run_path("D:/Proj/FreeCad/FreeCad_MCP_Server/tests/verify_model.py")["verify_model"]()
```

`run_tests(pattern="test_export*")` erlaubt fokussierte Tests. Diese internen
Python-Testharnesses bleiben erlaubt. Die neuen Referenzaufgaben muessen
zusatzlich ohne freie Python-Ausfuehrung ueber MCP abgenommen werden.

## Umgebung und Installation

- Workspace: `D:/Proj/FreeCad/FreeCad_MCP_Server`.
- Verifiziert mit FreeCAD 1.1 unter Windows und MCP-Host Python 3.10.
- FreeCAD-Programm: `C:/Program Files/FreeCAD 1.1/bin/freecad.exe`.
- Installiertes Addon beim letzten Abgleich:
  `%APPDATA%/FreeCAD/v1-1/Mod/FreecadAIBridge`.
- Vor Update wurde gesichert nach:
  `%APPDATA%/FreeCAD/v1-1/FreecadAIBridge_Backup_20260915_231952`.
- Alle elf installierten Python-Dateien stimmten beim letzten Hashvergleich
  mit dem Workspace ueberein. Kein Nachweis fuer den aktuellen geladenen Code.
- `tests/start_bridge.FCMacro` startet eine workspace-basierte Bridge auf
  Port 9876 in einer separaten FreeCAD-Instanz. Standardinstallation: Port 9875.
- Letzte Arbeitsinstanz enthielt das Schraubstockmodell. Prozess-IDs,
  Verbindungen und offene Dokumente sind nicht chatuebergreifend verlaesslich.
- Addon-Aenderungen erfordern Reload/Neustart; MCP-Schemaaenderungen erfordern
  MCP-Neustart. Benutzersitzung nicht ungefragt beenden oder ueberschreiben.
- Viele bestehende Codeaenderungen sind noch uncommitted. Aktuellen Git-Status
  pruefen und alle vorhandenen Aenderungen erhalten; keine automatischen Commits.

## Relevante Dateien und Modell

- `src/freecad_mcp/server.py`: MCP-Werkzeugregistrierung und Weiterleitung.
- `src/freecad_mcp/connection.py`: XML-RPC-Client.
- `freecad_addon/freecad_ai_bridge/`: Executor, Sicherheit und CAD-Operationen.
- `tests/test_*.py`: lokale Regressionen und Werkzeugvertraege.
- `tests/freecad_integration.py`: Live-Geometrietests.
- `tests/mcp_smoke.py`: echter MCP-stdio-End-to-End-Test.
- `tests/verify_model.py`: gespeichertes Beispiel und Exporte pruefen.
- `models/praezisions_schraubstock.py`: reproduzierbarer Demoaufbau in Etappen.
- `examples/Praezisions_Schraubstock_MCP.FCStd` sowie `.step`, `.stl`, `.png`:
  Schraubstock mit 17 Koerpern, 133 Baumobjekten, 18 bestimmten Skizzen.
- Modell hat vereinfachtes Gewinde, keine zertifizierte Belastbarkeit und keine
  vollstaendige globale Parameterverknuepfung. Bisher per Python aufgebaut;
  daher noch kein Beweis fuer den neuen Workflow ohne Python-Ausweichweg.

## Verifizierte technische Stolperstellen

- `Sketch.solve()` liefert Solverstatus, nicht Freiheitsgrade; `DoF` und
  `FullyConstrained` verwenden. Kein `Sketcher.Constraint("Lock", ...)`.
- FreeCAD 1.1 Pad: `SideType`; aelterer Fallback: `Midplane`.
- PartDesign-Loft/Pipe haben keine `Solid`-Eigenschaft. Shell-Anforderungen
  gehoeren zu Part und werden bisher fuer PartDesign abgelehnt.
- Musterreferenzen sind LinkSub-Verweise auf Body-OriginFeatures nach `Role`.
- Hole muss vor Zuweisung von `Depth` im Body sein. ISO-Groessen heissen
  beispielsweise `M6x1.0`, nicht einfach `M6`.
- GUI vor `fitAll()` aktualisieren; nach Mesh-Export vor Bildausgabe erneut
  aktualisieren/einpassen. Sonst kann die Vorschau abgeschnitten erscheinen.
- Roh-Python ist keine Sandbox. Loopback ohne Authentifizierung ist nur fuer
  vertrauenswuerdige lokale Clients geeignet; keine Portweiterleitung.
- Bereits laufende CAD-Berechnungen koennen nach Timeout noch fertig werden.
- Pylance-MCP benoetigt hier explizit `workspaceRoot`. `rg` war nicht verfuegbar.

## Pflege bei jeder Uebergabe

Folgenden Block pro bearbeiteter Stufe ergaenzen und oben Status/Naechsten
Schritt aktualisieren. Wiederkehrende Basisinformationen nicht duplizieren.

```text
Datum / Stufe / Status:
Umgesetzt (konkrete Funktionen und Varianten):
Betroffene Dateien und API-Aenderungen:
Tests (Befehl, Umgebung, Ergebnis; nicht ausgefuehrte Tests mit Grund):
Abnahmekriterien (erfuellt / offen):
Entscheidungen und begruendete Planabweichungen:
Blocker oder verbleibende Teilaufgaben:
Installation / geladener Code / offene Testdokumente:
Konkreter Startauftrag fuer den naechsten Chat:
```
