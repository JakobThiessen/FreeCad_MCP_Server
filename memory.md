# Projektgedaechtnis: FreeCAD MCP

Zuletzt aktualisiert: 2026-10-10.
Plan und Arbeitsregeln: [AGENTS.md](AGENTS.md). Bisheriger Audit: [docs/AUDIT.md](docs/AUDIT.md).

## Aktuelle Uebergabe

### Stufe 12a implementiert/geprueft; Gesamtabnahme offen (2026-10-10)

- Auftrag: Stufe 12 implementieren und pruefen, nicht nur planen. Feste Teilgates:
  12a Normalmodus/Referenzregression/konkrete Restoreluecken; 12b vollstaendiger
  V-Einzelvarianten-Audit samt Doppel-MCP; 12c isolierte Addoninstallation/Update/
  Neustart und kontrollierter Prozessverlust; 12d Kriterienaudit/Gesamtfreigabe.
  12a-Nachweise unten bestanden; 12b-12d offen, **Stufe 12 nicht abgeschlossen**.
  Kein FEM/CAM/BIM, kein Commit/Push/Tag/Release, keine Benutzerinstallation geaendert.
- Produktionsfixes: geometry_ops.capture_view sichert Fremddokumentkamera,
  pausiert deren Animation und restauriert Kamera/Aktivierung nach GUI-Updates.
  Der kombinierte Lauf hatte erst Aktivdokument-, dann Fremdkameraaenderungen
  gezeigt; fokussiert zweimal113 und danach mehrere komplette Doppelruns bestanden.
  assembly_ops.create_joint instanziiert jetzt den nativen ViewProviderJoint.
  Neue V-Fixtures fanden nach FCStd-Reopen/Recompute den vorherigen Fehler
  "'int' object has no attribute 'redrawJointPlacements'". Native Joint-Erzeugung
  ohne GUI-Proxy war Ursache. Fix am Erzeuger, keine FreeCAD-Installation editiert.
  Migration bereits fehlerhaft gespeicherter Gelenke bleibt offen.
- Harness: mcp_smoke --stage12-only fuehrt 15 vorhandene Gates zweimal aus,
  mit checkpoint-report/failure und Host-/Serverprovenienz; security-only
  ermoeglicht zwei Normalmoduslaeufe aus einem TEMP-installierten Hostpaket.
  --stage9-only erzeugt jetzt wirklich alle fuenf Joint-Fixtures; die alte
  feste Ergebnisliste war kein MCP-Nachweis. Geometrische Connectorauswahl,
  DoF/Referenzen/Kollision/Suppression/Undo/Redo/ungueltige unveraenderte
  Mutationen/Save/Reopen/zweiter Edit/Recompute/Resave, zweimal267 Fachaufrufe.
  A4-Rollback-Placementvergleich allein 1e-12 abs/0 rel statt exakter Floats,
  alle anderen Felder exakt. Beobachtetes Rauschen ca.4,4e-15; G/X unveraendert.
  test_connection_security exakter Opt-in; freecad_integration native ViewProvider-
  Regression. start_bridge meldet Python/PID/Pfade/Hashes, optional TEMP-Addonpfad.
- Beruehrt: assembly_ops.py, geometry_ops.py, test_connection_security.py,
  freecad_integration.py, mcp_smoke.py, start_bridge.FCMacro, README, CONTRACTS,
  COVERAGE, ACCEPTANCE, memory. Versionen unveraendert:194 Tools/Bridge0.11.0/Paket0.1.0.
- Frisch ermittelt: Windows10.0.26200; FreeCAD1.1.1 Build20260414/Commit
  0108fd4b4850cc46e625b60e53cea7a7bbe69f8d, native Python3.11.14; Host
  D:/Proj/FreeCad/FreeCad_MCP_Server/.venv/Scripts/python.exe, Python3.10.11,
  MCP1.27.1. Eigene GUIs mit TEMP-user/system-cfg, ports9950..9955, raw=0.
  Eine fremde GUI PID29592/9875 wurde nicht veraendert/gestoppt. Mehrere eigene
  GUIs verschwanden zwischen Laeufen ohne geklaerte Ursache; zuletzt 3744/9953.
  Kein bestandener Prozessverlusttest daraus abgeleitet. Keine alte PID voraussetzen.
- Aktuelle Hostregression: `.venv\Scripts\python.exe -B -m unittest discover
  -s tests -p 'test_*.py' -v`:55/55,2,913s,Exit0. Editor keine Fehler in fuenf
  geprueften Pythondateien; abschliessendes diff-check siehe weiteren Eintrag.
- Native nach beiden Produktionsfixes: Makro mit FREECAD_INTEGRATION_PATTERN=test_*
  und TEMP-report,59/59,25,915s,Exit0; loaded-module-Pfade/Hashes enthalten.
  Root R=`%TEMP%/freecad-stage12-34e1d64b195946908877e8697550cb76/`;
  `R/native-final.json`, `R/native-final-ready.json`, own PID22176/9954.
  Vorheriger native-full.json59/59 ist Vor-Fix-Beleg, nicht finales Ergebnis.
- Finaler aktueller MCP-Doppelrun: neue reine GUI PID26388/9955, raw=false,
  `.venv\Scripts\python.exe -B tests\mcp_smoke.py --stage12-only`:Exit0,
  **30/30 vorhandene Gates**, Bericht `%TEMP%/freecad-stage12-mcp-pkp8l8di/report.json`.
  Je Lauf:normal_mode113 Negativchecks; contracts inkl.Batch/Jobs; Dokument121,
  Geometrie113,Sketcher52,PartDesign29,Part29,A1=64,A2=65,A3=104,A4=267,
  TechDraw10a46,A5=125,Draft182,Mesh/Exchange142. Transkripte/FCStd/Exports/
  Renderreports in 1/2-Gateordnern. Keine freie Codeausfuehrung als CAD-Ausweg.
  Voriger erfolgreicher Gesamtbericht `%TEMP%/freecad-stage12-mcp-aefqmbk2/`
  nutzt dieselben Produktionsfixes, A4 noch247 mit festen Connectoren. Dessen
  vier A5-PDF/SVG-PNGs, beide A3-PNGs,10a-PDF,Geometrieiso/top direkt angesehen:
  nicht leer, Pflichtangaben/Ansichten/Masse im Blatt lesbar. Finaler Runner
  rendert und prueft numerisch erneut; keine visuelle Vollpruefung aller V-Assets.
  Fokussiert final Gelenke `%TEMP%/freecad-stage9-mcp-qrqvvike/report.json`,2x267.
- Normalmodus: pro Lauf113 negative Checks auf MCP execute_python, direkten
  RPC execute, alle zulaessigen Module mit exec/eval/compile/__import__/private/
  importierten Namen, fremde Module, Jobziele, Batch/Expressions/Spreadsheet.
  Raw deaktiviert, Volumen/Objektzustand erhalten. Spreadsheet `=import os`
  wird nativ als maskierter Literaltext akzeptiert, nicht ausgefuehrt, danach
  geloescht. Ausfuehrbare Funktionsausdruecke abgewiesen. Entwicklerflag nur
  exakt1, keine Sandbox. Kein Anspruch auf boesartige FCStd-/Proxy-Sandbox.
- Installationsteil: `pip wheel --no-deps --no-cache-dir --wheel-dir R/wheels .`
  erfolgreich; wheel0.1.0,size43803,SHA256
  ba88a9db99fecb12cd8f7e934fddbf6d8259f0691266e2fcd03e0e807bbd2072.
  `pip install --no-deps --no-compile --target R/installed-host R/wheels/...whl`
  erfolgreich, keine regulaere Installation editiert. FREECAD_TEST_SERVER_PATH
  auf installed-host und --stage12-security-only startet neuen MCP-stdio-Prozess:
  `%TEMP%/freecad-stage12-mcp-54xvo0nf/report.json`,2x113 erfolgreich,Provenienz.
  Wheel enthaelt nur Hostpaket, nicht Addonfixes. Addoninstallation/Update/Autoload
  offen. CLI --set-config UserAppData, FREECAD_USER_HOME und prozesslokales APPDATA
  aenderten --get-config UserAppData nicht (weiter regulaeres Roaming/v1-1).
  Kein regulaerer Mod-Ordner veraendert. Naechst `--module-path` plus InitGui-
  Pfadauflosung oder echte native Benutzerpfadkonfiguration isoliert verifizieren.
- Auditrest: V fordert fuer JEDE Matrixfunktion/Enum positiv,ungueltig/Grenze,
  Mutation/Edit/Rollback. Bestehende MCP-Gates52/29/29 decken nicht alle Sketch-
  Constraints/Geometrien, PartDesign-End-/Hole-/Pipe-/Transformoptionen und Part-
  Primitiven/Achsen/Spiegel-/Shell-/Repairvarianten ab. Native59 ersetzt V nicht.
  Neue aktuelle Zuordnung in COVERAGE zeigt explizit offene Gruppen; keine
  stillschweigende Umfangsreduzierung. N18 alle5 jetzt MCP-geprueft, Limits/
  Offsets vollstaendig zuordnen; N19/20/21 Variantenweise Audit noch offen.
  Neuer kontrollierter Timeout/Prozessverlustlauf via echtem MCP ebenfalls offen.
- Cleanup: letzte eigene Ports9954/9955 frisch via get_document_state beide
  documents={} und active=null, dann nur PIDs22176/26388 mit passender R-
  Kommandozeile gestoppt. Keine CAD-Dokumente verbleiben; TEMP-Evidenz erhalten.
  Nachkontrolle: keine FreeCAD.exe-Prozesse und keine Listener9950..9955.
  `git diff --check` ohne Ausgabe/Exit0;11 beruehrte Dateien, keine Commitaktion.
  Eine neue Sitzung darf keine Verbindung annehmen.
- Konkreter Startauftrag naechster Chat: Stufe12b an I05-I17/N08-N09 beginnen,
  V-Variantentabelle aus Schemas/Abnahmevertrag mit genauem Fixture/Orakel erstellen,
  bestehende check_stage5 erweitern und sofort doppelt auf neuer eigener GUI pruefen.
  Dann N10-N15 usw.; parallel keine neue Roadmapstufe. 12c danach isoliertes
  installiertes Host/Addon-Paar inklusive Update/Neustart/Hashes und Prozessverlust.
  Gesamtabnahme erst alle Pflichtkriterien; Benutzerfreigabe weiterhin separat.

### Stufe 11b/11c geprueft, Stufe 12 offen (2026-10-09)

- Neuester Auftrag nach Rechnerabsturz: Arbeit an 11b/11c fortsetzen und
  implementieren/pruefen. 11a-Bestand und Dirty-Worktree erhalten. **11b Mesh
  und 11c X-Austausch auf GUI 1.1.1 geprueft; keine Variante entfernt.**
  Kein Start Stufe 12, CAM, BIM, FEM; keine Installation/Commit/Push/Tag.
- Fuenf Mesh-Tools mesh_create/inspect/from_shape/repair/to_shape, zwei
  exchange_export/import; **194 registrierte Tools**, Bridge 0.11.0/Paket
  0.1.0 unveraendert. Explizite Dokumente/Names, strict finite Werte und
  diskriminierte extra-forbid Formatoptionen, GUI-Executor, eigene Undo-
  Transaktionen fuer Dokumentmutationen, keine neue Batchoperation und kein
  execute_python. Additives error.diagnostics erhaelt native Defektursachen.
- Mesh: Facetten/Punkte/Komponenten, globale BBox/Flaeche/Volumen/Abschluss/
  Orientierung und Defekte; Duplikate/degenerierte Facetten entfernen,
  Normalen harmonisieren/nach aussen richten, native fillupHoles mit 0..10000
  Kanten (0 aus), Diagnose vor/nach. Nonmanifold/invalid/self-intersecting
  ausserhalb Reparatur. Solid nur eine geschlossene outward-Komponente,
  target shape ebenfalls vorhanden; static BRep statt Reverse Engineering.
  Absolute Shape-Triangulation mm/rad, Relative=False; max 100000 Facetten.
- Austausch: STEP explizit AP214IS/AP242DIS/mm samt tatsaechlichem Header;
  Praeferenzen restauriert, kein Downgrade. Uniforme geerbte RGB, Labels,
  einfache App::Part-/Dokumentgruppen-/Linkhierarchie und globale Geometrie
  geprueft; externe Linkidentitaet/Parametrik/Constraints/Gelenke verloren,
  per-Face-/Link-Override-Paletten ungeprueft. STL ASCII/binaer, OBJ Import/
  Export, absolute mm/rad-Deflections; Einheit explizite mm-Annahme und
  Materialien/Farben/Struktur verloren. DXF/SVG globales XY Z=0, Linie/
  offener/geschlossener Wire/Kreis/Bogen; native DXF-Kantensortierung fuer
  static Wires, Segmentierung/Labels verloren. SVG native Pfadgeometrie mit
  XML-normalisierter globaler mm-Huelle; kein CSS/Text/Bild/3D/Splinevertrag.
- Absolute passende Pfade, Auswahl 1..100 eindeutige Names, Import max
  64 MiB/1000 neue Objekte. Export in staged TEMP-Verzeichnis am Ziel,
  atomare No-Clobber-Publikation oder explizites Replace. Quelle unveraendert,
  fremde Dokument-/App-Transaktion blockiert; App/GUI-Aktivdokument/Auswahl
  restauriert. Fehlerhafte Imports eigene Transaktion rolled_back. Datei-
  Operationen sind nicht per Undo rueckgaengig. Alt-Wrapper kompatibel;
  Optionen via exchange_export/import. Capabilities nur gepruefte GUI 1.1.1.
- Beruehrt: neue mesh_ops.py (vor Absturz begonnen) und exchange_ops.py;
  contracts.py, gui_executor.py, security.py, operations.py, server.py,
  test_tool_contracts.py, freecad_integration.py, mcp_smoke.py; CONTRACTS,
  COVERAGE, ACCEPTANCE, Notice und diese Uebergabe. Vorhandene 11a-/TechDraw-
  Aenderungen nicht zurueckgesetzt; start_bridge.FCMacro unveraendert weiterverwendet.
- Laufzeit nach Absturz frisch bestaetigt: zuerst keine FreeCAD-Prozesse,
  Port 9945 frei. Eigene FreeCAD.exe aus C:/Program Files/FreeCAD 1.1/bin,
  **1.1.1 Build 20260414**, Commit 0108fd4b4850cc46e625b60e53cea7a7bbe69f8d,
  native Python 3.11.14; Host .venv/Scripts/python.exe Python 3.10.11/MCP
  1.27.1. Workspace-Makro mit TEMP-Konfiguration/Ready-Signal, keine alte
  Verbindung/Installation vorausgesetzt. FREECAD_MCP_ALLOW_RAW_PYTHON=0.
- Host: `.venv\Scripts\python.exe -B -m unittest discover -s tests
  -p 'test_*.py' -v`: **54/54, 3,051 s, Exitcode 0**, inklusive 25 Tool-
  Vertragstests (Schema/Forwarding/Allowlist). Vollausgabe
  `%TEMP%/freecad-stage11bc-resume-9f33d6860515458f9c447b9099d3a65a/host-full-final.txt`.
  Nachfolgende Addon-/Harness-Fixes ohne Host-Serveraenderung. Beruehrte
  Python-Editordiagnosen keine Fehler.
- Native finales Gesamtgate: Makro mit FREECAD_INTEGRATION_PATTERN=test_*
  und FREECAD_INTEGRATION_REPORT unter TEMP, **59/59, 27,033 s**, vier neue
  Tests plus alle Bestandsregressionen, native Quellpfade/Hashes im Report.
  `%TEMP%/freecad-stage11bc-resume-9f33d6860515458f9c447b9099d3a65a/full-final-after-export.json`.
  Belegt gruppierte Shape/Mesh-Koordinaten, Defekte/Reparatur/Solid, beide
  echten STEP-Schemas/Farben/Struktur/Praeferenzen und alle Formate.
- **Finaler echter MCP-Doppelrun:** alle nativen Test-/Tracevariablen entfernt,
  neue reine GUI ohne Testvorlauf, Ready-PID **28820**, Port 9945, Version
  1.1.1, mesh_editing/structured_exchange/schema_selection=true und raw=false.
  `.venv\Scripts\python.exe -B tests\mcp_smoke.py --stage11bc-only`:
  **zweimal 142 protokollierte Fachaufrufe plus je elf Cleanup-Aufrufe,
  Exitcode 0**; beide Transkripte je 153 Eintraege, 194 Tools.
  Report `%TEMP%/freecad-stage11bc-mcp-iyc0kc7w/report.json`, Dokumente/Exporte/
  Transkripte je Unterordner 1/2. Ready/isolierte Konfiguration
  `%TEMP%/freecad-stage11bc-final-gui-0584705e9a7c4aa5a3afbcde55ae8e25/ready.json`.
  Orakel: offene Facette/ganze Wand und zu kleine Lochgrenzen; Duplikate,
  kollinear degeneriert, inward/inkonsistent, nonmanifold/Mehrkomponenten-
  Solid-Ablehnung; Undo/Redo/Fehlerrollback; Box8000, feinere Kugel mit
  analytischem Volumen nach G; AP214/AP242 zwei RGB-Links bei X0/60, Labels,
  je8000/BBox/ein Container zwei Kinder; ASCII/binaer-STL/OBJ Abschluss/
  Orientierung/Volumen/BBox; Rechteck40x20/KreisR5/Line/openWire/90GradArc,
  Gesamtkontur/Abschluss/Radius/globalBBox fuer DXF/SVG. No-Clobber/Overwrite,
  malformed SVG rolled_back, falsches Schema/fehlende Datei/nichtplanar,
  zweites leeres Fremddokument unveraendert. FCStd save/close/reopen, zweiter
  Placementedit/repair/resave/reexport/reimport mit BBox[9,10,11]..[49,30,21].
  Snapshotnumerik 1e-6 abs/rel, Struktur exakt, analytische G-Gates unveraendert.
- Gefundene/reparierte Fehler: fehlende MCP-Parameterbeschreibungen nach
  Absturz; _object verlangt Dokument-Name; BridgeError um Diagnose erweitert.
  Native Mesh.Volume unsigned; removeFacets liess Defektindices zurueck,
  native Rekonstruktion aus verbliebenen Facetten. Harmonize/Komponenten
  verloren Placement; speichern/restaurieren. Mesh.Topology enthaelt eigenes
  Placement, Konvertierung addiert nur Parent. STEP Linkfarben aus linked
  source, leeres GetContents None. DXF Writer zerlegt Konturen, native
  sortEdges/Wire rekonstruiert. SVG Bogen erscheint als gleichachsige Ellipse;
  native Export-Gruppen verschieben Spiegelung/Lage, XML-Huelle normalisiert;
  default SVG-Namespace statt vom Importer abgelehntem ns0. Reexportcheck
  fand verlorene Mesh-Placement beim Zusammenfuehren; die erste lokale
  Korrektur verschob das Zusammenfuehren versehentlich in den Shape-else.
  Auch diesen Patchfehler unmittelbar erkannt/repariert; beide Arten
  uebernehmen jetzt die globale numerische Topologie.
  Vorherige gescheiterte Kandidaten/Transkripte bleiben TEMP, nicht als
  erfolgreiche Abnahme ausgegeben. Gekuerzter Select-Object-First-Ausgabelauf
  hatte Exitcode1 trotz Report; finales Gate ohne abschneidende Pipeline.
- Cleanup: vor jedem eigenen Neustart frisch leerer RPC-Bestand; finale native
  RPC-Uebersicht `{documents: {}, active_document: None}`. Nur letzte eigene
  **PID16980** nach leerem Bestand beendet; danach **0 FreeCAD-Prozesse,
  0 Listener9945**, TEMP-Nachweise erhalten. Benutzerdateien unveraendert.
- **Naechster Einstieg:** Stufe11 im vereinbarten Umfang auf GUI1.1.1 geprueft.
  Stufe12 offen und nur nach Benutzerauftrag beginnen: Gesamtabnahme A1-A5,
  Installation/Update/MCP-Neustart und Normalmodus-Pfade. Neue Sitzung muss
  Laufzeit/Version/Port/geladenen Workspace-Code erneut pruefen. Keine alte
  PID/Verbindung annehmen. 1.1.4-Stufe11/per-Face-Farben/universelle Reparatur
  nicht durch obige Nachweise behaupten.

### Historisch: Teilstufe 11a/N20 Draft geprueft, damals 11b/11c offen (2026-10-09)

- Auftrag: Stufe 11 implementieren/pruefen; feste Teilstufen ausdruecklich
  erlaubt. **In diesem Chat 11a abgeschlossen, nicht gesamte Stufe 11.**
  11b Mesh und 11c X-Austausch nicht implementiert; keine vereinbarte Variante
  entfernt oder auf native Defaults reduziert. Stufen 1-10 nicht neu implementiert;
  vorhandenen Dirty-Worktree erhalten. Kein Release/Installation/Commit/Push/Tag.
- Fuenf neue MCP-Tools: draft_create_element, draft_edit_element,
  draft_create_array, draft_edit_array, draft_inspect. **187 registrierte Tools**,
  Bridge 0.11.0/Paket 0.1.0 unveraendert. Neue draft_ops.py nutzt native Draft-
  FeaturePython-Elemente/-Arrays und GUI-Executor, strikte diskriminierte Schemas,
  finite mm/Grad-Werte, Quaternion XYZW, explizite Dokument-/Name-Referenzen.
  Linie, offener/geschlossener Wire, Rechteck, Kreis/Bogen, Text/Custom-Label;
  nichtverschmolzene Ortho-XYZ-/Polararrays bis 1000 Instanzen. Vollstaendiger
  gleichartiger Spec-Ersatz beim Edit; Quellenaenderung propagiert. Vorhandene
  Loeschpfade wiederverwendet, keine Batch-Erweiterung und kein execute_python.
- Provenienz: schreibgeschuetzte MCPDraftKind/MCPDraftSource. Fehlende oder
  gewechselte Array-Base -> draft_reference_lost, keine stille Neuzuordnung.
  Nur selbst erzeugte Elemente fuer Edit/Inspect; Names statt UUIDs, identisch
  benannte Ersetzung nicht erkennbar. Kein kompletter Draft-Befehlskatalog.
  Capability draft_modeling nur GUI 1.1.1; andere Patches, auch 1.1.4 fuer Draft,
  ungeprueft. mesh_editing=false, STEP schema_selection=false unveraendert.
- Beruehrte Dateien: neue freecad_addon/freecad_ai_bridge/draft_ops.py;
  gui_executor.py (Draft-Aktivierung um Transaktion plus GUI-Update, bestehender
  Commit-vor-GUI-Update-Ablauf erhalten), security.py (Allowlist), operations.py
  (begrenzte Capability), src/freecad_mcp/server.py (Schemas/Wrapper),
  tests/test_tool_contracts.py, tests/freecad_integration.py, tests/mcp_smoke.py,
  tests/start_bridge.FCMacro (Draft-Trace, optionales TEMP-Ready-No-Clobber-Signal),
  docs/CONTRACTS.md, docs/COVERAGE.md, docs/ACCEPTANCE.md, Notice.md, diese Uebergabe.
- Frische Laufzeit: C:/Program Files/FreeCAD 1.1/bin/FreeCAD.exe, FreeCAD 1.1.1
  Build 20260414 (Git shallow), Commit 0108fd4b4850cc46e625b60e53cea7a7bbe69f8d,
  native Python 3.11.14; Host .venv/Scripts/python.exe Python 3.10.11/MCP 1.27.1.
  Workspace-Makro entfernt vorgeladene installierte Bridge-Module nur in eigener
  Instanz, laedt Workspace-Code. Eigener Port 9944, FREECAD_MCP_ALLOW_RAW_PYTHON=0.
  Native Report erfasst Modulpfade/Hashes; keine Standardinstallation geaendert.
- Host: `.venv\Scripts\python.exe -B -m unittest discover -s tests
  -p 'test_tool_contracts.py' -v`: **23/23, 2,870 s**. Danach gleiche discover-
  Ausfuehrung mit `-p 'test_*.py' -v`: **52/52, 2,977 s**. Beruehrte Python-
  Editordiagnosen ohne Fehler. Die finalen nachfolgenden Addon-Fixes sind nativ
  und per MCP geprueft; Host-Code seit diesem Gesamtlauf unveraendert.
  Abschliessendes `git diff --check` bestanden.
- Native Gesamtgate: Makro mit FREECAD_INTEGRATION_PATTERN=test_* und neuem
  FREECAD_INTEGRATION_REPORT unter TEMP, eigene PID 32036:
  **55/55, 22,974 s**, drei Draft-Tests plus gesamte Bestandsregression.
  Report `%TEMP%/freecad-stage11a-native-69b5030a163446bc964b14146a2a1099/full-final.json`;
  Startnachweis dort native-ready.json. Belegt Geometrie, XYZ 2x3x2=12,
  Polarachsen X/Y/Z, fremde Anwendungstransaktion in zweitem Dokument,
  App-/GUI-Aktivdokument-Isolation und lineares Undo.
- Reparierte lokale Fehler: Label nutzt ViewObject.FontSize, nicht TextSize;
  Arc ohne Wires darf nicht wegen all([]) als geschlossen gelten. Native
  Shape.BoundBox unterbegrenzt rotierten Kreis um ~0,01458 mm; optimalBoundingBox
  (False, False) besteht das unveraenderte analytische Gate. Native Draft-
  Arrayerzeugung versteckt die Quelle: alte Visibility innerhalb Transaktion
  restauriert. Erster Gesamtlauf **54/55, 23,212 s** fand genau diesen Fehler;
  unmittelbare Wiederholung test_stage11a_draft_native **1/1, 2,209 s**, dann
  finaler Gesamtlauf oben. Fruehere positive 3/3-Fokuslaeufe ersetzen das Gate nicht.
- Ein frueher MCP-Kandidatenlauf nach nativen Tests beobachtete falsche Wire-
  Undo-BBox trotz restauriertem Placement. Direkter nativer Trace-Test konnte
  das nicht reproduzieren; Ursache nicht bewiesen, kein angeblicher Proxy-Fix.
  Zwei saubere GUI-Kandidatenlaeufe und finaler frischer MCP-Doppelrun bestehen
  denselben strengen Undo-Geometriecheck. Fehlerartefakte/Traces bleiben TEMP.
  Bei Wiederauftreten genau dort einsteigen, keine Toleranzlockerung.
- **Finaler echter MCP-Nachweis:** alle nativen Test-/Trace-Variablen entfernt,
  neue TEMP-Konfiguration, Ready-PID 30616, gleiche Workspace-Bridge, kein
  nativer Testvorlauf. `.venv\Scripts\python.exe -B tests\mcp_smoke.py
  --stage11a-only`: **zweimal 182 Workflow-Aufrufe plus je zwei Cleanup-Aufrufe**,
  187 Tools, raw_python_enabled=false, draft_modeling=true, Version 1.1.1.
  Report `%TEMP%/freecad-stage11a-mcp-qwdw1ihe/report.json`, je Unterordner 1/2
  transcripts und FCStd. Eigene neue GUI-Konfiguration/Ready-Nachweis unter
  `%TEMP%/freecad-stage11a-final-gui-0e50e9f61eba487296ada522ddd31afd/`.
  Je acht Varianten, analytische Masse/Placement, gedrehtes Line-Quaternion,
  Ortho 6 und Polar 4, Anzahl-/Winkel-/Quellenedit, Undo/Redo, ungueltige
  Inputs/Quellen ohne Teilmodell, Base-Verlust/Undo, Loeschen/Undo, FCStd-Reopen
  und zweite Aenderung/Resave. Numerische Snapshots 1e-6 absolut/relativ gegen
  Rundungsrauschen, Struktur exakt; analytische Gates nicht abgeschwaecht.
- Cleanup: finale RPC-Dokumentuebersicht frisch `{documents: {}, active_document:
  None}`. Nur eigene PID 30616 beendet; danach Get-CimInstance meldet keine
  FreeCAD.exe, Get-NetTCPConnection keinen Listener 9944. Vorherige eigene
  Testinstanzen ebenfalls erst nach leerem Bestand beendet. TEMP-Nachweise
  erhalten. Naechster Chat muss Laufzeit/Verbindung/geladenen Stand neu pruefen.
- **Offene Gates unveraendert:** 11b N21 Mesh-Diagnose Facetten/Komponenten/BBox/
  Abschluss/Orientierung/Defekte, Duplikate/degenerierte Facetten, Normalen,
  begrenztes Lochschliessen, Shape->Mesh mit Toleranzen, geschlossenes Mesh->
  Shape/Solid mit Diagnose. Fehlende-Wand-Box reparieren, Nonmanifold ablehnen.
  11c I34/I35 und vollstaendiger X-Vertrag: STEP AP214/AP242 explizit mit mm,
  Labels/Farben/einfacher Linkstruktur; ASCII/binaer-STL mit absoluten linearen/
  angularen Toleranzen, OBJ-Import/-Export, planares DXF/SVG Line/Polyline/Circle/
  Arc. Kein Downgrade bei fehlender Option, kein Claim aufgrund Toolzaehlung.
- **Naechster konkreter Startauftrag:** 11b nach N21 und X/G-Vertrag beginnen.
  AGENTS.md, diese Uebergabe und lokale Mesh-Tests lesen; native Mesh-API im
  frischen eigenen FreeCAD verifizieren, dedizierte erlaubte Mesh-Operationen
  plus strikte MCP-Schemas implementieren. Enger missing-facet/Nonmanifold-Test,
  danach native Integration und zweimal echter MCP-Normalmodus mit Edit,
  Undo/Redo, Rollback, Datei-Roundtrip. Erst anschliessend 11c; Stufe 11 nicht
  abschliessen, bevor alle Formate/Optionen numerisch/strukturell belegt sind.
  Kein Start Stufe 12/CAM/BIM/FEM und keine Benutzerinstanz neu starten.

### Historisch: Stufe 10b/N19/A5 auch unter FreeCAD 1.1.1 abgenommen (2026-10-09)

- Auftrag: die noch offene 10b-Abnahme auf 1.1.1 ausfuehren und einen Startprompt
  fuer Stufe 11 liefern; Stufe 11 hier nicht beginnen. AGENTS.md, diese Uebergabe
  und lokale Vertrags-/Abnahmestellen gelesen; vorhandenen Dirty-Worktree erhalten.
- Laufzeit frisch ermittelt: `C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe`,
  FreeCAD 1.1.1 Build 20260414 (Git shallow), Commit
  `0108fd4b4850cc46e625b60e53cea7a7bbe69f8d`, native Python 3.11.14.
  Host `.venv\Scripts\python.exe`: Python 3.10.11/MCP 1.27.1/PyMuPDF 1.28.2.
  182 Tools, Bridge 0.11.0/Paket 0.1.0 unveraendert; kein neuer Release.
- Baseline ohne Codeaenderung: eigene PID 23436 auf 9943, native
  `FREECAD_INTEGRATION_PATTERN=test_stage10*` ueber `tests/start_bridge.FCMacro`:
  **5/5, 6,826 s**. Danach zwei Kandidaten-A5-MCP-Laeufe je 125 Aufrufe bestanden;
  Capability noch false wegen bisheriger ausdruecklicher 1.1.4-Whitelist.
  `%TEMP%/freecad-stage10b-111-native-937416af052f44ea848312f8307d92ad/focused.json`
  und `%TEMP%/freecad-stage10b-mcp-md5tsqvz/`. Kein Geometriefix erforderlich.
- Aenderungen: `freecad_addon/freecad_ai_bridge/operations.py` meldet
  techdraw_drawings nur bei GUI und exakt 1.1.1 oder 1.1.4; readiness und
  tested_versions nennen beide. `tests/freecad_integration.py` prueft diese
  Metadaten in bestehendem 10b-Nativtest; `tests/mcp_smoke.py --stage10b-only`
  verlangt positives Featureflag und aktuelle Version in tested_versions.
  Engster Check direkt nach Edit: reale get_capabilities-Funktion mit gemockten
  Runtime-Fakten fuer 1.1.1/1.1.4 true, 1.1.2/1.2.0 und GUI=false false bestanden.
- Host-Vollregression nach Edit:
  `.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_*.py' -v`:
  **51/51, 3,255 s**. Editordiagnosen fuer alle drei beruehrten Python-Dateien leer.
- Native Vollregression nach Edit: eigene neue PID 31580/Port 9943,
  `FREECAD_INTEGRATION_PATTERN=test_*`,
  `FREECAD_INTEGRATION_REPORT=%TEMP%/freecad-stage10b-111-native-937416af052f44ea848312f8307d92ad/full.json`,
  Start mit `tests/start_bridge.FCMacro`, `--user-cfg` und `--system-cfg` im
  gleichen eigenen TEMP-Verzeichnis: **52/52, 23,476 s**. JSON dokumentiert
  tatsaechliche 1.1.1-Laufzeit und geladene Workspace-Modulpfade/SHA256.
- Finale reine MCP-Abnahme: neue eigene PID 28928/Port 9943, keine
  FREECAD_INTEGRATION_REPORT/PATTERN gesetzt; frische TEMP-Konfiguration in
  `%TEMP%/freecad-stage10b-111-clean-1cfbddf87f694713b4fdc94913a70ffc/`.
  `FREECAD_TEST_PORT=9943`, `FREECAD_MCP_ALLOW_RAW_PYTHON=0`.
  `.venv\Scripts\python.exe -B tests\mcp_smoke.py --stage10b-only`:
  **zweimal 125 Workflow-Aufrufe plus je zwei sichere Cleanup-Aufrufe bestanden**,
  182 Tools, raw_python_enabled=false, techdraw_drawings=true, Version 1.1.1.
- A2/A5 unveraendert vollstaendig: First-angle Front/Top/Right, axialer Schnitt
  mit Bohrung, Flanschbohrungsdetail 2:1, A4/Schriftfeld 1:1. Sechs echte native
  References2D-Masse 60/8/20/8/48/44, Laenge 40->50 ergibt 58, Undo/Redo,
  Save/Close/Reopen, Dicke 8->9 ergibt 9/59. Radius 5 und Winkel 90 separat;
  Vorlage/Schnitt/stale Auswahl, identischer Objektzustand nach Negativrollback,
  Quelle/Topologie/Arbitrary/Typ/Messmodus, Fremdtransaktion und unveraenderte
  Export-SHA256 bei Overwrite-Ablehnung bestanden. Keine execute_python-Nutzung.
- Finale Artefakte: `%TEMP%/freecad-stage10b-mcp-ymvmje2o/{report.json,1/,2/}`:
  FCStd, PDF/SVG, getrennte drawing-pdf/svg.png, render-report.json und echte
  MCP-Transkripte. Beide Formate je eine A4-Seite; Papier 0,15 mm, alle fuenf
  Konturen mit 0,5 mm Toleranz numerisch geprueft. Alle vier finalen PNGs visuell
  kontrolliert: Pflichttexte/Masszeichen, Schnitt/Detail und Schriftfeld lesbar;
  keine gefundene Abschneidung oder Ueberlagerung von Pflichttexten.
- 10a-MCP-Regression auf derselben eigenen 1.1.1-GUI:
  `.venv\Scripts\python.exe -B tests\mcp_smoke.py --stage10a-only --stage10a-render`:
  **zweimal 46 Workflow-Aufrufe, PDF-/SVG-Rendergates bestanden**;
  `%TEMP%/freecad-stage10a-mcp-saoppng1/{report.json,1/,2/}`.
- Abschluss frisch bestaetigt: RPC `{documents: {}, active_document: null}`;
  nur eigene PID 28928 beendet und Exit abgewartet. **0 FreeCAD-Prozesse und
  0 Listener auf 9943**. Vorherige eigene PIDs ebenfalls erst mit leerem Bestand
  beendet. Keine Benutzerprozesse am Start, keine Benutzerdateien veraendert;
  Standardinstallation/-konfiguration unangetastet, TEMP-Artefakte erhalten.
- CONTRACTS/COVERAGE/ACCEPTANCE/Notice aktualisiert. Keine weiteren offenen
  10b-Pflichtgates auf 1.1.1 oder 1.1.4 im vereinbarten Umfang. Der untenstehende
  1.1.4-Nachweis ist vorherig, kein erneuter 1.1.4-Test in diesem Teilauftrag.
  Abschliessendes `git diff --check` bestanden; kein Commit/Push/Tag.
  Andere Patchversionen ungeprueft; Names statt UUID, konservativer Topologieschutz,
  keine universelle Blatt-/Layout-/Fertigungszusage oder harte Kernelabbruchgarantie.
- Naechster Startauftrag: Stufe 11 nach AGENTS.md, N20/N21, I34/I35 und
  X-Formatvertrag in ACCEPTANCE konkretisieren und implementieren/testen.
  Draft, Mesh und erweiterter Austausch; bei Bedarf feste Teilstufen 11a/11b/11c.
  Frische eigene Laufzeit/Verbindung pruefen, nicht Port oder Prozess dieses Chats
  voraussetzen. Stufe 12/CAM/BIM/FEM nicht starten, keine bereits abgenommene
  10b-Neuimplementierung. Keine Installation/Commit/Push/Tag ohne eigenen Auftrag.

### Historisch: Stufe 10/N19/A5 abgenommen unter FreeCAD 1.1.4 (2026-10-09)

- Auftrag: offenen Pflichtumfang bis Stufe 10 schliessen; keine Stufen 11/12,
  keine Veroeffentlichung oder Installationsaenderung. AGENTS, diese Uebergabe,
  CONTRACTS/COVERAGE/ACCEPTANCE/Notice gelesen. Historische Teilstatus der
  Inventarzeilen sind keine neuen Luecken in abgenommenen Stufen 1-9; I34/N21
  haben spaetere Austauschvarianten in Stufe 11. N19/10b/A5 waren offen und sind
  jetzt im vereinbarten Umfang abgenommen. Vorhandenen Dirty-Worktree erhalten.
- 182 Tools, Bridge 0.11.0/Paket 0.1.0 unveraendert. Sieben neue MCP-Wrapper in
  src/freecad_mcp/server.py: techdraw_create_projection_group/create_section/
  create_detail/list_geometry/create_dimension/create_annotation/create_leader.
  DrawingSelection erlaubt native Edge0/Vertex0; alte Modellselektion bleibt
  1-basiert. Schemas/Weiterleitung/Einheiten in tests/test_tool_contracts.py.
- freecad_addon/freecad_ai_bridge/techdraw_ops.py: native First-angle-Gruppe,
  orthogonaler Schnitt, Detail, echte projizierte References2D-Dimensionen fuer
  Laenge/Abstand/X/Y/Durchmesser/Radius/Winkel, Annotation und Leader.
  Quell-/Basis-/Leadernamen, Dimensionstyp und native Referenzen persistiert.
  Geordnete Geometrie-Rangsignatur erkennt Projektionsnachbarschaftsaenderung,
  keine automatische Index-Neuzuordnung. Arbitrary/Type/MeasureType-Manipulation
  abgewiesen. Native verlorene Referenzen bei gleichartigen umgeordneten Kreisen
  kontrolliert; native Kreismittelpunkt-Vertices statt fest codierter Indizes.
- Native Projektionskoordinaten unskaliert mit Y nach unten; Leaderpunkte sind
  lokale Papier-mm mit Y nach oben. Absolute Papierkoordinaten fuer Gruppenkinder
  und Dimensionen korrigiert. Manuelles Kindlayout deaktiviert AutoDistribute;
  Boundingbox-Inspektion teilt native Skalierung heraus. Native Detail-Clipkreis-
  Zugabe im Fixture 1 Prozent. Masszeichen und Schriftgroesse 3 mm; Lochkreis-
  FormatSpec hat nur Praefix plus nativen Zahlenplatzhalter, keinen festen Wert.
- gui_executor.py: list_geometry bleibt rein lesend (keine Auswahlrevision durch
  eigenen Recompute invalidieren), abgeleitete Modellansichten bei Mutationen/
  Undo/Redo nachfuehren. Export auch bei fremder globaler Transaktion in anderem
  Dokument ablehnen, deren ID/Dateien unveraendert. Bestehenden eigenen globalen
  Abschluss aus 10a weiterverwendet, keinen Besitzschutz umgangen.
- Native Regressionen in tests/freecad_integration.py: Ansichten/Detail/Scale,
  Diameter/Radius/Length/Angle/Parameteredit, typisierte Text/TextSize/WayPoints,
  gleichartige umgeordnete Referenzen, fremde aktive ID/Mutation/Export und
  10a-Rueckwaertskompatibilitaet. tests/mcp_smoke.py --stage10b-only enthaelt
  zweimal unabhaengigen A2/A5-Workflow samt separatem Radius-/Winkelfixture und
  festem lokalem PyMuPDF-Renderer; keine freie Codeausfuehrung als CAD-Ausweg.
- Host: `.venv\Scripts\python.exe -B -m unittest discover -s tests -p
  'test_*.py' -v`: **51/51, 3,502 s** nach funktionalem Fix. Nach finaler
  Capability-/Warntextkorrektur gezielt `-p 'test_tool_contracts.py' -v`:
  **22/22, 2,304 s**. Diese Zahlen sind aktuelle Laeufe, nicht alte 10a-Zahlen.
- Native Vollsuite: eigene frische PID 21364, Port 9942, Report-Env und
  tests/start_bridge.FCMacro mit FREECAD_INTEGRATION_PATTERN=test_*:
  **52/52, 66,479 s**. `%TEMP%/freecad-stage10b-native-full.json` enthaelt
  Laufzeit/Workspace-Modulpfade/SHA256. Nach funktionalen Fixes, vor abschliessend
  geaendertem Capability-/Warntext; kein erneuter voller 1.1.1-Test behauptet.
- Finale echte MCP-Abnahme: neue eigene PID 25708, kein nativer Testvorlauf,
  FREECAD_TEST_PORT=9942 und FREECAD_MCP_ALLOW_RAW_PYTHON=0.
  `.venv\Scripts\python.exe -B tests\mcp_smoke.py --stage10b-only`:
  **zweimal 125 Workflow-Aufrufe plus je zwei sichere Cleanup-Aufrufe bestanden**.
  Finale Capabilities: raw_python_enabled=false, techdraw_drawings=true, 182 Tools.
  Erste Verbindung an frische GUI war noch vor Bridge-Listen und scheiterte ohne
  CAD-Aufruf; danach Listener/PID belegt und unveraenderter Lauf erfolgreich.
- A2 parametrischer Flansch: Spreadsheet, vollstaendig bestimmte Revolutions-
  skizze, axialer Hole, Flansch-Hole und vierfaches Muster. Initialvolumen
  10144*pi. A5 A4 297x210 mm/1:1 mit ausgefuelltem Schriftfeld, drei orthogonalen
  Gruppenansichten, axialem Schnitt und Flanschbohrungsdetail 2:1. Sechs native
  Masse 60/8/20/8/48/44; Laenge 40->50 ergibt 58, Undo/Redo; Save/Close/Reopen;
  Dicke 8->9 ergibt 9 und 59. Radius 5/Winkel 90 separat. Vorlagenfehler,
  Schnittnormalenfehler, stale Auswahl, identischer Objektzustand nach Rollback,
  verlorene Quelle und Topologieaenderung, Manipulation von Arbitrary/Typ/Modus,
  Datei-SHA256 bei overwrite=false geprueft. Alle Referenzen nach Undo intakt.
- Finale A5-Artefakte: `%TEMP%/freecad-stage10b-mcp-27zfa7ex/report.json` und
  `{1,2}/` mit FCStd, drawing.pdf/svg, drawing-pdf/svg.png, render-report.json
  und MCP-Transkripten. Beide Formate je eine Seite, SVG valide/nicht leer,
  Papier innerhalb 0,15 mm PDF-Rundung, fuenf gedruckte Konturen binnen 0,5 mm
  Strichtoleranz numerisch bei 1:1 bzw. 2:1 geprueft. Alle vier finalen PNGs
  visuell kontrolliert; Pflichttexte/Masszeichen/Schnitt/Detail lesbar und nicht
  abgeschnitten oder ueberlagert. Frueherer Layoutfehltest wurde erhalten und
  korrigiert (AutoDistribute, Platzhalter FC-SC, Dimension/Schnittlabel).
- 10a-Regression danach auf derselben eigenen GUI:
  `.venv\Scripts\python.exe -B tests\mcp_smoke.py --stage10a-only --stage10a-render`:
  **zweimal 46 Workflow-Aufrufe, beide Renderer bestanden**.
  `%TEMP%/freecad-stage10a-mcp-mz6fqlyb/report.json` und `{1,2}/`.
- Laufzeit: FreeCAD 1.1.4 Build 20260928, Commit
  4fd3bf320d9566a27e60069fc8387448aaa3a094, native Python 3.11.14;
  `%TEMP%/freecad-audit114-portable/FreeCAD_1.1.4-Windows-x86_64-py311/bin/FreeCAD.exe`.
  Host .venv Python 3.10.11/MCP 1.27.1/PyMuPDF 1.28.2. Renderer nur lokale
  Testvoraussetzung, keine neue Serverabhaengigkeit. Kein Standardinstallations-
  update, Commit/Push/Tag oder Benutzerdateieingriff.
- Abschluss: per schreibgeschuetztem RPC `{documents: {}, active_document: null}`
  frisch bestaetigt, nur eigene PID 25708 beendet und deren Exit abgewartet:
  **0 FreeCAD-Prozesse, 0 Listener auf 9942**. Alle eigenen Testdokumente vorher
  sicher geschlossen; TEMP-Artefakte bleiben erhalten, kein Releasearchiv.
- Grenzen: 10b frisch nur auf 1.1.4 abgenommen; Capability true nur dort mit GUI.
  Names statt persistenten UUIDs, konservative Rangsignatur statt universeller
  Topologieidentitaet, keine allgemeine Ueberlappungs-/Blattqualitaetspruefung,
  Schriftfamilien koennen zwischen nativen Exportern abweichen, globaler Qt-Pool
  ohne harte Gesamtzeit-/Kernelabbruchgarantie. Keine Fertigungszusage.
- CONTRACTS/COVERAGE/ACCEPTANCE/Notice aktualisiert; N19/A5 abgeschlossen, keine
  offenen Pflichtgates fuer den vereinbarten Stufe-10-Umfang. Stufen 11/12
  bleiben offen und wurden nicht begonnen. Naechster Einstieg nur auf eigenen
  Auftrag: Stufe 11 nach N20/N21 und Formatvertrag konkretisieren, neue eigene
  Laufzeit pruefen. Nicht 10b erneut implementieren; Installation/Release nur
  nach separater Genehmigung.

### Historisch: Stufe 10a Gates bestanden (2026-10-09)

- Fortsetzung des unten dokumentierten unveroeffentlichten 10a-Stands.
  Vorhandenen schmutzigen Arbeitsbaum erhalten; kein Commit/Push/Tag und kein
  Update der Standardinstallation. Bridge-API 0.11.0/Paket 0.1.0 unveraendert,
  175 registrierte Tools. Nur eigene frische Portable-Prozesse auf Port 9941;
  zu Beginn keine Benutzer-FreeCAD-Prozesse vorhanden.
- Lokaler Ursachenbeweis: neue optionale `FREECAD_TRANSACTION_TRACE`-Spur im
  vorhandenen `tests/start_bridge.FCMacro`, ausschliesslich neue TEMP-Datei.
  Eigenschaftsaenderungen, native Transaktions-IDs und Oeffnungsstack erfasst.
  Fehltest `%TEMP%/freecad-stage10a-mcp-bsdh0i66/1/` reproduziert Quellen-Undo:
  `view_ops.undo -> doc.recompute()` oeffnet die alte `MCP: update_page`-ID 13.
  Ein leerer Dokument-Commit hatte den globalen Anwendungskontext nicht beendet.
  Spur `%TEMP%/freecad-stage10a-tx-106dce5a707d4322a5b4b063e4535386.jsonl`.
- Fix `freecad_addon/freecad_ai_bridge/transactions.py`: fremde Dokument-
  oder Anwendungstransaktion vor Mutation ablehnen. Beim eigenen open erfasste
  globale ID nach Commit/Rollback nur dann schliessen, wenn sie noch exakt
  dieselbe ist. Keine Uebernahme/Schliessung fremder IDs. Neue Regressionen in
  `tests/test_gui_executor.py` fuer leeren Commit/Rollback, globale Fremd-ID
  sowie gleichnamige ersetzte ID; FreeCAD-Mocks in `tests/test_batch.py` angepasst.
- Nach Transaktionsfix Quellen-Undo/Redo bestanden; naechster MCP-Test fand
  native Zentrierung beim `page.addView(view)`. Wunsch-X/Y jetzt danach setzen
  (`freecad_addon/freecad_ai_bridge/techdraw_ops.py`). Quellen-/Layout-Undo/Redo,
  PDF-Folgeaufrufe und sichere Close-Aufrufe bestehen nun im realen GUI-Loop.
- `operations.py`/TechDraw-Warnungen melden geprueften 10a-Teilumfang auf 1.1.4,
  keine alten Blockerzusagen; `techdraw_drawings=false` und volle A5 offen.
  CONTRACTS/COVERAGE/ACCEPTANCE/Notice aktualisiert, N19 bleibt teilweise.
- Finaler Hostlauf: `.venv\Scripts\python.exe -B -m unittest discover -s tests
  -p 'test_*.py' -v`: **50/50 bestanden, 2,657 s**. Betroffene Editordiagnosen
  ohne Fehler. `git diff --check` bestanden.
- Native Gesamtsuite: eigene PID 32108, `FREECAD_TEST_PORT=9941`,
  `FREECAD_INTEGRATION_PATTERN=test_*`, Report-Env und `tests/start_bridge.FCMacro`:
  **48/48 bestanden, 19,651 s**, einschliesslich 10a und vorheriger nativer
  Regressionen. Bericht `%TEMP%/freecad-stage10a-native-bf2a55bbe7fd49efa1652bf2cbb52227.json`
  mit Laufzeit/Workspace-Modulpfaden/SHA256; nach funktionalem Fix, vor der
  abschliessenden reinen Capability-/Warntextkorrektur. Keine frische 1.1.1-Abnahme.
- Finaler echter MCP-Normalmodus in neuer PID 29728 ohne nativen Vorlauf:
  `.venv\Scripts\python.exe -B tests\mcp_smoke.py --stage10a-only --stage10a-render`
  **zwei unabhaengige vollstaendige Laeufe bestanden, je 46 MCP-Aufrufe**.
  Quellen-/Layout-Undo/Redo, 60x40 -> 70x40 -> Reopen -> 70x45, Schriftfeld,
  FCStd-Save/Close/Reopen, fehlende Vorlage/ungueltige Richtung/Layout/Text,
  Negativrollback, Referenzverlust/Undo und PDF-/SVG-Overwrite-Schutz bestanden.
  Raw-Python false; kein execute_python oder freier CAD-Ausweg.
- Optionaler Render-Gate im bestehenden `tests/mcp_smoke.py`: PyMuPDF 1.28.2
  nur lokal in Host-.venv installiert, keine neue Server-/Projektabhaengigkeit.
  PDF/SVG je eine Seite, SVG-Titel, A4 297x210 mit 0,15 mm Papier-Rundungstoleranz,
  alle drei gedruckten Konturen mit Groesse/Lage und 0,8 mm Raster-/Strichbreiten-
  toleranz bestanden. Native PDF-Seite 842x595 pt = 297,039x209,903 mm.
  PNGs beider ersten Laeufe sowie finale PDF/SVG-Bilder visuell kontrolliert:
  Titelblock und drei getrennte Ansichten, keine Ueberdeckung.
- Finale Artefakte `%TEMP%/freecad-stage10a-mcp-eqzyan01/report.json` und
  `{1,2}/` mit FCStd, SVG/PDF, PNGs und MCP-Transkripten. Bericht enthaelt
  numerische Exportmessungen; vorheriger erfolgreicher Doppelrun ohne integrierten
  Renderer: `%TEMP%/freecad-stage10a-mcp-0mnw4x7s/`. TEMP ist kein Releasearchiv.
- Laufzeit frisch belegt: FreeCAD 1.1.4 Build 20260928, Commit
  `4fd3bf320d9566a27e60069fc8387448aaa3a094`, native Python 3.11.14.
  EXE `%TEMP%/freecad-audit114-portable/FreeCAD_1.1.4-Windows-x86_64-py311/bin/FreeCAD.exe`;
  Host `.venv/Scripts/python.exe`, Python 3.10.11/MCP 1.27.1.
- Abschluss: alle Testdokumente per safe close geschlossen, RPC-Lesepruefung
  bestaetigt `{}` Dokumentbestand. Nur eigene letzte PID 29728 beendet;
  danach frisch geprueft: **0 FreeCAD-Prozesse, 0 Listener auf 9941**.
  Keine Benutzerdateien/-sitzungen geaendert; TEMP-Artefakte bleiben erhalten.
- **10a unter dieser 1.1.4-Laufzeit abgenommen, nicht volle Stufe 10/A5.**
  Grenzen bleiben: namensbasierte Provenienz statt UUID, keine automatische
  Ueberlappungs-/Ganzblattvalidierung, globaler Qt-Pool-Wait ohne harte Gesamtzeit-
  oder Kernel-Abbruchgarantie; keine universelle Vorlagen-/Geometrieabnahme.
- Naechster Startauftrag: **Stufe 10b fortsetzen**, zunaechst native
  Projektionsgruppen/Schnitt/Detail lokal implementieren und sofort pruefen;
  dann modellgebundene Masse, Annotationen/Leader und vollstaendiges A5 mit
  A2-Flansch 48 -> 58 -> Reopen -> 59. Radius-/Winkelfixture nicht vergessen.
  Neue eigene Laufzeit/Verbindung herstellen; Stufen 11/12 nicht starten.

### Historischer Ausgangspunkt: 10a-MCP-Gates noch offen (2026-10-09)

- Auftrag: Stufe 10 TechDraw implementieren/verifizieren; bei zu grossem Umfang
  feste Teilstufen, keine Veroeffentlichung und keine Stufen 11/12.
  AGENTS/Notice/COVERAGE/ACCEPTANCE/CONTRACTS und vorherige Uebergabe gelesen.
- Frisch vor Implementierung: sauberer main; HEAD
  `762d4dc4a271551406b9fcda5582127fe299c780`, lokaler/remote main und gepeelter
  `bridge-v0.11.0` identisch. Keine FreeCAD-Prozesse/Bridge-Listener zu Beginn.
  Danach ausschliesslich eigene isolierte Portable-Instanzen auf Port 9940.
  Aktueller Teilstand ist uncommitted; kein Commit/Push/Tag, kein Installationsupdate.
- Sieben additive Tools (175 frisch registriert): `techdraw_list_templates`,
  `techdraw_create_page`, `techdraw_create_view`, `techdraw_inspect_page`,
  `techdraw_update_page`, `techdraw_set_layout`, `techdraw_export_page`.
  Neue `freecad_addon/freecad_ai_bridge/techdraw_ops.py`, Registrierung/Vertraege
  in `src/freecad_mcp/server.py`, Allowlist in `security.py`, Mutations-/Quellen-
  Projektionsabschluss in `gui_executor.py`, experimentelle Capabilities in
  `operations.py`. Bridge-API bleibt 0.11.0/Paket 0.1.0: kein Release behauptet.
- Native DrawPage/DrawSVGTemplate/DrawViewPart, echte Source-Verknuepfungen;
  `MCPSourceNames` prueft Verlust/Aenderung, aber keine UUID-Identitaet.
  Mitgelieferte Vorlage `ISO/A4_Landscape_TD.svg`; Templates in 1.1.4 liegen
  verschachtelt. Vertrauenswuerdige absolute SVGs mit expliziten mm-Massen
  unterstuetzt. Layoutmittelpunkt/positiver Massstab/Rotation und bekannte
  EditableTexts; keine automatische Ueberlappungs-/Ganzblattpruefung.
- Native exakte HLR ist im GUI asynchron. `_finish_projection` wartet intern
  zweimal bis 10 s auf den globalen Qt-Pool und verarbeitet Qt-Ereignisse ohne
  Benutzereingaben. Kein CoarseView-/Praeferenzfallback, keine harte Gesamtzeit-
  oder Kernel-Abbruchgarantie. Mutationen mit strukturierten Ansichten fuehren
  Quellen vor eigenem Commit nach. Fremdtransaktionen werden nicht uebernommen.
  Eine erfolglose Probe am bisherigen view_ops-Undo-/Redo-Pfad wurde zurueckgenommen.
- Export: native TechDrawGui-Ausgabe, absolute PDF/SVG-Pfade, Staging im Ziel-
  Elternordner, PDF-/XML-Grundvalidierung, No-Clobber-Hardlink bzw. ausdrueckliches
  os.replace. Datei- und Dokumentrollback getrennt; keine Fertigungs-/Zeichnungs-
  Qualitaetszusagen. Aktuelle Live-Grenze: PDF kann eine native Transaktion hinterlassen.
- Tests: `tests/test_techdraw.py` neu (2 Hosttests); Vertrags-/Forwarding-/Fehler-
  test in `tests/test_tool_contracts.py`; nativer fokussierter Test in
  `tests/freecad_integration.py`; `tests/start_bridge.FCMacro` berichtet Laufzeit,
  PID, Modulpfade und SHA256. `tests/mcp_smoke.py` hat `--stage10a-only` und
  den diagnostisch reduzierten `--stage10a-basic-only`. Bei Fehler wird der
  erste Lauf gestoppt; Transkript/failure.json bleiben trotz Cleanupfehlern.
- Finaler lokaler Lauf: `.venv\Scripts\python.exe -B -m unittest discover
  -s tests -p 'test_*.py' -v`: **47/47 bestanden, 2,545 s**. Betroffene Python-
  Editordiagnosen ohne Fehler. Keine neue native Gesamtsuite/1.1.1-/A1-A4-Regression.
- Finaler fokussierter nativer Lauf mit `FREECAD_TEST_PORT=9940`,
  `FREECAD_INTEGRATION_PATTERN=test_stage10a*` und Report-Env ueber
  `tests/start_bridge.FCMacro`: **1/1 bestanden, 1,627 s**. Belegt Seite/Vorlage,
  fehlende Vorlage/Rollback, Projektion, direkte Quellen-/Undo-/Redo-Masse,
  Layout, Source-Verlust sowie SVG/PDF/Overwrite. **Kein MCP-Abnahmeersatz.**
- Echter MCP-Normalmodus: `.venv\Scripts\python.exe -B tests\mcp_smoke.py
  --stage10a-basic-only` **fehlgeschlagen**, 31 Transkriptaufrufe inkl. Cleanup.
  Drei Ansichten/Schriftfeld, projizierte Masse 60x40 -> 70x40, FCStd-Reopen,
  zweiter Quellenedit -> 70x45 und PDF erreicht. Folgeexport und safe close
  liefern `transaction_conflict`; kein Doppelrun abgeschlossen.
- `.venv\Scripts\python.exe -B tests\mcp_smoke.py --stage10a-only`
  **fehlgeschlagen nach Quellen-Undo**, Folge-Update `transaction_conflict`;
  auch in frisch gestarteter Instanz ohne vorherigen nativen Harness reproduziert.
  Nach Undo muss Modell/Zeichnung 60x40 werden; safe close bleibt ebenfalls blockiert.
  Direkter nativer Test bestanden, echter GUI-Loop nicht: Ursache noch offen,
  keine pauschale Commit-/Abort-Uebernahme als vermeintlicher Fix.
- Artefakte ausserhalb Source: `%TEMP%/freecad-stage10a-native-final-9940.json`,
  `%TEMP%/freecad-stage10a-mcp-uxhffi8e/1/{mcp-transcript.json,failure.json,...}`
  und `%TEMP%/freecad-stage10a-mcp-3kv0hdd0/1/{mcp-transcript.json,failure.json,...}`.
  Native Modulpfad-/Hashvergleich mit aktuellem Workspace: keine Abweichung.
  TEMP-Berichte sind keine dauerhaften Releaseartefakte.
- Laufzeit: Portable FreeCAD 1.1.4 Build 20260928, Commit
  `4fd3bf320d9566a27e60069fc8387448aaa3a094`, native Python 3.11.14.
  EXE `%TEMP%/freecad-audit114-portable/FreeCAD_1.1.4-Windows-x86_64-py311/bin/FreeCAD.exe`.
  Host `D:/Proj/FreeCad/FreeCad_MCP_Server/.venv/Scripts/python.exe`, Python
  3.10.11/MCP 1.27.1. Raw-Python false; kein execute_python/CAD-Ausweg.
  Standardinstallation und Benutzer-FreeCAD/Dokumente unangetastet.
- Abschlussbereinigung: letzte eigene Instanz PID 31824 hatte ausschliesslich
  `MCP_Stage10a`. Wegen blockiertem safe close nur diesen eigenen Testprozess
  beendet; danach kein Listener auf 9940 und kein FreeCAD-Prozess sichtbar.
  Keine verbliebenen offenen Testdokumente; TEMP-Dateien/Reports erhalten.
  Naechster Chat muss eine neue eigene Laufzeit/Verbindung herstellen.
- **10a ist nicht abgenommen**, `techdraw_pages` experimentell mit Warnung,
  `techdraw_drawings=false`. Voller und reduzierter MCP-Lauf scheitern schon
  im ersten geplanten Durchlauf. Quellenverlust via MCP, Layout-Undo/Redo,
  spaetere SVG/Overwrite-Gates, PDF-Seitenzahl/Papier und gerenderte Sichtkontrolle
  bleiben unvollstaendig; keine A5-Gehaeuse-/Flansch-Zeichnungsbehauptung.
- 10b fehlt: Projektionsgruppen, orthogonaler Schnitt/Detail, modellgebundene
  Laengen/Abstands/Durchmesser/Radius/Winkelmasse, Annotation/Leader. Erst nach
  10a-Gate komplettes A5 auf A2 mit 48->58->59, sechs Massen und Exportabnahme.
- **Naechster Startauftrag:** frischen eigenen FreeCAD-Prozess/geladenen Stand
  verifizieren; den dokumentierten MCP-Quellen-Undo-/PDF-Transaktionsrest lokal
  untersuchen (native Auto-/Nachlauftransaktionen, GUI-Loop vs. direkter Harness).
  Fremdtransaktionsschutz erhalten, gezielte Regression und beide MCP-Doppelruns
  gruen machen; danach Sicht-/Seitenzahlpruefung und erst 10b. Nicht neu
  implementieren, nicht Stufe 11/12 oder Veroeffentlichung starten.

### Git-Veroeffentlichung 2026-10-09

- Freigegebener Auftrag: Auditverbesserungen und Ordnerbereinigung committen,
  pushen und taggen. Ziel: `origin/main`, annotierter Tag `bridge-v0.11.0`.
  Tag bezeichnet die Bridge-API; Paketversion bleibt unveraendert `0.1.0`.
- Vor Commit: Remote frisch abgefragt; main und origin/main synchron,
  keine vorhandenen Remote-Tags. Code-Diff und Loeschumfang geprueft.
- Aktueller Pre-commit-Lauf: `.venv\Scripts\python.exe -B -m unittest discover
  -s tests -p 'test_*.py'`: **44/44 bestanden, 2,329 s**. Keine neuen nativen
  FreeCAD-Laeufe; deren vorherige Auditnachweise bleiben unten getrennt.
- Publikationsgate: Commit und annotierten Tag gemeinsam ohne Force pushen;
  Remote-main und aufgeloester Remote-Tag muessen auf den lokalen Commit zeigen,
  danach muss der Arbeitsbaum sauber sein. Den aktuellen Publikationsstatus aus
  Git-Referenzen ermitteln, nicht aus historischen Prozess-/Testnotizen ableiten.
- Naechster fachlicher Einstieg nur auf Benutzerauftrag; keine neue Roadmap-
  Stufe oder Paketversionsaenderung durch diese Veroeffentlichung aktiviert.

### Ordnerbereinigung 2026-10-09

- Vorheriger Auftrag: Repository aufraeumen, danach auf separaten Auftrag sauber
  committen, pushen und taggen. Zum Abschluss der Bereinigung war noch kein
  Commit, Push, Tag oder Branch erstellt.
- AGENTS.md und den bisherigen separaten Ausbauplan zusammengefuehrt.
  Architekturregeln, alle 14 Stufen und Abnahmekriterien in Reihenfolge gegen
  den Originaltext geprueft; nur Markdown-Einrueckung normalisiert. Doppelte
  Plan-Datei entfernt und Verweise in README/Notice, Vertraegen, Matrix und
  Uebergaben bereinigt. Neue Regel: Testartefakte in temporaeren Verzeichnissen.
- Nach ausdruecklicher Freigabe auch alle CAD-Beispiele und Modellskripte
  entfernt: examples/ und models/, einschliesslich FEM-Debugskripten/-Ausgaben,
  Backups, Bildern, Exporten und MCP-Modellprotokollen. CAD-Dateien direkt in
  tests/ sowie den ausschliesslich beispielbezogenen Modellpruefer entfernt.
  Ordner-/CAD-Bereinigung: **104 Dateien, 18,51 MiB**, dazu drei Cache-Ordner;
  doppelte Plan-Datei und Modellpruefer separat entfernt. Historische Modell-
  und Testergebnisnotizen sind keine aktuell verfuegbaren Beispieldateien.
- Server/Add-on, regulaere lokale/native/MCP-Testharnesses, Konfiguration,
  LICENSE, Notice und Projektdokumentation erhalten; Audit-Code nicht
  zurueckgesetzt. .git, .venv, Installation, externe TEMP-Berichte und Benutzer-
  FreeCAD-Sitzungen nicht veraendert. .gitignore um FreeCAD-Backups und
  versehentlich direkt in tests/ abgelegte CAD-/Bildartefakte ergaenzt.
- Neuer Lauf nach Loeschung: `.venv\Scripts\python.exe -B -m unittest discover
  -s tests -p 'test_*.py' -v`: **44/44 bestanden, 3,016 s**. Lokale Markdown-
  Links in allen acht Projekt-Markdown-Dateien geprueft. Keine neuen nativen
  oder MCP-End-to-End-Laeufe fuer reine Dateibereinigung; Auditlaeufe unten
  bleiben getrennte, historische Nachweise dieses Chats.
- Naechster Einstieg: Git-Diff einschliesslich Auditverbesserungen und
  geloeschter Dateien pruefen, dann nach explizitem Auftrag committen/pushen.
  Paketversion, Release-/Tagname und Zielbranch vor Veroeffentlichung bewusst
  festlegen; 0.11.0 bezeichnet bisher die Bridge-API, nicht die Paketversion.

### Vorheriger MCP-Bestands-/Versionsaudit

- Vorheriger Auftrag: umfassender MCP-Bestands-/Versionsaudit. Begrenzte
  Verbesserungen umgesetzt und verifiziert; **keine Gesamtabnahme** und keine
  automatische Aktivierung der Stufen 10-12. Vollstaendiger Bericht:
  [Notice.md](Notice.md). Historische Modell- und Stufennotizen bleiben erhalten.
- Workspace-Bridge **0.11.0**, **168 Tools**: Patchversion im RPC erhalten;
  freie Python-Ausfuehrung standardmaessig gesperrt (`raw_python_disabled`),
  nur `FREECAD_MCP_ALLOW_RAW_PYTHON=1` im FreeCAD-Prozess aktiviert Entwicklercode.
  Capabilities wahrheitsgemaess; private/importierte RPC-Ziele liefern
  `rpc_not_allowed`. Keine Sandbox und keine Authentifizierung.
- Jobkapazitaet unter Lock vor Queue-Einreichung geprueft; abgelehnte Jobs
  starten nicht unerfasst. Grenzfall lokal getestet, kein neuer nativer 256-Job-
  Last-/Prozessverlustlauf. Registry bleibt prozesslokal, Cancellation queued-only.
- Neues `techdraw_scrub_edges` nutzt native 1.1.4-API, 1..256 revisionsgepruefte
  Kanten eines expliziten Dokuments, kopierte Eingangsgeometrie, statischer
  Part-Compound, SourceNames, Undo/Redo/Rollback. **Flaechenrandbereinigung,
  keine Vereinigung:** native API entfernt offene Endstuecke; Beispiel 0..10
  und 5..15 mm ergibt nur 5 mm. Schema/Warnung benennen dies. Keine Zeichnungsseite.
  Ohne native API `unsupported_feature`. Sources bleiben unveraendert.
- Harness bereinigt geladene Bridge-Module vor Workspace-Import; vorher konnten
  installierte alte Contracts 0.10.0 im Speicher bleiben. Kein installierter
  Code ersetzt, kein Benutzerprozess neu gestartet. `--audit-only` neu; native
  Harnesslaeufe brauchen keinen oeffentlichen Python-Opt-in.
- Finale lokale Suite **44/44, 2.897 s**. Native Gesamtsuite **47/47 unter
  1.1.4, 47.484 s**, **47/47 unter 1.1.1, 17.747 s**. Finaler echter MCP-Audit
  auf beiden Versionen bestanden. 1.1.4: Vertragslauf und Bestands-Smoke bestanden,
  Stage 8 A1/A2/A3 je zweimal 64/65/104 strukturierte Aufrufe, Stage 9 zweimal
  97 Assembly-Aufrufe. Host Python 3.10.11/MCP 1.27.1; keine gemeldeten Python-
  Editorfehler, vorhandene README-Markdownlint-Hinweise nicht bereinigt.
- FreeCAD **1.1.4 Build 20260928**, Commit
  `4fd3bf320d9566a27e60069fc8387448aaa3a094`, offizielles Portable-Archiv mit
  SHA256 `4828741fc91ee37fafcdb97a1abacb18b04ba451ac4372d9ff7a7349b36f4d6d`
  verifiziert. Installierte 1.1.1 Build 20260414 nicht geaendert. Release ist
  Wartung plus zwei Dateiverarbeitungs-Sicherheitsfixes; Upgrade empfohlen.
- Berichte: `%TEMP%/freecad-audit114-final-9936.json`,
  `freecad-audit111-final-9937.json`, `freecad-audit-mcp-v4iawbt_/report.json`
  (finaler 1.1.4-Audit), `freecad-audit-mcp-io51wr_9/report.json` (1.1.1),
  `freecad-stage8-mcp-f5k2_1c0/`, `freecad-stage9-mcp-qpmda9ei/`.
  Frueher `freecad-audit-mcp-lnhih2zp` hat ueberholte Beschriftung und ist nicht
  der finale Nachweis. Keine neuen dauerhaften Releaseartefakte im Repo abgelegt.
- Eigene alte Testprozesse nach leerem Status beendet. Finale 1.1.4 PID 6104/
  Port 9936 bei Abschluss bereits abwesend, Ursache unbekannt; nicht durch
  Agent beendet. Finale 1.1.1 PID 12032/Port 9937 nach leerem Status beendet.
  Portable Laufzeit/Reports bleiben TEMP; Standardinstallation unveraendert.
- TODO: N19 TechDraw-Seiten/Ansichten/Masse/PDF/SVG, N20 Draft, N21 Mesh,
  N22 Installation/Gesamtabnahme. Flags fuer fehlende Workflows explizit false.
  Grosse Modularisierung von server.py/MCP-Testworkflows **nur notiert, nicht
  durchgefuehrt**; getrennten Refactor mit unveraenderten Toolnamen/Schemas und
  Regressionstore planen. Prozessverlust und alle frueheren Stage-3-bis-7-MCP-
  Einzellaeufe wurden nicht separat wiederholt. FEM ausgeschlossen, CAM/BIM inaktiv.

Naechster Startauftrag:

> AGENTS.md, memory.md, Notice.md und docs/COVERAGE.md lesen.
> Repository ist bereinigt; Git-Ziel ist origin/main mit bridge-v0.11.0.
> Vor neuer Arbeit lokalen und entfernten Stand abgleichen. Keine weitere
> Ausbau-Stufe automatisch starten.
> Auditverbesserungen sind im beschriebenen Umfang verifiziert, nicht alle
> FreeCAD-Features implementiert. Stufe 10 nur auf expliziten Folgeauftrag.
> Neue Sitzung darf keine alte GUI/Verbindung/interpretierten Module voraussetzen.
> Vor Live-Tests eigene Prozesse/Ports/Workspace-Code kontrollieren; Benutzerdateien
> und -sitzungen erhalten. Installationsupdate separat bewusst durchfuehren.

## Historische Uebergabe Stufe 9

- Aktueller Auftrag: **Stufe 9 Assembly**. Status: **Abgenommen am 2026-10-01
  nach technischem Gate**. Stufen 7/8 blieben abgenommen; vorab war kein offener
  funktionaler Punkt nachzuimplementieren.
- Bridge 0.10.0, 167 Tools. Neu sind acht strukturierte native Assembly-Tools
  fuer Erzeugen, externe Komponentenlinks, Grounding, fuenf Gelenktypen,
  partielle Gelenkaenderung, diskrete Posen, Inspektion und statische Kollision.
  Exakte DoF werden konservativ nur fuer einen vollstaendig verbundenen,
  azyklischen Gelenkbaum mit genau einer Fixierung ausgegeben.
- Aktuell bestaetigt: **40/40 lokale Tests** in 3.290 s und **46/46 native
  GUI-Tests** in 20.115 s. Echter Stage-9-MCP-Doppelrun auf Port 9925: zweimal
  97 strukturierte Aufrufe, 167 Tools, A4 mit Zustaenden (0,0), (45,10),
  (90,20), Quellenedit 60->70 mit Undo/Redo, Negativrollback, Kollision,
  FCStd-Reopen, fehlender Quelle und STEP mit drei Solids/Verlustbericht.
  Bericht: `C:/Users/jakob/AppData/Local/Temp/freecad-stage9-mcp-91e_jjns/`.
- `--contracts-only` und `--stage8-a3-only` bestanden. Host Python 3.10.11,
  MCP 1.27.1, FreeCAD 1.1.1 Build 20260414. Keine Python-Editor-Diagnosen;
  bestehende README-Markdownlint-Hinweise bleiben ausserhalb Stufe 9.
- Benutzerprozess PID 21780/Port 9875 wurde nicht veraendert. Die agent-eigene
  Testinstanz PID 4460/Port 9925 wurde nach leerem Dokumentstatus beendet; ein
  neuer Chat darf Prozess, Verbindung oder geladenen Code nicht voraussetzen.

Aktueller Startauftrag fuer den naechsten Chat:

> Lies AGENTS.md, memory.md und docs/COVERAGE.md, ACCEPTANCE.md,
> CONTRACTS.md. Stufen 7 bis 9 sind technisch abgenommen; nicht erneut
> implementieren. Beginne Stufe 10 nur auf ausdruecklichen Benutzerauftrag.
> Vor Live-Tests Prozesse/Ports/Workspace-Code neu feststellen; bestehende
> Benutzersitzungen nicht neu starten oder beenden. FEM bleibt ausgeschlossen,
> CAM/BIM inaktiv.

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

> Lies AGENTS.md, memory.md, docs/COVERAGE.md und docs/ACCEPTANCE.md.
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
  dem inzwischen entfernten Modellskript models/cnc_router_mcp.py, kein execute_python,
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

## CNC-Profilmodell: separater Modellauftrag vom 2026-10-02

- Benutzer korrigierte die Bauweise von Holz auf item Profil 8. Bestaetigt:
  40x40 schwer, 40x80 fuer Y-Schienenauflagen und Portalbalken, Winkel plus
  Innenverbinder, MDF-Opferplatte, fahrendes Portal, 800x800 mm Arbeitsbereich,
  150 mm Z-Hub, sechs SBR20, vier SFU1605, vier Closed-Loop-NEMA23 mit 2 Nm
  und 1,5-kW-ER11-Spindel mit 80-mm-Gehaeuse.
- Installiertes Add-on war veraltet und blockierte unter anderem Capabilities,
  Batch und sichere Speicherung. Benutzer gab das Update ausdruecklich vor.
  Die vom Assistenten gestartete FreeCAD-Sitzung wurde beendet, Workspace-
  `freecad_addon` nach `%APPDATA%/FreeCAD/v1-1/Mod/FreecadAIBridge` gespiegelt
  und mit 17/17 Dateien, keinen Extras und identischen SHA256-Werten geprueft.
  Danach Bridge API 0.10.0 auf FreeCAD 1.1.1 bestaetigt. Kein `execute_python`
  und kein Modellierungsskript verwendet.
- Neues Dokument `CNC_Item_Profile_800x800`: Rahmen 1300x1300 mm, hintere
  Y-Motoren bis y=1376 mm, Hoehe bis 726 mm. Zuschnitt: 40x80 2x1300 und
  2x1220 mm; 40x40 5x1140, 3x1220 und 4x507 mm. Bettquertraeger und Stringer
  liegen auf getrennten Hoehenebenen. Portalbalken aus zwei 40x80-Profilen
  bildet 80x80; vier 40x40-Pfosten stehen auf zwei 15-mm-Fussplatten.
- Hardwarehuellen: SBR20 Y 2x1200, X 2x1100, Z 2x400 mm und zwoelf Wagen;
  SFU1605 Y 2x1200, X 1100, Z 400 mm; vier 57-mm-NEMA23; zwei gefraeste
  80-mm-Spindelklemmen. Gruppen und natives Spreadsheet
  `ITEM_BOM_and_Parameters` mit Zuschnitt-, Kaufteil- und Verbindungsliste.
- Verifikation: beide grossen Geometriebatches atomar erfolgreich; alle
  ausgegebenen Endkoerper gueltig. Acht kritische Rahmen-/Portalverbindungen
  per `check_interference` jeweils `contact`, 0 mm Abstand und exakt 0 mm^3
  Schnittvolumen. Isometrische 1400x1000-Ansicht visuell kontrolliert, nicht
  leer oder geclippt. Final gespeichert mit `modified=false` und
  `pending_transaction=false`. STEP exportierte 68 sichtbare Endkoerper.
- Artefakte: `examples/CNC_ITEM_Profile_800x800.FCStd` (111292 Bytes beim
  ersten finalen Save) und `examples/CNC_ITEM_Profile_800x800.step`.
  Vorheriges Holzmodell blieb als Vergleich unangetastet.
- Grenzen: Profile sind vereinfachte massive Lieferantenhuellen ohne Nutdetail;
  konkrete item-Artikelnummern, Verbinderbohrungen, Winkel-/Schraubenpositionen,
  SBR20- und Lagerbock-Lochbilder, Kupplungen, Endschalter, Schleppketten,
  Schaltschrank, Schutzumhausung, Absaugung und Festigkeitsnachweis bleiben vor
  Fertigung zu detaillieren. Keine Fertigungs- oder Maschinensicherheitsfreigabe.

### Korrektur und aktueller Endstand vom 2026-10-02

- Der oben beschriebene vereinfachte Neuaufbau wurde vom Benutzer verworfen.
  `examples/CNC_ITEM_Profile_800x800.FCStd` wurde durch eine professionelle,
  aus `examples/CNC_SBR20_1200.FCStd` abgeleitete Konstruktion ersetzt. Die
  Referenzdatei selbst blieb unveraendert. Modellierung ausschliesslich ueber
  strukturierte MCP-Werkzeuge; kein `execute_python` und kein Modellierungsskript.
- Beibehalten wurden der detaillierte Profilrahmen, fahrendes Portal, Tisch,
  sechs SBR20-Fuehrungen, Wagen, Seitenwangen, Schleppketten und die vorhandene
  Lager-/Traegerarchitektur. X und die alte mittige Y-Spindel wurden von d20 auf
  d16/SFU1605 geaendert; die mittige Y-Einheit ist ausgeblendet und durch zwei
  seitliche SFU1605-Antriebe ersetzt. Vier sichtbare Closed-Loop-NEMA23-Huellen
  mit 2 Nm, Motorplatten, Wellen und Kupplungen wurden ergaenzt.
- Die Makita-65-mm-Einheit wurde parametrisch durch eine 1,5-kW-ER11-Spindel
  d80x240 und zwei Split-Klemmen 120x110x30 mit 80,2-mm-Bohrung ersetzt. Beide
  Klemmen, Spindel sowie X/Y-Spindeln bestanden `part_validate` als geschlossene,
  gueltige Solids ohne Diagnosen; Dokument-Recompute erfolgreich.
- Isometrische 1400x1000-, Front- und Draufsicht wurden visuell kontrolliert:
  professioneller Referenzaufbau erhalten, Arbeitsraum frei, Motoren ausserhalb
  des Arbeitsraums, Spindel mittig. Finaler Save: 1002403 Bytes,
  `modified=false`, `pending_transaction=false`, Objektzustaende Up-to-date.
  STEP ueberschrieb `examples/CNC_ITEM_Profile_800x800.step` und exportierte
  282 sichtbare Endobjekte; erwarteter Verlust von Featurehistorie/Constraints.
- Nach Benutzerhinweis wurden ueberlappende Verbindungen konstruktiv korrigiert:
  Front- und Heckprofil von 1280 auf 1120 mm lichte Laenge getrimmt und zwischen
  die 80-mm-Seitenprofile auf Stoss gesetzt. Alle vier vorherigen Eckkollisionen
  von je ca. 75008 mm^3 sind jetzt Kontakt mit exakt 0 mm^3 Schnittvolumen.
  Vier verschmolzene L-Eckwinkel 80x80x60x8 liegen auf den freien Innenflaechen;
  alle acht Winkel-zu-Profil-Pruefungen ergaben Kontakt und 0 mm^3 Interferenz.
- Beide Y-Antriebe wurden nach innen und vor den Rahmen versetzt; Motoren sind
  15,24/33,05 mm von den Seitenprofilen getrennt, Motorplatten liegen nur an.
  Der X-Motor wurde vor den linken Portalsteifer gesetzt: 10 mm Freigang,
  Flanschkontakte 0 mm^3, Welle 3,65 mm frei. Sechs Y-Lager-/Muttertraeger
  erhielten echte d20/d22-Bohrungen; Spindelfreigang 2/3 mm und 0 mm^3
  Schnittvolumen. Recompute und abschliessende Isometrie erfolgreich.
- Die fuenf Bettquertraeger beruehrten Platte und Seitenrahmen zwar mit 0 mm
  Abstand, lagen am Rahmen aber nur an den oberen Innenkanten an. Zehn
  verschmolzene 8-mm-L-Auflagewinkel verbinden nun jedes Traegerende flaechig
  mit dem jeweiligen Seitenprofil und stuetzen den Traeger von unten. Alle
  zwanzig Winkelkontakte sind ohne Durchdringung; die 28-mm-Auflagezungen
  halten 4,17 mm Abstand zur linken und 24,06 mm zur rechten Y-SFU1605.
  Platte und alle fuenf Traeger bleiben untereinander in exaktem Kontakt.
- Der Entwurf ist weiterhin ein belastbares Konzept, keine Fertigungs- oder
  Maschinensicherheitsfreigabe. Konkrete Lieferantenteile, Lochbilder,
  Passungen, Endschalter, Schutz, Absaugung und Festigkeitsnachweis bleiben offen.

## Lenkbares Antriebsrad: separater Modellauftrag vom 2026-10-02

- Referenz war das achtsekündige Video `f4XyY6Ksu4k`, Titel "Drivable and
  steerable wheels". Wegen blockiertem Videostream wurden Vorschaubild sowie
  YouTube-Zeitmarken bei 25/50/75 Prozent ausgewertet. Sichtbar sind ein um die
  Hochachse schwenkbarer Radtraeger, ein drehbares Laufrad, Lenkritzel und
  Kegelradantrieb unter zwei Motorhuellen.
- Modellierung ausschliesslich mit strukturierten MCP-Werkzeugen, ohne
  `execute_python` oder Modellierungsskript. Fuenf gespeicherte Quelldokumente
  bilden Grundplatte, Lenktraeger, Rad, Lenkritzel und Antriebsritzel; die
  Assembly enthaelt fuenf externe `App::Link`-Komponenten.
- Native Kinematik: Grundplatte geerdet, vier Revolutgelenke fuer Lenkachse,
  Radachse, Lenkritzel und Antriebsritzel. Verifizierter Zustand nach Endpose:
  vier exakte unabhaengige Freiheitsgrade, alle Quellen aufgeloest, Solver
  `Up-to-date`. Endpose: Traeger 35 Grad eingeschlagen, Rad und beide Ritzel
  passend diskret weitergedreht.
- Speicher-Roundtrip bestanden: Assembly sicher geschlossen, erneut geoeffnet,
  alle Komponenten, Gelenke, Limits und Posen erhalten. Final `modified=false`,
  `pending_transaction=false`; isometrische Ansicht nach `fit_view` vollstaendig
  sichtbar. STEP exportierte fuenf Endkomponenten mit erwartetem Verlust von
  Gelenken, Constraints und Featurehistorie.
- Artefakte unter `examples/Lenkbares_Antriebsrad/`: fuenf Quellen-FCStd,
  `Lenkbares_Antriebsrad_Assembly.FCStd` und
  `Lenkbares_Antriebsrad_Endpose.step`.
- Bereitschaftsgrenze: Es gibt kein strukturiertes Zahnrad-Mate fuer gekoppelte
  Uebersetzungen und keine Zeitachsen-Animation. Die vier Drehteile sind native
  Gelenkkomponenten, ihre im Video entsprechende Endstellung wurde jedoch als
  berechneter diskreter Bewegungszustand gesetzt. Zahnflanken und Motorhuellen
  sind vereinfachte Funktionsgeometrie, keine Fertigungskonstruktion.

### Detailkorrektur und aktueller Endstand vom 2026-10-02

- Der vereinfachte Aufbau unter `examples/Lenkbares_Antriebsrad/` bleibt als
  Vergleich unangetastet. Auf Benutzerkorrektur entstand separat die sichtbar
  detaillierte Rekonstruktion unter `examples/Lenkbares_Antriebsrad_Detail/`:
  Reifen mit Profil, Felge mit acht Speichen, Gabelrippen, Lager, Wellen,
  Stellringe, Schraubdetails und abgestufte Motorhuellen.
- Fuenf gespeicherte Quelldokumente liefern Grundplatte/Motoren, Lenktraeger,
  Radgruppe, Lenkritzel und Antriebsritzel. Die native Assembly enthaelt neun
  aufgeloeste externe Komponentenlinks: drei Grundkomponenten, Lenktraeger,
  Felge, Reifen, Radkegelrad und beide Ritzel.
- Nach Benutzerhinweis wurden die angesetzten Quaderzaehne vollstaendig
  ersetzt. Der Lenkkranz besitzt jetzt ein integriertes 60-Zahn-Profil, das
  gruene Lenkritzel ein integriertes involutenaehnliches 10-Zahn-Profil mit
  schmalen Spitzen und 20-Grad-Flankenstuetzpunkten; Achsabstand 112 mm.
  Radkegelrad und rotes Antriebsritzel sind integrierte, verjuengte 16-/12-
  Zahn-Loftkoerper statt aufgesetzter Stummel. Alle vier Zahnrad-Endobjekte
  bestanden `part_validate`: gueltig, geschlossen, je genau ein Solid und
  ohne Diagnosen. Die internen Bestandsnamen der Ritzel blieben fuer stabile
  externe Links unveraendert.
- Kinematik verifiziert: Grundplatte geerdet; zwei feste Motorverbindungen,
  zwei feste Radgruppenverbindungen und vier Revolutgelenke fuer Lenktraeger,
  Rad, Lenkritzel und Antriebsritzel. `assembly_inspect` meldet acht Gelenke,
  exakt vier unabhaengige Freiheitsgrade, `Up-to-date` und keine Warnungen.
- Phasenversuche mit `solve:false` reduzierten die statische Zahnueberdeckung,
  machten nach Reopen jedoch beide Ritzel-Revolutgelenke `Invalid` und wurden
  deshalb verworfen. Die solverguelige Sicherung vom 2026-10-02 19:07:49 wurde
  ueber die Hauptdatei gespeichert. Der anschliessende Hauptdatei-Roundtrip
  bestaetigte neun aufgeloeste Links, acht aktive Gelenke, vier exakte DoF,
  `Expanded`/`Up-to-date`, 28 Objekte `Up-to-date`, keine Warnungen oder
  invaliden Zustaende sowie `modified=false` und `pending_transaction=false`.
- Finale Unter- und Isometrieansicht mit 1200x900 Pixeln wurden visuell
  kontrolliert; die 60/10-Lenkpaarung und beide verjuengten Kegelraeder sind
  sichtbar, das Modell ist nicht leer oder geclippt. STEP wurde aus allen neun
  Komponenten neu exportiert; erwarteter Verlust von Gelenken, Constraints
  und Featurehistorie.
- Artefakte: fuenf Quellen-FCStd,
  `Lenkbares_Antriebsrad_Detail_Assembly.FCStd` (23979 Bytes) und
  `Lenkbares_Antriebsrad_Detail_Endpose.step` (1039630 Bytes). Die verworfenen
  PhaseProbe-Dateien wurden entfernt. Die Haupt-Assembly ist nach dem
  bestandenen Roundtrip geoeffnet. Weder `execute_python` noch ein Neustart
  der bestehenden FreeCAD-Sitzung wurden verwendet.
- Verbleibende Grenze: Mangels strukturiertem Zahnrad-Mate und Zeitachse sind
  die Uebersetzungen diskrete Posen. Der solverguelige Original-Phasenstand hat
  eine begrenzte statische Zahnueberdeckung; eine optisch guenstigere freie
  Phasenverschiebung wird nicht gegen ungueltige native Gelenke eingetauscht.
  Das Modell ist eine detailreiche visuelle und kinematische Rekonstruktion,
  keine masshaltige Fertigungsfreigabe.

## Stufenstatus

| Stufe | Thema | Status |
| --- | --- | --- |
| Basis | Vorheriger Audit, Reparaturen und Demo | Historisch umgesetzt und getestet |
| 1 | Abdeckungsmatrix und Abnahmevertrag | Abgenommen am 2026-09-16; Umfang einschliesslich D1-D5 bestaetigt |
| 2 | MCP-Vertraege und Infrastruktur | Abgenommen am 2026-09-16; 28 lokale/24 CAD-Tests und beide MCP-Laeufe bestanden |
| 3 | Dokumente, Eigenschaften, Parameter | Abgenommen am 2026-09-16; 30 lokale/28 CAD-Tests, zweifacher strukturierter MCP-Lauf und Bestandsregression bestanden |
| 4 | Geometrieauswahl, Messung, Rueckmeldung | Abgenommen am 2026-09-16; 4a/4b, 32 lokale/33 CAD-Tests, zweimal 113 MCP-Aufrufe und Bild-/Bestandsregression bestanden |
| 5 | Sketcher | Abgenommen am 2026-09-17; 33 lokale/36 native GUI-Tests, zweimal 52 MCP-Aufrufe und Bestandsregression bestanden |
| 6 | PartDesign | Abgenommen am 2026-09-29; N10-N13, 34 lokale/42 native Tests, zweifacher MCP-Lauf und Bestandsregression |
| 7 | Part und Flaechen | Abgenommen am 2026-10-01; N14-N15, finite Quader-Gap-Probe, 45 native Tests und zweifacher MCP-Lauf bestanden |
| 8 | Auftraege und mechanischer Gesamtworkflow | Abgenommen am 2026-10-01; N16-N17, A1-A3 zweimal, Timeout/Prozessverlust und Austausch-Roundtrips bestanden |
| 9 | Assembly | Abgenommen am 2026-10-01; N18/A4, alle fuenf Gelenktypen, zweifacher MCP-Lauf und Regression bestanden |
| 10 | TechDraw | Nicht begonnen |
| 11 | Draft, Mesh, Austausch | Nicht begonnen |
| 12 | Gesamtabnahme und Betriebsmodus | Nicht begonnen |
| 13 | CAM | Optional; nicht freigegeben |
| 14 | BIM/Arch | Optional; nicht freigegeben |

Zulaessige Statuswerte fuer die Fortfuehrung: Nicht begonnen, In Arbeit,
Blockiert, Implementiert aber nicht vollstaendig geprueft, Abgenommen.

## Stufe 7: Teilprotokoll vom 2026-09-29

Umgesetzt in `part_ops.py`, `server.py` und `schema.py`: Wire aus Kanten, Face
mit robust orientierten Loechern, lineare Extrusion, Achsrevolution, Loft,
Sweep, Shell und Solid; Section und `BOPTools.SplitAPI`-Split; planarer
2D-Offset und 3D-Offset; lesende Validierung mit Topologie-/Volumenbericht,
Refine, Sewing und begrenztes Shape-Fix. Erwartete Solids muessen gueltig sein,
genau einen Solid und positives Volumen besitzen. Boolean-Ergebnisse liefern
Qualitaetsberichte. 16 MCP-Tools verwenden strikte Enums, Listengrenzen,
Feldmetadaten und dokumentierte mm/Grad-Einheiten. Capabilities benennen die
Grenzen; Bridge-API 0.8.0, insgesamt 155 Tools.

Verifikation:

- Lokal final `python -m unittest discover -s tests -p "test_*.py" -v`:
  36/36 in 4.221 s; `py_compile`, Editor-Diagnosen und `git diff --check` sauber.
- Native Vollsuite auf frischer FreeCAD-1.1.1-Instanz: 44/44 in 15.200 s;
  Bericht `C:/Users/jakob/AppData/Local/Temp/freecad-stage7-full-final2-a96d7d02-ced1-4afa-a7d2-1723e9e8d6c6.json`.
- Gezielte native Stufe-7a-/7b-Laeufe zuvor je 1/1 in 0.656/0.786 s.
- Echter MCP-stdio-Stufe-7-Doppelrun auf Port 9910: 155 Tools, zweimal 29
  Aufrufe, Extrusion/Loft je 125.6637061435917 mm^3, FCStd save/reopen, STEP,
  Negativfall und Cleanup bestanden; Bericht und Artefakte unter
  `C:/Users/jakob/AppData/Local/Temp/freecad-stage7-mcp-w3y3vvz7/`.
- Regression auf Port 9911: `--contracts-only` erfolgreich; `--stage6-only`
  zweimal 29 Aufrufe mit unveraenderten Housing-/Flanschvolumina; Legacy-Smoke
  mit Part-Fillet, Messen, Undo/Redo, STEP/STL/OBJ und MCP-Bild erfolgreich.

N15-Abschluss am 2026-10-01: natives `sewShape` schloss den endlichen Gap nicht.
`sew_faces` besitzt deshalb einen eng begrenzten Fallback nur fuer sechs
planare, nahezu rechteckige, achsparallele Quaderflaechen. Ein 0,005-mm-Gap
bleibt bei 0,001 mm offen und ergibt bei 0,01 mm genau einen gueltigen
1000-mm^3-Solid; `healing_mode` macht den Pfad sichtbar. Die GUI-Vollsuite
bestand 45/45, Stage 7 ueber MCP zweimal 29 Aufrufe. Keine allgemeine
Gap-/Shape-Heilung zugesagt.

## Stufe 9: Abschlussprotokoll vom 2026-10-01

- `assembly_ops.py` implementiert native `Assembly::AssemblyObject`- und
  `JointGroup`-Workflows, dokumentuebergreifende `App::Link`-Komponenten mit
  erhaltenem Quellplacement, GroundedJoint sowie Fixed, Revolute, Slider,
  Cylindrical und Ball. Relative DoF: 0/1/1/2/3.
- Persistente Gelenkreferenzen verwenden komponentenverwurzelte
  `PropertyXLinkSub`-Werte. Limits und Offset-Edits bleiben bei partiellen
  Aenderungen erhalten. XYZ-Euler wird korrekt auf FreeCADs Z/Y/X-Konstruktor
  abgebildet. Eine zweite Fixierung im bereits fixierten aktiven Gelenkbaum
  liefert `assembly_unsolved` und rollt zurueck.
- A4 verwendet drei gespeicherte Quelldokumente plus Assembly. Normale
  Zustaende (0 Grad/0), (45 Grad/10), (90 Grad/20) sind innerhalb G und ohne
  Interferenz; der bewusste Kollisionszustand liefert positives Volumen.
  Arm 60->70 aktualisiert den Link und besteht Undo/Redo. Reopen erhaelt Links,
  Gelenke, Limits und Placements; fehlende Armdatei ergibt `resolved=false`.
  Nach Reopen wird Hub 15 gespeichert und STEP mit genau drei gueltigen Solids
  importiert. Der Export meldet Gelenk-/Constraint-/Featurehistorienverlust.
- Verifikation: 40/40 lokale Tests; 46/46 native GUI-Tests; Stage 9 zweimal
  mit je 97 MCP-Aufrufen. Bericht und Artefakte unter
  `C:/Users/jakob/AppData/Local/Temp/freecad-stage9-mcp-91e_jjns/`.
  `--contracts-only` und `--stage8-a3-only` bestanden. Geaenderte Python-Dateien
  ohne Editor-Diagnosen; bestehende README-Markdownlint-Hinweise unveraendert.
- Grenzen: DoF exakt nur fuer einen fixierten verbundenen azyklischen Baum;
  diskrete Bewegung und statische BRep-Kollision, keine Dynamik-/Sicherheits-
  oder Fertigungszusage. STEP erhaelt keine Gelenke. Standardinstallation und
  Benutzer-FreeCAD wurden nicht veraendert.

Naechster Einstieg nur auf neuen Auftrag: Stufe 10 TechDraw nach N19/A5. Erst
Prozess/Port und geladene Workspace-Version neu pruefen; keine alte Verbindung
oder laufende Testinstanz voraussetzen.

## Stufe 8: Abschlussprotokoll vom 2026-10-01

- A1: ein PartDesign-Body mit voll bestimmten Outer-/Inner-Profilen und
  Spreadsheet-Expressions; Volumen 32088, nach L=100 38328, nach Reopen/t=4
  49536 mm^3. t=26 und Zyklus rollen zurueck; Undo/Redo und FCStd/STEP/STL
  inklusive STEP-Solid-/Volumen- und STL-Importpruefung bestanden.
- A2: voll bestimmtes Revolutionsprofil, axiale Bohrung und vierfaches
  Polarmuster; Volumen 10144*pi bzw. 10984*pi, Negativmuster und stale Auswahl
  ohne Mutation, save/reopen, Pitch 22->23 und Austausch-Roundtrip bestanden.
- A3: fuenf getrennte Endsolids, g=30/45/35, exakte Volumina,
  Kontakt/Interferenz und 0,5-mm-Spindelspiel; g=-1 und fehlendes Dokument
  rollen kontrolliert ab. Job-Reconnect erzeugt keine Komponente doppelt.
  FCStd, STEP mit einem Fuenf-Solid-Compound, fuenf STL-Reimports, Farben und
  isometrisches PNG bestanden.
- Finaler Doppelrun unter
  `C:/Users/jakob/AppData/Local/Temp/freecad-stage8-mcp-w98psl07/`: je Runde
  A1 64, A2 65, A3 104 Aufrufe; beide Runden erfolgreich. N16-Timeout und
  Prozessverlust separat mit `tests/job_process_loss.py` bestanden.
- Regression: 39/39 lokale Tests; 45/45 native GUI-Tests; Stage 7 zweimal,
  Stage 6 zweimal und `--contracts-only` erfolgreich; Editor-Diagnosen und
  `git diff --check` sauber. Standardinstallation blieb unveraendert.

## Stufe 6: Abschlussprotokoll vom 2026-09-29

Umgesetzt in `partdesign_ops.py`, `server.py` und `schema.py`: native Datum-
ebene/-achse/-punkt mit Placement, AttachmentOffset und revisionsgeprueftem
Support; Pad/Pocket-Endbedingungen und Seiten; Revolution/Groove mit Datumachse
und zwei Winkeln; Pipe-Kanten, Standard/Frenet und drei Transitions; Hole-
Senkungen/Gewindemetadaten; ungleiche Chamfer, Thickness-/Draftoptionen;
Mehrfachoriginale, native MultiTransform-Ketten und begrenzte Feature-/Profil-
bearbeitung. Revisionstokens werden vor jeder Mutation aufgeloest. Erfolgreiche
PartDesign-Features muessen genau einen verbundenen Solid liefern. Capabilities
und zentrale Feld-/Einheitenmetadaten sind auf Bridge 0.7.0 aktualisiert.

Verifikation:

- `python -m unittest discover -s tests -p "test_*.py" -v`: 34/34 in 3.900 s.
- Native Vollsuite auf frischer FreeCAD-1.1.1-Instanz: 42/42 in 16.630 s;
  Bericht `C:/Users/jakob/AppData/Local/Temp/freecad-stage6-full-latest-3a9ba764-152e-496f-8a6f-b0a90c52e673.json`.
- Sechs gezielte Stufe-6-Nativtests inklusive Ein-Solid-Pruefung: 6/6 in
  3.637 s; Bericht `C:/Users/jakob/AppData/Local/Temp/freecad-stage6-solid-final-97ee210b-8666-4f02-a992-12a6879b6adf.json`.
- Echter MCP-stdio-Doppelrun auf Port 9904: 139 Tools, zweimal 29 Aufrufe,
  Housing 6552.296425984978 mm^3, Flansch 17592.918860102844 mm^3; FCStd und
  STEP unter `C:/Users/jakob/AppData/Local/Temp/freecad-stage6-mcp-xmoi7bbm/`.
- Aktuelle Regressionen bestanden: `--contracts-only`; `--stage5-only` zweimal
  52; `--stage4-only` zweimal 113 auf frischer Instanz; `--stage3-only` zweimal
  121; Legacy-Smoke. Ein erster Stufe-4-Lauf auf einer vorbenutzten Instanz
  verlor nach Capture das aktive Dokument; die Wiederholung auf frischer
  Instanz bestand und Produktionscode fuer View/Geometry wurde nicht geaendert.
- Editor-Diagnosen fuer alle geaenderten Python-Dateien: keine Fehler;
  `git diff --check`: bestanden.

Grenzen: Das Stufe-6-Fixture ist das PartDesign-Teilgate und nicht der komplette
A1/A2-Gesamtworkflow aus Stufe 8. Variable Mehrprofil-Pipes, modellierte
Gewindehelix und beliebige Feature-Propertybearbeitung sind nicht zugesagt.
Standardinstallation/MCP-Registrierung blieben unveraendert. Alle vorhandenen
unversionierten Modell-/Beispieldateien wurden erhalten. Finale eigene Bridge
PID 24692/Port 9905 meldete `documents={}` und `active_document=null` und
wurde danach beendet.

Naechster Einstieg nur auf neuen Auftrag: Stufe 7 Part/Flaechen gemaess N14/N15.
Vor Live-Tests laufende Prozesse und Codeversion erneut feststellen und keine
Benutzersitzung neu starten.

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

Naechster Einstieg nur auf neuen Auftrag: Stufe 6 gemaess AGENTS.md/N10-N13.
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

Abnahme: Stufe-2-Gates laut AGENTS.md und N01/N02 im dokumentierten Umfang
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
