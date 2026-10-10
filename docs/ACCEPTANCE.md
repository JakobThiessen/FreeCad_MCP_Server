# Abnahmevertrag: strukturierte CAD-Workflows

Stand: 2026-10-10. **Umfang einschliesslich D1-D5 vom Benutzer bestaetigt.**
Dieser Vertrag konkretisiert [AGENTS.md](../AGENTS.md) und die Funktions-IDs in
[COVERAGE.md](COVERAGE.md). Er ist keine Zusage bereits bestandener CAD-Tests.

Implementierter Stufe-2-Vertrag: [CONTRACTS.md](CONTRACTS.md).
Stufe 2 am 2026-09-16 nach technischem Gate abgenommen: 28 lokale Tests,
24 FreeCAD-Integrationstests und echter MCP-Vertragslauf mit zwei Dokumenten,
allen elf Batchoperationen, Vorschau, atomarem Rollback/Undo/Redo, Vorvalidierung,
Mehrdokument-Teilstatus und Cleanup bestanden. Bestehender MCP-Smoke ebenfalls
bestanden. N01/N02 im dokumentierten Infrastrukturumfang erfuellt;
keine Gesamtabnahme A1-A5 oder spaeterer Fachvarianten. Protokoll: [memory.md](../memory.md).

Stufe 3 am 2026-09-16 nach technischem Gate abgenommen: 30 lokale Tests,
28 native Integrationstests, zweimal 120 strukturierte MCP-Aufrufe auf frischer
Bridge 0.4.0; Stufe-2-Vertragslauf und Bestands-Smoke ebenfalls bestanden.
N03-N06 im dokumentierten Umfang erfuellt. A1-Parameterteil mit Part-Box/Cut
und analytischen Volumen/Undo/Redo/Negativfaellen/FCStd reopen/STEP/STL geprueft;
vollstaendige Sketcher-/PartDesign-Aufgabe bleibt Stufen 5/6/8.

Stufe 4a und anschliessend 4b am 2026-09-16 nach technischem Gate abgenommen:
32 lokale Tests, 33 native CAD-Tests und zweimal 113 strukturierte MCP-Aufrufe
auf frischer Bridge 0.5.0/Port 9883. I32/I33/I36/N07 im Vertrag aus CONTRACTS
erfuellt: geometrische Filter/Revision, sechs Dress-up-Verbraucher, globale
Container-/Linkkoordinaten, analytische Abstaende/Winkel/Kontakt/Interferenz,
Undo/Redo/reopen und sieben dokumentgezielte Ansichten. 14 PNGs mit 800x600
Pixeln pixelgeprueft; Isometrie und Draufsicht visuell kontrolliert, native
Kamerarichtungen separat numerisch geprueft. GUI-Markierung separat vom PNG-
Export, der Hervorhebungen ausblenden kann. Revisionslose Altselektoren bleiben
ungeschuetzt, keine kontinuierliche Kollisionszusage. Stufe-2-Vertragsregression,
zweimal 121 Stufe-3-Aufrufe und Bestands-Smoke bestanden. Zum damaligen Gate
kein Start Stufe 5 und keine Gesamtabnahme A1-A5. Exakte Artefakte und
Testfixturekorrekturen: memory.md.

Stufe 5 am 2026-09-17 nach technischem Gate abgenommen: 33 lokale Tests,
36 native GUI-Tests und zweimal 52 strukturierte MCP-Aufrufe auf frischer
Bridge 0.6.0. Die beiden geforderten Profile erreichen DoF 0 ohne pauschale
Block-Constraints, lassen sich ueber treibende Masse aendern und bleiben nach
FCStd save/reopen bestimmt. Konflikt-/Redundanzfehler liefern IDs und rollen
vollstaendig zurueck. N08/N09 sind fuer Geometry-/Constraint-CRUD, Modi,
Diagnosen, revisionsgepruefte externe Kanten, planare/Datum-Attachments sowie
Trim/Extend/Fillet/Copy/Mirror erfuellt. FreeCAD-1.1-Grenzen stehen in
CONTRACTS. Vertrags-, Stufe-4-, Stufe-3- und Bestands-MCP-Regressionslaeufe
bestanden. Keine Vorwegnahme Stufe 6 und keine Gesamtabnahme A1-A5.

Stufe 6 am 2026-09-29 nach technischem Gate umgesetzt: Bridge 0.7.0 mit 139
Tools, lokale Vertragspruefung, native PartDesign-Varianten und zwei
unabhaengige strukturierte MCP-Laeufe fuer Gehaeuse-/Flanschfixtures samt
Bearbeitung, Negativfall, FCStd save/reopen, exakter Body-Tip-Pruefung und STEP.
N10-N13 sind im begrenzten Variantenvertrag aus CONTRACTS umgesetzt. Dies ist
das PartDesign-Teilgate, nicht die durchgaengige A1/A2-Gesamtabnahme aus Stufe 8;
freie Python-Ausfuehrung war kein CAD-Ausweg. Exakte Zahlen und verbleibende
Laufzeitgrenzen stehen in memory.md.

Stufe 8 am 2026-10-01 nach technischem Gate abgenommen: Bridge 0.9.0 mit 159 Tools.
Strukturierte Batch-Jobs besitzen prozesslokale IDs, sechs Statuswerte,
idempotentes Ergebnislesen, sichere Abbruchsemantik fuer wartende Futures und
explizites `cancel_not_supported` fuer laufende Kernelarbeit. Objektuebersichten
sind additiv paginiert; Bildgrenzen aus Stufe 4 bleiben bestehen. Lokale Tests
und echte MCP-stdio-Laeufe pruefen Same-Process-Reconnect, genau einmal erzeugte
Geometrie, Jobfehler, unbekannte IDs, Pagination, echten Transport-Timeout und
kontrollierten Prozessverlust. A1-A3 liefen zweimal in frischen Dokumenten mit
Parameteraenderung, Undo/Redo, Negativrollback, FCStd-Zyklus, analytischen
Orakeln, STEP-/STL-Roundtrip und A3-Bildrueckmeldung. Keine CAD-Mutation nutzte
`execute_python`; Einzelheiten und Artefaktpfade stehen in memory.md.

## Teilgate 11a: Draft

Am 2026-10-09 auf FreeCAD 1.1.1 Build 20260414 geprueft: N20 mit fuenf
strukturierten Werkzeugen und bestehenden sicheren Loeschpfaden. 52 Hosttests,
55 native Regressionen und **zwei unabhaengige echte MCP-Laeufe je 182
Workflow-Aufrufe** bestanden. Native Tests und MCP nutzen eigene Dokumente,
finaler MCP-Nachweis eine frische GUI ohne Testvorlauf, Raw-Python deaktiviert.

Orakel: Linie, offener/geschlossener Wire, Rechteck 40*20, Kreis und Bogen mit
analytischer Laenge/Radius/Abschluss; Text und Custom-Label mit Textgroesse und
Placement. Translation und 90-Grad-Quaternion numerisch geprueft. Ortho 2x3=6,
XYZ 2x3x2=12, Polar 4 mit X/Y/Z-Achsen, nachtraeglicher Winkel-/Anzahledit und
Quellenaenderung propagieren. Native Quellsichtbarkeit und fremdes Aktivdokument
bleiben erhalten. Beide MCP-Laeufe pruefen pro Element/Array Bearbeitung,
Undo/Redo, ungueltige Spezifikationen ohne Objektveraenderung, kaputte Quelle,
sicheres Loeschen/Undo, Speichern/Schliessen/erneutes Oeffnen und zweite Aenderung.
Lage/Laenge nach G, Strukturidentitaet exakt; numerische Snapshotvergleiche
verwenden 1e-6 absolut/relativ gegen natives Rundungsrauschen. Kein Abschwaechen
analytischer BBox-Gates; rotierte Kreise nutzen die native optimale BBox.

Zum damaligen Teilgate waren nur 11a und GUI 1.1.1 geprueft; 11b/11c folgten
in einem separaten Auftrag und wurden nicht durch diesen Draft-Nachweis ersetzt.
Exakte Befehle, Artefakte und Laufzeitgrenzen: [memory.md](../memory.md),
Werkzeugvertrag: [CONTRACTS.md](CONTRACTS.md).

## Teilgates 11b/11c: Mesh und X-Austausch

Am 2026-10-09 auf eigener FreeCAD 1.1.1 Build 20260414 geprueft: 54 Hosttests
(3,051 s), 59 native Regressionen (27,033 s) und neue reine Normalmodus-GUI
ohne nativen Testvorlauf, zweimal 142 protokollierte strukturierte MCP-
Fachaufrufe plus elf Cleanup-Aufrufe je Lauf, Exitcode 0, 194 Tools.
Raw-Python aus; alle CAD-Aufrufe strukturiert, temporaere eigene Dokumente/Dateien.

Mesh-Orakel: 40*20*10-Box mit fehlendem Dreieck und ganzer Wand, zuerst
unzureichende Lochgrenze ohne Originalaenderung, dann Abschluss und 8000 mm3.
Duplikat/kollinear degenerierte Facette entfernen, inverse/inkonsistente Normalen
korrigieren, vor/nach Diagnose, Undo/Redo mit Struktur-/numerischen Snapshots.
Nonmanifold, offenes Solid und mehrere Komponenten werden kontrolliert abgewiesen.
Shape/Solid-Konvertierung und absolute lineare/angularen Optionen, feinere
Kugeltriangulation gegen grobe mit analytischem Volumen nach G. Gruppierte
Shape-/Mesh-Koordinaten nativ geprueft; verschobenes Mesh nach Reopen/zweitem
Edit/Resave/Reexport/Reimport behaelt globale BBox und Volumen.

X-Orakel unveraendert: beide echten STEP FILE_SCHEMA-Header AP214/AP242,
je zwei verschiedenfarbige Links in einem Container, Labels, RGB, globale
BBox (X=0/60), 8000 mm3 je Solid, zwei Kinder und Wiederherstellung nativer
Exportpraeferenzen. STL ASCII/binaer einschliesslich Facetten-/Binaerlaenge und
einstellbarer absoluter Toleranzen; OBJ-Import/-Export mit Abschluss, Orientierung,
Volumen/BBox. DXF/SVG: Rechteck 40*20, Kreis R5 bei (10,10), offene Linie/Wire
und 90-Grad-Bogen R5; Gesamtkontur, zwei geschlossene Konturen, Radius und
globale mm-Koordinaten nach G. Import-Undo/Redo, fehlerhaftes SVG mit Rollback,
ungueltige Auswahl/Schemaoption, fehlende Datei, nichtplanares Exportobjekt,
No-Clobber und explizite Ueberschreibung, Fremddokument unveraendert.

Stufe 11 ist damit im vereinbarten Variantenumfang auf GUI 1.1.1 geprueft;
andere Patches, per-Face-/Link-Farbpaletten und allgemeines Healing ungeprueft.
Statische Ergebnisse/Informationsverluste gemaess CONTRACTS, kein Schema-Downgrade.
Keine Gesamtabnahme Stufe 12 und kein CAM/BIM/FEM-Auftrag. Exakte Pfade und
Prozesscleanup in [memory.md](../memory.md); Artefakte
`%TEMP%/freecad-stage11bc-mcp-iyc0kc7w/{1,2}/` und report.json.

## Umfang und Freigabe

### Aktuelles Teilgate 12a (2026-10-10)

FreeCAD 1.1.1 Build 20260414, native Python 3.11.14, Host Python 3.10.11/MCP
1.27.1, Bridge 0.11.0/Paket 0.1.0, 194 Tools, Raw-Python aus. 55/55 Hosttests
(2,913 s), 59/59 native Tests nach beiden Produktionsfixes (25,915 s).
`tests/mcp_smoke.py --stage12-only` auf neuer eigener GUI/Port 9955 besteht:
15 Gates je Durchlauf, zweimal eigene Dokumente, A1-A5 und Fachregressionen,
je 113 Normalmodus-Negativchecks; A4 zusaetzlich alle fuenf Gelenktypen mit
geometrisch ausgewaehlten Connectoren, je 267 Fachaufrufe. FCStd-Reopen,
zweiter Edit/Recompute/Resave, Suppression/Undo/Redo und ungueltige Mutationen
der neuen Gelenkfixtures bestanden. Fehlerhafter Alt-ViewProvider und Fremd-
kameraaenderung wurden gefunden und im jeweiligen Eigentuemer korrigiert.

Finaler Bericht: `%TEMP%/freecad-stage12-mcp-pkp8l8di/report.json`, Eingaben,
Ausgaben und Artefakte je `1/` und `2/`. G und X unveraendert. A4-Rollback-
Snapshot vergleicht nur Placement-Zahlen mit 1e-12 absolut/0 relativ, alle
anderen Daten exakt; beobachtete native Abweichung ca. 4,4e-15. Dies ersetzt
weder analytische G-Orakel noch erlaubt es Strukturabweichungen.
Die vorherigen vier A5-PDF/SVG-Renderbilder und A3-PNGs aus dem identischen
Produktionsstand `%TEMP%/freecad-stage12-mcp-aefqmbk2/` wurden visuell geprueft;
numerische Rendergates auch im finalen Run bestanden. Pflichttexte/Ansichten
lesbar im Blatt, kein beobachteter Textueberlauf. Keine Fertigungsfreigabe.

**Kein Gesamtabschluss:** alle V-Varianten brauchen weiterhin einzeln zugeordnete
aktuelle Doppel-MCP-Nachweise; native Tests allein ersetzen diese nicht.
Addon-Autoload/Update, kontrollierter neuer Prozessverlustnachweis und Migration
alter fehlerhafter Joint-ViewProvider sind offen. Isolierte Wheelinstallation
und neuer MCP-Prozess aus diesem Paket bestanden, aber nicht der ganze N22-Zyklus.
Keine regulaere Installation geaendert, keine Benutzerfreigabe vorweggenommen.
Feste Folgegates und genaue Laufzeit/Cleanup: [memory.md](../memory.md).

Kern: Dokumente, Properties, Spreadsheet/Expressions, Sketcher, PartDesign,
Part/Flaechen, geometrische Auswahl/Analyse/Bilder, Jobs, native Assembly,
TechDraw, begrenztes Draft/Mesh und Austausch gemaess Matrix I01-I38/N01-N22.
Vollstaendig bedeutet alle dort aufgezaehlten Varianten, nicht jede FreeCAD-
Funktion. `execute_python` (I38) zaehlt ausschliesslich als abzuschaltender
Altpfad, nicht als zulaessiges Werkzeug fuer CAD-Referenzaufgaben.

- FreeCAD 1.1/Windows mit lokaler GUI-Bridge; Standardtransport MCP stdio.
- FEM ist ausgeschlossen (X01), auch wenn alte FEM-Skripte im Workspace liegen.
- CAM und BIM/Arch (X02/X03) sind optionale, nicht aktivierte Stufen 13/14.
- Nicht enthalten: Drittanbieter-Workbenches, Remote-/Mehrbenutzerbetrieb,
  andere FreeCAD-Versionen, beliebige NURBS-Bearbeitung, dynamische Simulation,
  kontinuierliche Kollisionsfreiheit, real ausgeformte Gewinde und Fertigungs-
  oder Festigkeitsfreigaben. Nicht aufgefuehrte Formate/Varianten sind keine
  implizite Zusage. Keine Betriebssystem-Sandbox oder CAD-Reparaturgarantie.
- Benutzer und CAD-Assistent schreiben keine Modellierskripte. Interne
  Implementierung, Testtreiber und unabhaengige lesende Python-Prueforakel sind
  erlaubt. Testtreiber duerfen CAD nur mit strukturierten MCP-Aufrufen aufbauen
  oder aendern; kein verdeckter RPC-/Konsolen-/Makro-Codeausweg.
- Vor Stufe 2 ist eine ausdrueckliche Bestaetigung dieses Umfangs erforderlich.
  Eine Bestaetigung startet noch keine weitere Stufe; dazu ist ein Auftrag noetig.

## G: Gemeinsame Abnahmeregeln

### Umgebung und Nachweis

Jeder Lauf protokolliert Datum, Windows-/FreeCAD-Version inklusive Build soweit
verfuegbar, Python-Interpreter des MCP-Hosts, MCP-/Addon-Version bzw. Dateihashes,
Konfiguration/Capabilities, Bridge-Port, Testfall-ID, Eingaben, Ausgaben und
Artefaktpfade. Ein neuer Chat prueft die Umgebung neu. Alte Testzahlen gelten
nicht als neuer Lauf. Historischer Stand und aktueller Nachweis: COVERAGE.

Alle A1-A5 laufen durch den **echten MCP-stdio-Server und GUI-Executor**, in
eigenen Dokumenten und eigenem Ausgabeverzeichnis, moeglichst isolierter GUI.
Vorhandene Benutzerdokumente werden nicht geaendert, geschlossen oder
ueberschrieben; kein Neustart der Benutzersitzung ohne Zustimmung.
Snapshots umfassen Objektidentitaeten/Typen, Abhaengigkeiten, Properties,
Placement, Tip, Solverstatus, Geometriekennwerte und Sichtbarkeit.

### Einheiten und Toleranzen

Modellkoordinaten und Laengen in mm, Flaechen mm^2, Volumen mm^3, Winkel in Grad,
ausdrueckliche rad-Altparameter nach Schema; jedes neue Schema nennt Einheit
und globales/lokales Bezugssystem. A1-A3 sind idealisierte Geometrien.
Folgende Toleranzen sind **bestaetigte Abnahmekriterien**, keine Messwerte:

| Groesse | Pass-Kriterium |
| --- | --- |
| Analytische Laenge/Lage/BBox | absolut <= 0.001 mm |
| Analytischer Winkel | absolut <= 0.001 Grad |
| Analytische BRep-Flaeche/Volumen | Abweichung <= max(1e-6 absolut in mm^2/mm^3, 1e-6 * Betrag des Sollwerts) |
| FCStd reopen | Objekt-/Link-/Constraint-/Gelenkstruktur und Werte erhalten; Geometrie innerhalb BRep-/Laengentoleranz |
| STEP Roundtrip | Solidanzahl exakt, alle gueltig; relatives Gesamtvolumen <= 1e-5, BBox <= 0.01 mm; Einzelteile nicht nur Gesamtsumme pruefen |
| STL/OBJ Roundtrip geschlossener Solids | geschlossen/orientiert, Komponentenanzahl pro disjunktem Fixture erhalten; relatives Volumen <= 0.005, BBox <= 0.1 mm |
| Mesh-Triangulation | lineare Abweichung <= 0.1 mm, Winkelabweichung <= 0.5 rad; Optionen protokollieren, keine identische Facettenzahl verlangen |
| Kontakt/Interferenz | Abstand <= 0.001 mm: Kontakt; Schnittvolumen > 1e-6 mm^3: Interferenz; beide Kennwerte ausgeben, nicht nur Boolean |
| Zeichnung | numerische Modellmasse innerhalb Laengentoleranz; Anzeige auf 0.01 mm; Sollmassstab, Papierformat und sichtbare Beschriftung korrekt |

Referenzvolumen werden aus den unten angegebenen idealen Abmessungen berechnet,
nicht aus dem erzeugten Modell als eigener Sollwert uebernommen. Bei bewusst
verrundeten/entformten Zusatzfixtures vorher/nachher separat pruefen; fehlendes
analytisches Orakel durch festgelegte Geometrieinvarianten ergaenzen, nicht
einfach durch `isValid()`. Physikalische Masse nur mit expliziter Dichte.

### Erstellen, Bearbeiten und Fehler

Jede Referenzaufgabe muss in einem frischen Dokument reproduzierbar sein und
mindestens zweimal unabhaengig bestehen. Erzeugte interne Namen duerfen variieren;
Aufrufe benutzen zurueckgegebene Referenzen, keine geratenen `EdgeN`/`FaceN`.
Ausnahmen nur Variantenfixtures, die bewusst ungueltige Referenzen testen.

Pflicht je Aufgabe: Erstellen, inspizieren/messen, vorgeschriebene Aenderung,
recompute, Undo, Redo, Negativfall, speichern, schliessen, erneut oeffnen,
erneut inspizieren, zweite gueltige Aenderung nach reopen und Export nach X.
Undo stellt den Snapshot vor der Aenderung wieder her, Redo den danach.
Erneut speichern nach der zweiten Aenderung. Geometrische G-Messungen und
Abhaengigkeiten muessen in jedem relevanten Zustand stimmen.

Bei Fehlern: stabiler Fehlercode mit Ursache, betroffenen Referenzen, Warnungen
und Ergebnisstatus. Keine neuen unerkannten Teilobjekte, veraenderten Tips,
halben Constraints oder offenen eigenen Transaktionen nach Rollback. Zwei
Dokumente mit gleichen Objektnamen gehoeren zum Infrastrukturtest; das jeweils
andere Dokument bleibt unveraendert. Read-only, falsche Typen/Enums/Einheiten,
fehlende/veraltete Referenzen, leere Auswahl, Mehrdeutigkeit, Selbstschnitt,
Solverkonflikt und Expressionszyklen erhalten dedizierte Negativtests.

### Dateien, Batches und lange Auftraege

Save/Export ueberschreibt im Zielvertrag nicht stillschweigend: vorhandener
Pfad verlangt explizite Zustimmung; Datei bleibt bei Ablehnung unveraendert.
Dateioperationen werden separat von Dokumenttransaktionen getestet, inklusive
unbeschreibbarem Ziel/fehlender Eingabedatei. Kein Versprechen eines verteilten
Datei-/Dokument-Rollbacks. Teilweise geschriebene Ausgabe darf nicht als Erfolg
gelten; Status und verbleibende Artefakte sind auszuweisen.

Batchvertrag: maximal 100 erlaubte strukturierte Schritte, vorher validierte
Ergebnisreferenzen; `atomic` nur fuer ein bestehendes Dokument und erlaubte
Dokumentmutationen. Dokumentwechsel, Datei-I/O und Lebenszyklusoperationen im
atomaren Batch vor Ausfuehrung ablehnen. Dokumentuebergreifender nichtatomarer
Batch stoppt beim ersten Fehler und meldet je Schritt Erfolg/Fehler/nicht
ausgefuehrt; erfolgreiche Schritte werden nicht als zurueckgerollt ausgegeben.
Test: Erfolg, fehlerhafter mittlerer Schritt, Forward-/Zyklusreferenz und
fremde offene Transaktion mit mindestens zwei Dokumenten.

Jobs: queued/running/succeeded/failed/cancelled unterscheiden. Wartender
abgebrochener Job darf nie nachtraeglich mutieren. Laufender Kerneljob darf
`cancel_not_supported` melden; Timeout bedeutet nicht automatisch Abbruch.
Job-ID nach Wiederverbindung inspizieren statt Mutation blind wiederholen;
wiederholtes Ergebnislesen erzeugt null weitere Objekte. Nach Prozessverlust
explizit unbekannter Zustand, keine erfundene Jobfortsetzung. Fortschritt darf
unbekannt sein; keine unbelegten Prozentwerte oder festen CAD-Laufzeiten.
Stufe 8 testet diese Faelle gezielt mit kontrolliertem Testharness.

### V: Variantentests ausserhalb der fuenf Hauptaufgaben

Die fuenf Aufgaben decken nicht alle Matrixvarianten ab. Fuer **jede** genannte
Funktion/Enum-Variante ist zusaetzlich mindestens ein positiver, ein ungueltiger
oder Grenzfall und bei Mutationen ein Bearbeitungs-/Rollbackfall erforderlich.
Nicht jede Parameterkombination ist zugesagt: zulaessige Kombinationen im Schema
explizit auflisten, unzulaessige vor Mutation ablehnen. Gemeinsame Parametertypen
koennen geteilte Vertragstests verwenden, geometrische Varianten nicht.

Besonders notwendige Zusatzfixtures: alle Sketch-Geometrien/Constraints und
Zeichenoperationen (I05-I17/N08-N09), alle PartDesign-Endbedingungen/Optionen
(N10-N13), alle Primitiven/Rotationen/Spiegelungen, Flaeche->Shell->Solid,
Part-Loft/-Sweep/Offset/Split/Reparatur (N14-N15), alle fuenf Gelenktypen (N18),
TechDraw-Detail/Radius/Winkel (N19), Draft-Arrays und Mesh-Defekte (N20-N21).
Die jeweiligen analytischen bzw. strukturellen Orakel stehen in COVERAGE.
Bei nicht unterstuetzter Pflichtvariante ist die Zeile blockiert, nicht bestanden.

Stufe 7 ist seit 2026-10-01 technisch abgenommen. N14 sowie Section, Split,
2D-/3D-Offset, Validierung, Refine, Sewing und begrenztes Shape-Fix aus N15
sind mit analytischen bzw. strukturellen Orakeln implementiert. Da FreeCAD 1.1
den endlichen Gap nativ nicht schliesst, rekonstruiert `part_sew` ausschliesslich
sechs nahezu rechteckige, planare, achsparallele Quaderflaechen, wenn jede
Ecke innerhalb der Eingabetoleranz an den ermittelten Quadergrenzen liegt.
Die 0,005-mm-Probe bleibt bei 0,001 mm offen und wird bei 0,01 mm zu genau
einem gueltigen 1000-mm^3-Solid. Andere Topologien erhalten keine allgemeine
Lueckenheilungszusage.

## A1: Parametrisches Gehaeuse

Matrix: I02-I03/I05-I07/I16-I19/I34-I37, N03-N10/N17.
Teilgate Stufen 3/5/6, kompletter mechanischer Workflow Stufe 8, final Stufe 12.

- Offene rechteckige Schale, ein Body/Solid. Aussen 80*50*30, Boden und Waende
  t=3. Boden auf z=0, Innenausschnitt 74*44 ab z=3 bis z=30. Keine Rundungen,
  Bohrungen oder Deckel im analytischen Hauptfixture.
- Spreadsheet-Aliase L/W/H/t steuern Skizzen und Pad/Pocket ueber Expressions.
  Native-kompatible Namen seit Benutzerfreigabe am 2026-09-16:
  `LengthParam/WidthParam/HeightParam/WallParam` (W wird von FreeCAD 1.1
  als Alias abgelehnt). L/W/H/t bleiben mathematische Kurzbezeichnungen.
  Vollstaendig bestimmte, sinnvoll bemasste Profile: DoF=0 und kein pauschales
  Blockieren aller Geometrien als Ersatz fuer Parameter.
- Sollvolumen `L*W*H - (L-2*t)*(W-2*t)*(H-t)` = **32088 mm^3**;
  BBox 80/50/30, Boden/Wand an ausgewaehlten Flaechen messen.
- Bearbeiten: L von 80 auf 100, Innenlaenge wird 94; V = **38328 mm^3**,
  Breite/Hoehe/t unveraendert. Undo/Redo pruefen diese beiden Zustaende.
- Negativ: t=26 (kein positiver Innenquerschnitt) und zyklische Expression;
  beide melden Ursache und behalten vorherige Parameter/Geometrie/Tip.
- Nach G-Dateizyklus bei L=100: t auf 4 aendern, Innenmass 92*42*26,
  V = **49536 mm^3**, erneut speichern. Export STEP und STL gemaess X;
  ein gueltiger Solid bzw. geschlossenes Mesh ohne Body-Duplikation.

## A2: Wellen-/Flanschbauteil

Matrix: I05-I07/I16-I17/I20/I23/I26/I34-I36, N07-N13/N17.
Teilgate Stufen 5/6, kompletter Workflow Stufe 8, final Stufe 12.

- Ein rotationssymmetrischer Body/Solid: Flansch Radius 30, z=0..8;
  koaxiale Welle Radius 10, z=8..48. Axiale Durchgangsbohrung Radius 4 ueber
  z=0..48. Vier Durchgangsloecher Radius 3 im Flansch auf Teilkreisradius 22,
  z=0..8, 0/90/180/270 Grad, als parametrisches Polarmuster.
- Rotationsprofil voll bestimmt; Revolution, Hole/Pocket und Polarmuster
  nachvollziehbar im Featurebaum. Achse und Lochkanten geometrisch auswaehlen.
- Sollvolumen `(30^2*8 + 10^2*40 - 4^2*48 - 4*3^2*8)*pi`
  = **10144*pi mm^3**, BBox 60/60/48; Lochanzahl vier, kein Gewinde erforderlich.
- Bearbeiten: Wellenlaenge 40 auf 50, Gesamthoehe 58, Durchgang bleibt offen,
  V = **10984*pi mm^3**. Undo/Redo, Lochzentren und Teilkreis unveraendert.
- Negativ: Musteranzahl 0 sowie mehrdeutige/veraltete Kantenreferenz nach
  Profilwechsel; keine stille Kantenneuzuordnung und kein defekter Tip.
- G-Dateizyklus bei Laenge 50; danach Teilkreisradius 22 auf 23, V unveraendert,
  vier Zentren auf Radius 23. Speichern, STEP/STL exportieren und nach X pruefen.

## A3: Parametrischer Schraubstock

Matrix: N03-N08/N10/N12/N16-N17, I27-I37. Gate Stufe 8, final Stufe 12.
Eine geometrisch idealisierte Referenz, **keine Pflicht zur Reproduktion der
historischen 17-Koerper-Demo** und noch keine Assembly-Gelenkabnahme.

- Fuenf getrennte gueltige Einzelkoerper mit Parametertabelle:
  Basis 120*60*10 bei (0,0,0); feste Backe 15*60*25 bei (0,0,10);
  bewegliche Backe 15*60*25 bei (15+g,0,10), initial g=30;
  vereinfachte Spindel Radius 4, Laenge 70 entlang X ab (15,30,22.5);
  Griff Radius 2, Laenge 40 entlang Y ab (90,10,22.5).
- Backen jeweils mit koaxialer Bohrung Radius 4.5 entlang X durch die
  komplette Backendicke. Volumen Basis=72000, pro Backe=`22500-303.75*pi`,
  Spindel=`1120*pi`, Griff=`160*pi`; Summe = **117000+672.5*pi mm^3**.
  Kontakt Basis/Backen erlaubt, positives Schnittvolumen zwischen diesen
  Komponenten nicht; Spindel hat radiales Spiel 0.5 in den Bohrungen.
- Parameter g steuert Backenplacement. Bearbeiten g=30 auf 45:
  gemessener Abstand paralleler Innenflaechen genau 45, Anzahl/Volumen der
  fuenf Teile unveraendert, Spindel durchquert beide Bohrungen. Undo/Redo.
- Negativ: g=-1 mit unerlaubter Backenueberlappung und nicht vorhandene
  Dokumentreferenz; kontrollierte Ablehnung ohne Teilmodell. Zusaetzlicher
  Job-/Timeout-/Wiederverbindungstest nach G, keine doppelte Komponente.
- Bei g=45 speichern/schliessen/oeffnen; danach g=35 aendern, pruefen und
  speichern. STEP mit fuenf Solids, STL pro Komponente exportieren (Kontakt
  zwischen getrennten Komponenten ist kein zugesagtes druckbares Gesamtmesh).
  Farbliche Unterscheidung und isometrischer Screenshot, alle Teile sichtbar.

## A4: Gelenkbaugruppe

Matrix: N06-N07/N18, I02/I30/I32/I34. Gate Stufe 9, final Stufe 12.

- Native FreeCAD-Assembly mit fixiertem Sockel, einem verknuepften Arm und
  Schlitten aus separatem Komponentendokument. Arm zwischen zwei Referenzpunkten
  Laenge 60; Schlittenachse entlang Arm. Ein Revolute-Gelenk am Ursprung um Z
  und ein Slider-Gelenk entlang Arm. Ohne vorgegebenen Bewegungszustand genau
  zwei unabhaengige DoF; gespeicherte Gelenkreferenzen statt nur Placements.
- Arm-Messpunkt bei (60,0,0) im lokalen Arm-System. Zustaende (Winkel, Hub):
  (0 Grad,0), (45 Grad,10), (90 Grad,20). Bei 90 Grad liegt der Arm-Messpunkt
  global bei (0,60,0); Schlittenbewegung parallel gedrehter Armachse, Hub 20.
  Alle Zustandswerte/Placements innerhalb G; kein dynamischer Simulationsanspruch.
- Bearbeiten Armreferenzlaenge 60 auf 70 im Quelldokument; Link und Gelenke
  aktualisieren, Messpunkt bei 90 Grad dann (0,70,0). Undo/Redo dieses Edits.
- Negativ: zusaetzliche widersprechende Fixierung liefert Solverdiagnose und
  Rollback. Bewusst kollidierender Zustand meldet betroffene Komponenten und
  positives Schnittvolumen; die drei normalen Testzustaende ohne Interferenz.
- Alle Quelldokumente und Assembly speichern, nur Testdokumente schliessen,
  erneut laden; Links/Gelenktypen/Parameter/Placements erhalten. Fehlende
  Quelldatei in separater Kopie pruefen: explizit unaufgeloester Link.
- Nach reopen Hub 20 auf 15 stellen, speichern, STEP im aktuellen Zustand:
  drei Komponentensolids und Placements erhalten; Gelenke werden in STEP
  **nicht** erwartet, Verlustbericht gemaess X. Zusaetzliche Joint-Fixtures V.

Technischer Nachweis 2026-10-01: A4 lief zweimal ueber echten MCP-stdio mit je
97 strukturierten Aufrufen auf FreeCAD 1.1.1/Windows. FCStd-Reopen, fehlende
Quelle, drei STEP-Solids, Verlustbericht, Negativrollback und alle fuenf
Gelenkfixtures bestanden. Dies ist das Stufe-9-Gate, nicht die Gesamtabnahme.

## A5: Technische Zeichnung

Matrix: N07/N19, I02/I34, X-Formatvertrag. Gate Stufe 10, final Stufe 12.

**A5/Stufe 10 auf FreeCAD 1.1.1 und 1.1.4 abgenommen am 2026-10-09.**

Frischer 1.1.1-Nachweis: installierte FreeCAD 1.1.1 Build 20260414, native
Python 3.11.14, getrennte eigene TEMP-Konfiguration. Ohne Geometrieanpassung
bestanden: 51 Hosttests (3,255 s), alle 52 nativen Tests (23,476 s), danach
frische Normalmodus-GUI ohne Testvorlauf und zweimal 125 A5-MCP-Aufrufe plus
Cleanup. Voller 48->58->Undo/Redo->FCStd-Reopen->59-Zyklus, sechs native Masse,
Radius/Winkel, Referenz-/Negativ-/Rollback-/Exportgates bestanden.
PDF/SVG je eine A4-Seite; alle fuenf Konturen numerisch mit bestehenden
Toleranzen geprueft, alle vier finalen PNGs visuell kontrolliert. Pflichttexte,
Masszeichen, Schnitt/Detail und Schriftfeld lesbar, keine gefundene Abschneidung.
10a-MCP-Regression ebenfalls zweimal 46 Aufrufe mit beiden Renderern bestanden.
Capability jetzt genau fuer 1.1.1/1.1.4 mit GUI; Raw-Python false, 182 Tools.
Artefakte: `%TEMP%/freecad-stage10b-mcp-ymvmje2o/{report.json,1/,2/}`,
`%TEMP%/freecad-stage10a-mcp-saoppng1/` und native Vollsuite
`%TEMP%/freecad-stage10b-111-native-937416af052f44ea848312f8307d92ad/full.json`.
Eigene Dokumente geschlossen und Prozesse beendet; Port 9943 wieder frei.
Stufen 11/12 nicht begonnen. Kein Installationsupdate oder Release.

Vorheriger 1.1.4-Nachweis (kein erneuter 1.1.4-Lauf in der 1.1.1-Abnahme):

51 Hosttests, 52 native Regressionen; zweimal 125 echte MCP-Aufrufe ohne
Raw-Python in frischer GUI ohne nativen Testvorlauf. First-angle Front/Top/Right,
axialer Schnitt mit Bohrung, Flanschbohrungsdetail 2:1, A4 und Schriftfeld 1:1.
Native References2D-Werte zuerst 60/8/20/8/48/44, danach 58 mit Undo/Redo,
nach Save/Close/Reopen und Dicke 9 zuletzt 60/9/20/8/59/44. Radius 5/Winkel 90
separat per MCP; Arbitrary/Type/MeasureType-Manipulation erkannt.
PDF/SVG je genau eine A4-Seite, valide/nicht leer; fuenf Konturen beider Formate
bei 1:1 bzw. Detail 2:1 mit 0,5 mm Strich-/0,15 mm Papiertoleranz vermessen.
Pflichttexte/Masszeichen/Schnitt/Detail/Schriftfeld visuell kontrolliert;
angeschnittene Ansicht und Textueberlagerungen vor dem finalen Lauf korrigiert.
Vorlage/Schnitt/stale Auswahl, Verlust/Umordnung von Referenzen, identischer
Objektzustand nach Negativrollback, Fremdtransaktion und SHA256-unveraenderte
Zieldateien bei Overwrite-Ablehnung bestanden.
Artefakte: `%TEMP%/freecad-stage10b-mcp-27zfa7ex/{report.json,1/,2/}` mit FCStd,
PDF/SVG, getrennten PNGs, render-report.json und MCP-Transkripten. Native Suite:
`%TEMP%/freecad-stage10b-native-full.json` (52/52, 66,479 s). 10a-MCP-Regression
je 46 Aufrufe mit Renderer: `%TEMP%/freecad-stage10a-mcp-mz6fqlyb/`.
Andere als die beiden geprueften Patchversionen ohne 10b-Zusage; keine universelle Layoutabnahme;
Stufen 11/12 offen. Genaue Uebergabe in [memory.md](../memory.md).

Historischer 10a-Teilnachweis:

Teilumfang 10a vom 2026-10-09, **unter FreeCAD 1.1.4 abgenommen**: Seiten mit benannter
A4-Querformatvorlage, drei Einzelansichten, Schriftfeld/Layout, Quellenedit,
Datei-Reopen und einfache Ausgaben implementiert. Der Teillauf verwendet ein
parametrisches Box-Fixture, nicht A2; das senkt keine der folgenden A5-Kriterien.
50 lokale Tests und alle 48 nativen Regressionen bestanden. Eigene globale
Transaktions-IDs werden jetzt auch nach leeren Updates geschlossen; Fremdbesitz
bleibt geschuetzt. Native `addView`-Zentrierung erfolgt vor der Wunschposition.
`tests/mcp_smoke.py --stage10a-only --stage10a-render`: zwei unabhaengige
vollstaendige Laeufe mit je 46 MCP-Aufrufen bestanden, einschliesslich
Quellen-/Layout-Undo/Redo, Speichern/Schliessen/Reopen, zweiter Quellenaenderung,
Referenzverlust/Undo, Negativrollback und PDF-/SVG-Overwrite-Schutz.
Je ein A4-Querformat-PDF-Blatt und gueltiges SVG, Titelblock und drei getrennte
Ansichten gerendert und visuell kontrolliert. Konturgroesse/-lage mit 0,8 mm
Raster-/Strichbreitentoleranz, Papier mit 0,15 mm PDF-Rundungstoleranz geprueft.
Raw-Python war deaktiviert; keine freie Codeausfuehrung als CAD-Ausweg.
Artefakte/Transkripte: `%TEMP%/freecad-stage10a-mcp-eqzyan01/{1,2}/`.
Dies ist keine Abnahme aller Geometrien, Vorlagen oder frueheren FreeCAD-Versionen.
Die volle A5-Abnahme hat die folgenden unveraenderten Kriterien erfuellt:

- Von A2 eine A4-Querformatseite 297*210 mm mit benannter SVG-Vorlage und
  Schriftfeld, Massstab 1:1. Vorder-/Drauf-/Seitenansicht sowie axialer Schnitt
  mit sichtbarer Bohrung; ein Detail der Flanschbohrung.
- Mindestens sechs modellgebundene Masse: Flanschdurchmesser 60, Flanschdicke 8,
  Wellenradius als Durchmesser 20, Bohrungsdurchmesser 8, Gesamtlaenge 48 und
  Teilkreisdurchmesser 44; dazu Hinweis vier Loecher Durchmesser 6 und Titel.
  Echte TechDraw-Referenzen, keine nur optisch passende Freitextbemaszung.
- Bearbeiten Wellenlaenge 40 auf 50 im Modell: Gesamtmass 58, aktualisierte
  Ansichten/Schnitt, uebrige Sollmasse unveraendert; Undo/Redo samt Zeichnungsupdate.
- Negativ: fehlende Vorlage und verlorene Modellreferenz; explizite Diagnose,
  keine als aktuell ausgegebene veraltete Zeichnung oder halbe Seite nach Fehler.
- Speichern/schliessen/oeffnen inklusive Modellbezug, danach Flanschdicke 8 auf 9:
  Gesamtlaenge 59 bei Wellenlaenge 50, Dickemass 9; speichern und PDF/SVG ausgeben.
- PDF genau eine Seite, SVG valide XML, beide nicht leer, A4 und Massstab korrekt.
  Visuelle Pruefung gerenderter Ausgaben: alle Pflichtansichten und Masse innerhalb
  Blatt, keine abgeschnittenen/ueberlappenden Pflichttexte, Schnitt/Detail lesbar.
  PNG aus 3D-Ansicht allein ist kein Zeichnungsnachweis. V prueft Radius/Winkel.

## X: Austausch- und Informationsvertrag

Nur die folgenden Formate sind Kernumfang. Alle Dateipfade und Auswahlmengen
explizit protokollieren. Import jeweils in frisches Testdokument, Export aus
expliziter Auswahl oder dokumentierter sichtbarer Endauswahl. Keine versteckten
Zwischenfeatures/Body-Duplikate. Leere Auswahl muss fehlschlagen.

| Format | Richtung, Varianten und erhaltener Inhalt | Abnahme und bekannte Grenzen |
| --- | --- | --- |
| FCStd | Save/Save As/open; vollstaendige native Dokumente, Expressions, Skizzen, Features, Links, Assembly, TechDraw | G-Dateizyklus fuer A1-A5; externe Links ueber gemeinsam erhaltene Quelldateien, keine automatische Paketierung zugesagt. |
| STEP | Import/Export; AP214 und AP242 als explizite Zieloptionen, mm; Solids, Placement, Namen/Labels, einfache Baugruppenstruktur und Objektfarben soweit nachgewiesen | Zwei verschiedenfarbige verlinkte Komponenten als Metadatenfixture; Struktur/Farben je Schemaoption pruefen. Nicht verfuegbare Option blockiert Freigabeentscheidung D2; kein stiller Downgrade. Kein Featurebaum/Constraints/Gelenke. |
| STL | Import/Export; ASCII und binaer; Triangulation mit einstellbarer linearer/angularer Abweichung, absolute Toleranzen | Geschlossene Solids nach G; STL enthaelt keine verlaessliche Einheit, mm als explizite Importannahme/Exportvereinbarung; kein Farb-/Struktur-/Parametrikerhalt. |
| OBJ | Import/Export; polygonales Dreiecksmesh, dieselben Triangulationsparameter | Geometrie/Orientierung/BBox nach G, Einheit explizit; kein Material-/Textur-/Baugruppenvertrag, Warnung bei entsprechendem Verlust. Strukturierter Import/Export in 11c nachgewiesen. |
| DXF | Import/Export von planaren Linien/Polylinien, Kreisen/Boegen aus N20, mm | Rechteck 40*20 und Kreis Radius 5: Elementtypen, Abschluss, Koordinaten/Radius nach G; keine 3D-/Bemaeszungs-/Layout-/Spline-Vollabdeckung. |
| SVG (Draft) | Import/Export derselben planaren Geometrie wie DXF, mm bzw. explizite viewBox-Abbildung | 40*20-Test mit Kreis Radius 5 erhaelt Groesse/Elementgeometrie; Pfadkonvertierung erlaubt, keine CSS-/Text-/Bild-Roundtripzusage. |
| PDF/SVG (TechDraw) | Nur Ausgabe, Papiergroesse/Massstab/Ansichten/Masse/Schriftfeld nach A5 | Gerenderte Sichtkontrolle und numerische Massreferenzen; kein PDF-/Zeichnungs-Reimport als Parametrik zugesagt. |

Mesh-Reparaturen liefern Defekte vor/nach Eingriff, angewandte Toleranz und
verbleibende Grenzen. Ein Format ohne Metadaten darf diese nicht als erhalten
melden. STEP-Farb-/Strukturfaehigkeiten sind mit nativer API und echtem MCP
in 11c fuer uniforme geerbte RGB/einfache Linkstruktur nachgewiesen; fehlende
Unterstuetzung weiterer zugesagter Varianten verlangt ausdrueckliche Vertragsentscheidung.

## Stufengates und Abschluss

Stufe 1 ist dokumentarisch erst abgenommen, wenn Inventar/Matrix/Pruefkriterien
konsistent sind und der Benutzer den Umfang bestaetigt hat. Die aktuelle lokale
Verifikation in COVERAGE ist keine funktionale Abnahme der Stufen 2-12.

Jede Implementierungsstufe prueft zuerst den engsten aussagekraeftigen Test,
dann relevante CAD-Integration und echten MCP-Transport. Matrixzeilen und
Varianten erhalten konkrete Test-IDs mit aktuellem Ergebnis, Datum und Umgebung.
Bei Unterbrechung wird die Teilstufe mit Einstiegspunkt in
[memory.md](../memory.md) offengehalten; keine automatische Folgestufe.

Stufe 12 besteht nur, wenn alle Kernvarianten V und A1-A5 jeweils zweimal in
frischen Dokumenten durchgaengig bestanden haben, mit **deaktivierter freier
Codeausfuehrung**, ohne unerledigte Pflichtkriterien. Installations-/Update-/
Neustartpruefung muss geladenen Code und echte Transportverbindung nachweisen.
Direktes RPC `execute` und jeder indirekte Codepfad werden separat negativ
getestet; reine Entfernung des MCP-Tools reicht nicht. Ein Entwicklermodus,
falls beibehalten, ist explizit opt-in, nicht Bestandteil der CAD-Abnahme und
keine Sandbox. Benutzerfreigabe und Testnachweis sind zwei getrennte Gates.

## Bestaetigte Entscheidungen und Restpunkte

Am 2026-09-16 hat der Benutzer auf die ausdrueckliche Frage nach dem Umfang
einschliesslich D1-D5 mit "ja" geantwortet. Damit ist Stufe 1 dokumentarisch
abgenommen. Dies ist kein Auftrag zum Start von Stufe 2 und kein Live-Testnachweis.

| ID | Bestaetigter Umfang | Freigabestatus / Folge |
| --- | --- | --- |
| D1 | Kern exakt nach Matrix inkl. fuenf idealisierten Referenzaufgaben, Teilstufen in bestehender Reihenfolge; FreeCAD 1.1/Windows | Bestaetigt am 2026-09-16. Die alte 17-Koerper-Demo ist nicht zwingende Mindestkomplexitaet. |
| D2 | Native Assembly mit Fixed/Revolute/Slider/Cylindrical/Ball; TechDraw inkl. Schnitt/Detail; begrenztes Draft/Mesh; Formate/Varianten gemaess X | Bestaetigt am 2026-09-16; Assembly-API/Enums und geometrischer STEP-Verlustbericht am 2026-10-01 live belegt. TechDraw, Draft/Mesh und vollstaendige STEP-Metadaten bleiben ihren Stufen vorbehalten. |
| D3 | Numerische Toleranzen nach G; statische diskrete Kollision, vereinfachte Gewinde, keine Fertigungs-/Festigkeitszusagen | Bestaetigt am 2026-09-16; Toleranzaenderungen erfordern dokumentierte Begruendung, nicht nachtraegliche Anpassung an fehlgeschlagene Tests. |
| D4 | Batchlimit 100; ein Dokument atomar, mehrere mit explizitem Teilstatus; kein Datei-Rollback; kein harter Abbruch laufender Kernelberechnungen | Bestaetigt am 2026-09-16; konkrete Fehlercodes/Schema-/Migrationsstrategie in Stufe 2, Jobdetails in Stufe 8. |
| D5 | Normalmodus ohne freie Python-Pfade; Alt-Defaults nur mit dokumentierter Migration; Entwicklermodus optional explizit | Bestaetigt am 2026-09-16; ob Entwicklermodus erhalten bleibt, spaetestens vor Stufe 12 entscheiden. Sein Wegfall verkleinert nicht den CAD-Kern. |
| D6 | FEM ausgeschlossen, CAM/BIM nur auf separaten Auftrag | Durch Benutzerauftrag vorgegeben; keine Aktivierung durch Bestaetigung des Kerns. |

Die verbleibenden technischen Pruefungen und Detailentscheidungen sind durch
die Umfangsbestaetigung nicht erledigt. Neue Varianten nur durch ausdrueckliche Vertragsaenderung mit
Matrix-ID, Zielstufe und messbarem Pruefkriterium aufnehmen.
