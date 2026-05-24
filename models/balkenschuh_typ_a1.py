"""
Balkenschuh Typ A1 - nach Massskizze aus testbilder/
Verwendet den MCP Server (FreeCADConnection) mit Part-Primitiven und Boolean-Ops.

Parameter (aus Zeichnung + Benutzervorgabe):
- Breite: 60mm (Innenbreite fuer den Balken)
- Laenge: 160mm (Hoehe der Seitenplatten/Rueckplatte)
- Materialstaerke: 2mm
- Tiefe: 80mm (U-Tiefe, wie tief der Balken reinsitzt)
- Loecher: dia5mm (Naegel), dia11mm (Bolzen)
- 45-Grad-Schnitt an den unteren Flansch-Ecken
"""

import sys
sys.path.insert(0, r"D:\Proj\FreeCad\AI_Server\src")

from freecad_mcp.connection import FreeCADConnection

# === Verbindung zum MCP Server ===
conn = FreeCADConnection(host="127.0.0.1", port=9875)
if not conn.connect():
    print("FEHLER: Keine Verbindung zu FreeCAD!")
    sys.exit(1)
print(f"Verbunden mit FreeCAD {conn.get_version()}")


def call(module, function, **kwargs):
    """MCP-Tool Aufruf (wie server.py _call)"""
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    return conn.call_function(module, function, **kwargs)


# === PARAMETER ===
BREITE = 60.0         # Innenbreite (= Balkenbreite)
LAENGE = 160.0        # Hoehe der Rueckplatte/Flansche (Gesamthoehe)
DICKE = 2.0           # Materialstaerke Stahlblech
TIEFE = 80.0          # U-Tiefe (Balken sitzt so tief drin)
FLANSCH = 42.0        # Flanschbreite (Montagelaschen links/rechts, aus Zeichnung)
U_HOEHE = 100.0       # Hoehe der U-Seitenwaende (aus Zeichnung "100")

# Lochparameter (aus Massskizze)
LOCH_KLEIN = 5.0      # Nagelloch-Durchmesser
LOCH_GROSS = 11.0     # Bolzenloch-Durchmesser
ABST_V = 20.0         # Vertikaler Lochabstand
RAND_OBEN = 8.0       # Abstand Oberkante -> erstes Loch
ABST_H = 18.5         # Horizontaler Abstand zwischen 2 Lochspalten

# Abgeleitete Masse
AUSSEN_B = BREITE + 2 * DICKE             # Aussenbreite des U-Profils (64mm)
GESAMT_B = BREITE + 2 * FLANSCH           # Gesamtbreite mit Flanschen (144mm)
U_START_Z = LAENGE - U_HOEHE              # Z-Position wo die U-Seitenwaende beginnen (60mm)

# ============================================================
# SCHRITT 1: Neues Dokument
# ============================================================
conn.execute("""
for name in list(FreeCAD.listDocuments().keys()):
    FreeCAD.closeDocument(name)
""")
result = call("freecad_ai_bridge.operations", "create_document", name="Balkenschuh_A1")
print(f"Dokument: {result}")

# ============================================================
# SCHRITT 2: Hauptplatten als Part::Box erstellen
# ============================================================

# --- Rueckplatte (Montageplatte): GESAMT_B x DICKE x LAENGE ---
# Liegt in der YZ-Ebene (flach an der Wand)
result = call("freecad_ai_bridge.part_ops", "make_box",
              length=GESAMT_B, width=DICKE, height=LAENGE,
              x=-GESAMT_B/2, y=0.0, z=0.0, name="Rueckplatte")
print(f"Rueckplatte: {result}")

# --- Bodenplatte: BREITE x TIEFE x DICKE ---
# Verbindet die Seitenwaende unten, ragt nach vorne
# Sitzt bei U_START_Z (nicht ganz unten!)
result = call("freecad_ai_bridge.part_ops", "make_box",
              length=BREITE, width=TIEFE, height=DICKE,
              x=-BREITE/2, y=DICKE, z=U_START_Z, name="Bodenplatte")
print(f"Bodenplatte: {result}")

# --- Linke Seitenwand: DICKE x TIEFE x U_HOEHE ---
# Nur 100mm hoch (ab U_START_Z)
result = call("freecad_ai_bridge.part_ops", "make_box",
              length=DICKE, width=TIEFE, height=U_HOEHE,
              x=-BREITE/2 - DICKE, y=DICKE, z=U_START_Z, name="LinkeWand")
print(f"LinkeWand: {result}")

# --- Rechte Seitenwand: DICKE x TIEFE x U_HOEHE ---
result = call("freecad_ai_bridge.part_ops", "make_box",
              length=DICKE, width=TIEFE, height=U_HOEHE,
              x=BREITE/2, y=DICKE, z=U_START_Z, name="RechteWand")
print(f"RechteWand: {result}")

# ============================================================
# SCHRITT 3: Alle Platten verschmelzen (Boolean Fuse)
# ============================================================
result = call("freecad_ai_bridge.part_ops", "boolean_fuse",
              obj_names=["Rueckplatte", "Bodenplatte", "LinkeWand", "RechteWand"],
              name="Balkenschuh_Roh")
print(f"Fuse: {result}")

# ============================================================
# SCHRITT 4: 45-Grad-Schnitte an den Flansch-Ecken (unten)
# ============================================================
# Dreieckige Keile die die unteren Ecken der Flansche abschneiden
# Verwende execute_python fuer die Dreiecks-Extrusion
conn.execute(f"""
import Part
from FreeCAD import Vector

doc = FreeCAD.ActiveDocument

# Linker Flansch: Dreieck unten-links
# Flansch geht von x=-{GESAMT_B/2} bis x=-{BREITE/2}
# Schnitt: 45 Grad, Hoehe = Flanschbreite
flansch_L_start = -{GESAMT_B/2}
flansch_L_end = -{BREITE/2}
flansch_R_start = {BREITE/2}
flansch_R_end = {GESAMT_B/2}
schnitt_h = {FLANSCH}  # 45 Grad: Hoehe = Breite des Flanschs

# Linkes Dreieck (Schneidkoerper)
pts_L = [
    Vector(flansch_L_start, -1, 0),
    Vector(flansch_L_end, -1, 0),
    Vector(flansch_L_end, -1, schnitt_h),
    Vector(flansch_L_start, -1, 0),
]
wire_L = Part.makePolygon(pts_L)
face_L = Part.Face(wire_L)
cut_L = face_L.extrude(Vector(0, {DICKE + 2}, 0))
obj_L = doc.addObject('Part::Feature', 'CutL')
obj_L.Shape = cut_L

# Rechtes Dreieck
pts_R = [
    Vector(flansch_R_start, -1, 0),
    Vector(flansch_R_end, -1, 0),
    Vector(flansch_R_start, -1, schnitt_h),
    Vector(flansch_R_start, -1, 0),
]
wire_R = Part.makePolygon(pts_R)
face_R = Part.Face(wire_R)
cut_R = face_R.extrude(Vector(0, {DICKE + 2}, 0))
obj_R = doc.addObject('Part::Feature', 'CutR')
obj_R.Shape = cut_R

doc.recompute()
result = 'ok'
""")

# Ecken abschneiden
result = call("freecad_ai_bridge.part_ops", "boolean_cut",
              base_name="Balkenschuh_Roh", tool_name="CutL", name="Balkenschuh_Cut1")
print(f"Cut links: {result}")
result = call("freecad_ai_bridge.part_ops", "boolean_cut",
              base_name="Balkenschuh_Cut1", tool_name="CutR", name="Balkenschuh_Cut2")
print(f"Cut rechts: {result}")

# ============================================================
# SCHRITT 5: Nagelloecher in Rueckplatte (Flansche)
# ============================================================
# Loecher werden als Zylinder erstellt und per Boolean Cut entfernt
conn.execute(f"""
import Part
from FreeCAD import Vector, Placement, Rotation
import math

doc = FreeCAD.ActiveDocument

# Loch-Positionen berechnen
breite = {BREITE}
laenge = {LAENGE}
dicke = {DICKE}
flansch = {FLANSCH}
gesamt_b = {GESAMT_B}
d_klein = {LOCH_KLEIN}
d_gross = {LOCH_GROSS}
abst_v = {ABST_V}
abst_h = {ABST_H}
rand_oben = {RAND_OBEN}

# Flansch-Mitten (X-Position)
flansch_mitte_L = -(breite/2 + flansch/2)
flansch_mitte_R = (breite/2 + flansch/2)

# Loch-Spalten X-Positionen (2 Spalten pro Flansch)
col_L1 = flansch_mitte_L - abst_h/2
col_L2 = flansch_mitte_L + abst_h/2
col_R1 = flansch_mitte_R - abst_h/2
col_R2 = flansch_mitte_R + abst_h/2

# Vertikale Positionen (von oben: rand_oben, dann +abst_v)
z_positionen = []
z = laenge - rand_oben
while z > 5:
    z_positionen.append(z)
    z -= abst_v

# Alle Nagelloecher als ein CompoundShape
cylinders = []
r_klein = d_klein / 2

for z_pos in z_positionen:
    for cx in [col_L1, col_L2, col_R1, col_R2]:
        cyl = Part.makeCylinder(r_klein, dicke + 2, Vector(cx, -1, z_pos), Vector(0, 1, 0))
        cylinders.append(cyl)

# Grosses Bolzenloch in der Mitte jedes Flanschs
r_gross = d_gross / 2
z_mitte = laenge / 2
for cx in [flansch_mitte_L, flansch_mitte_R]:
    cyl = Part.makeCylinder(r_gross, dicke + 2, Vector(cx, -1, z_mitte), Vector(0, 1, 0))
    cylinders.append(cyl)

# Alle Zylinder zu einem Compound vereinen
if cylinders:
    compound = cylinders[0]
    for c in cylinders[1:]:
        compound = compound.fuse(c)
    obj = doc.addObject('Part::Feature', 'BackHoles')
    obj.Shape = compound

doc.recompute()
result = {{'holes': len(cylinders)}}
""")
print("Rueckplatten-Loecher erstellt")

# Loecher ausschneiden
result = call("freecad_ai_bridge.part_ops", "boolean_cut",
              base_name="Balkenschuh_Cut2", tool_name="BackHoles", name="Balkenschuh_Cut3")
print(f"Loecher Rueckplatte: {result}")

# ============================================================
# SCHRITT 6: Nagelloecher in Seitenwaenden
# ============================================================
conn.execute(f"""
import Part
from FreeCAD import Vector
import math

doc = FreeCAD.ActiveDocument

breite = {BREITE}
laenge = {LAENGE}
dicke = {DICKE}
tiefe = {TIEFE}
d_klein = {LOCH_KLEIN}
abst_v = {ABST_V}
rand_oben = {RAND_OBEN}
u_start_z = {U_START_Z}
u_hoehe = {U_HOEHE}

r_klein = d_klein / 2

# Vertikale Positionen NUR im U-Bereich (ab u_start_z bis oben)
z_positionen = []
z = laenge - rand_oben
while z > u_start_z + 10:
    z_positionen.append(z)
    z -= abst_v

# Lochspalten in Y-Richtung (Tiefe der Seitenwand)
# 2 Spalten: bei 25mm und 55mm Tiefe
sw_col1 = dicke + 25.0
sw_col2 = dicke + 55.0

# Linke Wand: X = -breite/2 - dicke (Mitte des Materials)
x_L = -breite/2 - dicke/2
x_R = breite/2 + dicke/2

cylinders = []
for z_pos in z_positionen:
    for y_pos in [sw_col1, sw_col2]:
        # Linke Wand (Loch in X-Richtung)
        cyl = Part.makeCylinder(r_klein, dicke + 2, Vector(x_L - dicke, y_pos, z_pos), Vector(1, 0, 0))
        cylinders.append(cyl)
        # Rechte Wand
        cyl = Part.makeCylinder(r_klein, dicke + 2, Vector(x_R - 1, y_pos, z_pos), Vector(1, 0, 0))
        cylinders.append(cyl)

if cylinders:
    compound = cylinders[0]
    for c in cylinders[1:]:
        compound = compound.fuse(c)
    obj = doc.addObject('Part::Feature', 'SideHoles')
    obj.Shape = compound

doc.recompute()
result = {{'holes': len(cylinders)}}
""")
print("Seitenwand-Loecher erstellt")

result = call("freecad_ai_bridge.part_ops", "boolean_cut",
              base_name="Balkenschuh_Cut3", tool_name="SideHoles", name="Balkenschuh")
print(f"Fertiger Balkenschuh: {result}")

# ============================================================
# SCHRITT 7: Aufraeumen und Ansicht
# ============================================================
conn.execute("""
import FreeCADGui
doc = FreeCAD.ActiveDocument

# Nur das Endergebnis anzeigen
for obj in doc.Objects:
    if obj.Name != 'Balkenschuh' and hasattr(obj, 'Visibility'):
        obj.Visibility = False

doc.getObject('Balkenschuh').Visibility = True
doc.recompute()

FreeCADGui.updateGui()
FreeCADGui.ActiveDocument.ActiveView.fitAll()
FreeCADGui.ActiveDocument.ActiveView.viewIsometric()

body = doc.getObject('Balkenschuh')
result = {
    'volumen_cm3': round(body.Shape.Volume / 1000, 2),
    'valid': body.Shape.isValid(),
    'bounding_box': {
        'breite_mm': round(body.Shape.BoundBox.XLength, 1),
        'tiefe_mm': round(body.Shape.BoundBox.YLength, 1),
        'hoehe_mm': round(body.Shape.BoundBox.ZLength, 1),
    }
}
""")

# Abschlussbericht
final = conn.execute("""
doc = FreeCAD.ActiveDocument
body = doc.getObject('Balkenschuh')
result = {
    'volumen_cm3': round(body.Shape.Volume / 1000, 2),
    'valid': body.Shape.isValid(),
    'bounding_box': {
        'breite_mm': round(body.Shape.BoundBox.XLength, 1),
        'tiefe_mm': round(body.Shape.BoundBox.YLength, 1),
        'hoehe_mm': round(body.Shape.BoundBox.ZLength, 1),
    }
}
""")
print(f"\n=== BALKENSCHUH TYP A1 FERTIG ===")
print(f"Ergebnis: {final}")
print(f"\nParameter:")
print(f"  Innenbreite: {BREITE}mm")
print(f"  Hoehe:       {LAENGE}mm")
print(f"  U-Tiefe:     {TIEFE}mm")
print(f"  Material:    {DICKE}mm Stahlblech")
print(f"  Flansch:     {FLANSCH}mm")
