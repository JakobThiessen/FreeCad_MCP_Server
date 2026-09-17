# Ausbauplan: strukturierter FreeCAD MCP Server

Planstand: 2026-09-16. Fortschritt und Testergebnisse: [memory.md](memory.md).

## Ziel und Grenzen

Ein nachvollziehbarer, getesteter MCP-Server fuer FreeCAD 1.1 unter Windows,
mit dem ein Assistent die vereinbarten CAD-Aufgaben ausschliesslich ueber
strukturierte Werkzeuge ausfuehren kann. Benutzer und Assistent muessen fuer
diese Aufgaben weder Python schreiben noch `execute_python` verwenden.
Intern bleiben Python, FreeCAD-APIs und Python-Testprogramme erlaubt.

Vollstaendig bedeutet: alle in Stufe 1 vereinbarten Funktionen und Varianten
sind implementiert und abgenommen. Es bedeutet nicht, dass beliebige
Drittanbieter-Workbenches oder jede zukuenftige FreeCAD-Version abgedeckt sind.

- Kernumfang: Dokumente, Eigenschaften, Spreadsheet, Sketcher, PartDesign,
  Part, Geometrieauswahl, Analyse, Assembly, TechDraw, Draft, Mesh und Austausch.
- FEM bleibt ausgeschlossen.
- CAM und BIM sind separate Erweiterungen, die der Benutzer eigens startet.
- Keine fertigungstechnischen Sicherheits- oder Festigkeitszusagen allein
  aufgrund gueltiger CAD-Geometrie.
- Bestehende 82 Werkzeuge sind Ausgangsbasis, kein Nachweis voller Abdeckung.

## Arbeitsweise pro Chat

1. `AGENTS.md`, diese Datei und `memory.md` lesen. Aktuellen Arbeitsstand und
   die vom Benutzer angeforderte Stufe feststellen.
2. Nur die naechste lokale Implementierungsstelle und ihre Tests untersuchen.
   Historische Testberichte nicht als aktuellen Lauf ausgeben.
3. Aufgaben und Abnahmekriterien der Stufe konkretisieren. Bei zu grossem
   Umfang feste Teilstufen bilden und diese in `memory.md` festhalten.
4. Kleine, pruefbare Aenderungen implementieren und unmittelbar gezielt testen.
   Bestehende API-Konventionen und Tests weiterverwenden.
5. Betroffene Vertraege, Dokumentation und Abdeckungsmatrix aktualisieren.
6. Abschluss oder Teilfortschritt in `memory.md` dokumentieren. Nicht ohne
   Auftrag mit der naechsten Stufe beginnen.

Ein Chat ist eine Arbeitsgrenze, keine Zusage, eine beliebig grosse Stufe in
einem Durchlauf fertigzustellen. Bei Unterbrechung bleibt die Stufe offen und
wird im naechsten Chat an einem konkreten Einstiegspunkt fortgesetzt.

## Gemeinsame Architekturregeln

- Alle Operationen nutzen explizit aufloesbare Dokument- und Objektreferenzen.
  Bestehende optionale Defaults nur mit dokumentierter Migration aendern.
- MCP-Schemas beschreiben Einheiten, Koordinatensysteme, Pflichtfelder,
  unterstuetzte Varianten und moegliche Fehler.
- Ergebnisse liefern gezielte Daten statt unbeschraenkter Eigenschaftslisten:
  betroffene Objekte, Warnungen, Referenzen und strukturierte Fehlerursachen.
- FreeCAD-Zugriffe erfolgen ueber den GUI-Executor. Keine Hintergrundthreads
  fuer ungesicherte direkte Dokument- oder Geometriezugriffe.
- Eigenschaften werden typisiert und nach Schreibbarkeit validiert.
  Keine generische Codeausfuehrung, `eval` oder beliebige Methodenaufrufe als
  Ersatz fuer fehlende MCP-Funktionen.
- Stapelauftraege enthalten nur erlaubte Operationen und Ergebnisreferenzen,
  keine Skriptsprache. Atomaritaet und Teilfehlerverhalten sind explizit.
- Geometrietreffer werden auf Eindeutigkeit und Aktualitaet geprueft.
  Nach Topologieaenderungen keine stillschweigende Neuzuordnung.
- Abbruch langer Berechnungen nur zusagen, wenn technisch moeglich.
  Wiederholte Aufrufe duerfen nach einem Timeout nicht blind dupliziert werden.
- Fehler duerfen keine unerkannten Teilmodelle hinterlassen. Transaktions-
  grenzen fuer Dokumente, Dateien und Stapeloperationen getrennt festlegen.
- Modellieraufgaben muessen auch ueber den echten MCP-Transport testbar sein.
  Interne Python-Tests sind erlaubt; die Abnahme-Workflows verwenden keine
  freie Codeausfuehrung als CAD-Ausweg.

## Stufe 1: Abdeckungsmatrix und Abnahmevertrag

Ziel: Aus dem Gesamtwunsch einen begrenzten, nachpruefbaren Umfang machen.

- Tatsaechlich registrierte Tools und Addon-Operationen inventarisieren.
- Pro Funktion Varianten, Parameter, lesende/aendernde Operationen,
  FreeCAD-Version, vorhandene Tests und fehlende Anteile erfassen.
- Status unterscheiden: vorhanden, teilweise, fehlt, getestet, ausgeschlossen.
- Primaere Referenzaufgaben definieren: Gehaeuse, Wellen-/Flanschbauteil,
  Schraubstock, Gelenkbaugruppe und technische Zeichnung.
- Fuer jede Aufgabe messbare Kriterien festlegen, einschliesslich Bearbeiten,
  Fehlerfaellen, Speichern, erneutem Oeffnen und Export.
- Die folgenden Stufen gegen die Matrix pruefen und bei Bedarf begruendet
  unterteilen, ohne ausgeschlossene Bereiche eigenmaechtig aufzunehmen.

Lieferumfang: `docs/COVERAGE.md` und `docs/ACCEPTANCE.md`; diese beiden Dateien
werden erst in Stufe 1 angelegt. Noch keine funktionale Servererweiterung.
Abnahme: Jede vereinbarte Funktion hat Status, Zielstufe und Pruefkriterium;
offene Entscheidungen und Ausschluesse sind sichtbar. Umfang dem Benutzer
zur Bestaetigung vor Stufe 2 vorlegen.

## Stufe 2: Einheitliche MCP-Vertraege und Infrastruktur

- Faehigkeiten und Versionsmerkmale abfragen; Schemas und Fehler vereinheitlichen.
- Dokument-/Objektreferenzen, Einheiten und Koordinatensysteme definieren.
- Transaktionen, Vorschau riskanter Aenderungen und Rollback konsistent machen.
- Begrenzte Stapelaufrufe mit Ergebnisreferenzen und klaren Fehlerregeln.
- Rueckwaertskompatibilitaet oder ausdrueckliche Migrationsregeln festhalten.

Abnahme: Schema-/Transporttests sowie Stapelerfolg, ungueltige Eingaben,
Teilfehler und Rollback mit mindestens zwei Dokumenten pruefen.

## Stufe 3: Dokumente, Eigenschaften und Parameter bearbeiten

- Dokumente aktivieren und inspizieren; Bodies, Gruppen und Tips verwalten.
- Eigenschaften mit Typ, Einheit, Schreibbarkeit und Auswahlwerten lesen/setzen.
- Expressions, Spreadsheet-Zellen, Aliase und Abhaengigkeiten verwalten.
- Umbenennen, Kopieren, Links, Gruppieren und sichere Loeschvorgaenge.
- Folgefeatures und Auswirkungen einer geplanten Aenderung ermitteln.

Abnahme: Bestehendes parametrisches Teil ausschliesslich per MCP aendern,
recompute, Undo/Redo, speichern und erneut oeffnen. Schreibgeschuetzte
Eigenschaften, fehlerhafte Referenzen und zyklische Expressions testen.

## Stufe 4: Geometrieauswahl, Messung und visuelle Rueckmeldung

- Flaechen/Kanten/Punkte strukturiert auflisten und nach Geometrie filtern.
- Auswahl nach Lage, Normalenrichtung, Form, Radius und Groesse kombinieren.
- Treffer markieren und Screenshots mit gezielten Ansichten liefern.
- Mehrdeutigkeit und veraltete Referenzen erkennen.
- Abstaende, Winkel, Schnittmengen und vereinbarte Kollisionspruefungen.

Abnahme: Auswahl ohne fest codierte Kantennummern; mehrdeutige Treffer und
Topologieaenderungen werden nachvollziehbar behandelt. Messwerte mit
analytisch bekannten Beispielen vergleichen.

## Stufe 5: Sketcher vervollstaendigen

- Geometrie und Constraints anlegen, inspizieren, aendern und entfernen.
- Vereinbarte Constraint-Varianten, Referenzmasse und treibende Masse.
- Externe Geometrie, Befestigung und Skizzen-Koordinatensysteme.
- Trimmen, Verlaengern, Verrunden und weitere vereinbarte Zeichenoperationen.
- Freiheitsgrade, Konflikte und redundante Constraints diagnostizieren.

Abnahme: Profile von Gehaeuse und Flansch per MCP vollstaendig bestimmen und
nachtraeglich aendern; Konfliktfaelle liefern verwertbare Diagnose und Rollback.

## Stufe 6: PartDesign vervollstaendigen

- Bezugsebenen, -achsen und -punkte sowie Attachment-Verwaltung.
- Pad/Pocket-Endbedingungen und beidseitige Varianten laut Matrix.
- Revolution, Groove, Loft/Pipe und deren vereinbarte Optionen.
- Bohrungen, Kantenfeatures, Thickness, Draft, Muster und Mehrfachtransformationen.
- Profile und Featureparameter nachtraeglich aendern; Tip/Abhaengigkeiten sichern.

Abnahme: Gehaeuse und Wellen-/Flanschbauteil mit nachvollziehbarem Featurebaum
erstellen und bearbeiten; gueltige Volumen und erwartete Masse pruefen.

## Stufe 7: Part und Flaechenmodellierung

- Part-Extrusion/-Revolution, Loft/Sweep fuer Volumen und Flaechen.
- Draehte, Flaechen, Schalen und Volumen bilden bzw. umwandeln.
- Boolesche Operationen, Schnitte, Aufteilungen und Offsets.
- Validierung, Formreparatur und Verfeinerung mit klaren Grenzen.

Abnahme: Flaechenmodell schliessen, Boolesche Bauteile bearbeiten und Ergebnisse
pruefen; ungueltige bzw. nicht reparierbare Eingaben kontrolliert behandeln.

## Stufe 8: Auftraege und mechanischer Gesamtworkflow

- Lange Operationen als Auftraege starten, Status/Fortschritt/Ergebnis abrufen.
- Timeout-, Wiederverbindungs-, Wiederholungs- und Abbruchverhalten festlegen.
- Dokumentuebersichten begrenzen; Stapelaufgaben und Bildrueckmeldung optimieren.
- Gehaeuse, Flansch und Schraubstock durchgaengig ueber MCP erstellen,
  bearbeiten, pruefen und exportieren.

Abnahme: Mechanischer Kern ohne `execute_python`-Ausweichweg. Reproduzierbare
MCP-Workflows samt Negativtests und Zeitueberschreitungsfaellen.
Bestehendes Python-Modellskript allein zaehlt nicht als diese Abnahme.

## Stufe 9: Assembly

- Komponenten einfuegen/verknuepfen, fixieren und positionieren.
- Vereinbarte Gelenke, Freiheitsgrade und Gelenkparameter verwalten.
- Bewegungszustaende pruefen, Kollisionen und unloesbare Baugruppen melden.
- Dokumentuebergreifende Referenzen und Baugruppenstruktur erhalten.

Abnahme: Schraubstock oder Gelenkbaugruppe per MCP zusammensetzen und bewegen;
Speichern/Wiederherstellen erhaelt Gelenke und Platzierungen.

## Stufe 10: TechDraw

- Seiten und Vorlagen, Ansichten, Projektionen, Schnitte und Details.
- Masse, Beschriftungen und Layout gezielt erstellen und bearbeiten.
- Modellbezug aktualisieren und PDF/SVG ausgeben.

Abnahme: Technische Zeichnung eines Referenzbauteils mit mehreren Ansichten,
Schnitt und Massen; nach Modellaenderung pruefen und visuell kontrollieren.

## Stufe 11: Draft, Mesh und erweiterter Austausch

- Vereinbarte Draft-Elemente, Arrays und Beschriftungen.
- Netze inspizieren, reparieren und konvertieren, jeweils mit Ergebnisdiagnose.
- In Stufe 1 festgelegte Formate/Optionen, Einheiten und Metadaten erhalten.
- Baugruppenstruktur und Farben beim Austausch pruefen, soweit unterstuetzt.

Abnahme: Format-Roundtrips mit Geometrie-, Einheiten- und Strukturvergleich;
unzulaessige Konvertierungen und Informationsverluste explizit melden.

## Stufe 12: Gesamtabnahme und normaler Betriebsmodus

- Alle vereinbarten Matrixeintraege und Referenzaufgaben abnehmen.
- Dokumentation, Installation/Update und MCP-Neustart nachvollziehbar pruefen.
- Versionen und verbleibende Grenzen klar ausweisen; keine ungeprueften Zusagen.
- Freie Python-Ausfuehrung im normalen Modus deaktivieren; ein etwaiger
  Entwicklermodus muss ausdruecklich aktiviert und dokumentiert sein.
- Sicherstellen, dass freier Code auch nicht ueber andere RPC-Pfade erreichbar
  ist, wenn der normale Modus dies ausschliesst; keine Sandbox behaupten.

Abnahme: Alle Referenzaufgaben bestehen mit deaktivierter freier Codeausfuehrung
ueber den echten MCP-Transport. Ausgeschlossene Bereiche bleiben sichtbar.

## Optionale Stufe 13: CAM

Nur nach eigenem Auftrag: Aufspannungen, Werkzeuge, vereinbarte Operationen,
Werkzeugwege, Simulation und Postprozessoren. Ausgabe nicht ungeprueft als
maschinensicher bezeichnen; Abnahmekriterien vor Implementierung festlegen.

## Optionale Stufe 14: BIM/Arch

Nur nach eigenem Auftrag: Bauelemente, Gebaeudestruktur, Parameter, IFC und
vereinbarte Auswertungen. Abnahmekriterien und IFC-Roundtrips vorher festlegen.

## Pruef- und Uebergaberegeln

- Je Aenderung zuerst der billigste aussagekraeftige Test, danach relevante
  Integration und MCP-End-to-End-Pruefung. Kein Ersatz durch reine Toolzaehlung.
- Live-Tests in eigenen Dokumenten und moeglichst isolierter FreeCAD-Instanz.
  Vorherige Benutzerdateien und nicht gespeicherte Dokumente nicht veraendern.
- Schematests: Werkzeugregistrierung, Pflichtfelder, Argumentweitergabe,
  Serialisierung, Fehler und kompatible Aufrufer.
- CAD-Tests: erwartete Geometrie/Masse, Zustand, Bearbeitung, Undo/Redo,
  Rollback, Datei-Roundtrip und erforderlichenfalls visuelle Kontrolle.
- Nicht ausfuehrbare Tests samt Grund als offen dokumentieren. Kein automatischer
  Stufenabschluss, nur weil Code geschrieben wurde.
- `memory.md` am Ende aktualisieren: Datum, Status, Aenderungen, betroffene
  Dateien, Testbefehle/Ergebnisse, offene Punkte, Laufzeit/Installation,
  verbleibende Dokumente und konkreter Startauftrag fuer den naechsten Chat.
- API-Aenderungen und geaenderte Entscheidungen samt Begruendung festhalten.
  Alte Arbeit nicht erneut implementieren; alte Testzahlen nicht fortschreiben.
