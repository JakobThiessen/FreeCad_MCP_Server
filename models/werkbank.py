"""
Werkbank - 2000mm x 1000mm x 900mm
Mit Schubladen auf der rechten Seite.
Verwendet den MCP Server (FreeCADConnection) mit Part-Primitiven.

Aufbau:
- Massive Arbeitsplatte (Buche, 40mm stark)
- 4 Stahlbeine (60x60mm Vierkantrohr)
- Zargenrahmen (Stahlprofil 40x40mm)
- 3 Schubladen rechts (Stahlblech, Vollauszug)
- Ablageboden links unten
"""

import sys
sys.path.insert(0, r"D:\Proj\FreeCad\AI_Server\src")
from freecad_mcp.connection import FreeCADConnection

conn = FreeCADConnection()
if not conn.connect():
    print("FEHLER: Keine Verbindung zu FreeCAD!")
    sys.exit(1)
print(f"Verbunden mit FreeCAD {conn.get_version()}")


def call(module, function, **kwargs):
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    return conn.call_function(module, function, **kwargs)


# === PARAMETER ===
LAENGE = 2000.0       # X-Richtung (2m)
TIEFE = 1000.0        # Y-Richtung (1m)
HOEHE = 900.0         # Z-Richtung (90cm)

# Arbeitsplatte
PLATTE_DICKE = 40.0   # 40mm Buche massiv
PLATTE_UEBERHANG = 20.0  # Ueberstand ueber Beine

# Beine (Vierkantrohr 60x60mm)
BEIN_B = 60.0
BEIN_HOEHE = HOEHE - PLATTE_DICKE  # 860mm

# Zargen (Stahlprofil 40x40mm)
ZARGEN_B = 40.0
ZARGEN_H = 40.0

# Schubladen (3 Stueck, rechte Seite)
SCHUB_ANZAHL = 3
SCHUB_FRONT_DICKE = 3.0    # Frontblech
SCHUB_SEITEN_DICKE = 1.5   # Seitenbleche
SCHUB_SPALT = 3.0           # Spalt zwischen Schubladen
SCHUB_BREITE_AUSSEN = (LAENGE / 2) - BEIN_B - 20.0  # rechte Haelfte minus Bein minus Abstand
SCHUB_TIEFE = TIEFE - 2 * BEIN_B - 40.0  # Tiefe minus Beine minus Luft
# Korrekte Berechnung: verfuegbarer Raum zwischen unterer Zarge und oberer Zarge
_untere_z = 100.0
_zargen_z = BEIN_HOEHE - ZARGEN_H
_schub_start_z = SCHUB_SPALT + _untere_z + ZARGEN_H
_schub_end_z = _zargen_z - SCHUB_SPALT   # Spalt zur oberen Zarge
SCHUB_BEREICH_H = _schub_end_z - _schub_start_z
SCHUB_H = (SCHUB_BEREICH_H - (SCHUB_ANZAHL - 1) * SCHUB_SPALT) / SCHUB_ANZAHL

# Ablageboden (links)
BODEN_DICKE = 18.0    # Spanplatte

# ============================================================
# Neues Dokument
# ============================================================
conn.execute("""
for name in list(FreeCAD.listDocuments().keys()):
    FreeCAD.closeDocument(name)
""")
call("freecad_ai_bridge.operations", "create_document", name="Werkbank")
print("Dokument erstellt")

# ============================================================
# ARBEITSPLATTE
# ============================================================
call("freecad_ai_bridge.part_ops", "make_box",
     length=LAENGE, width=TIEFE, height=PLATTE_DICKE,
     x=0, y=0, z=BEIN_HOEHE,
     name="Arbeitsplatte")
print("Arbeitsplatte erstellt")

# ============================================================
# 4 BEINE (Vierkantrohr)
# ============================================================
# Positionen: Einrueckung = PLATTE_UEBERHANG vom Rand
einr_x = PLATTE_UEBERHANG
einr_y = PLATTE_UEBERHANG

bein_positionen = [
    (einr_x, einr_y, "Bein_VL"),                                    # vorne links
    (LAENGE - einr_x - BEIN_B, einr_y, "Bein_VR"),                  # vorne rechts
    (einr_x, TIEFE - einr_y - BEIN_B, "Bein_HL"),                   # hinten links
    (LAENGE - einr_x - BEIN_B, TIEFE - einr_y - BEIN_B, "Bein_HR"), # hinten rechts
]

for bx, by, name in bein_positionen:
    call("freecad_ai_bridge.part_ops", "make_box",
         length=BEIN_B, width=BEIN_B, height=BEIN_HOEHE,
         x=bx, y=by, z=0, name=name)
print("4 Beine erstellt")

# ============================================================
# ZARGEN (Verbindungen zwischen Beinen)
# ============================================================
# Zargen-Z-Position: oben, direkt unter Platte
zargen_z = BEIN_HOEHE - ZARGEN_H

# Vordere Zarge (X-Richtung, vorne)
call("freecad_ai_bridge.part_ops", "make_box",
     length=LAENGE - 2*einr_x - 2*BEIN_B, width=ZARGEN_B, height=ZARGEN_H,
     x=einr_x + BEIN_B, y=einr_y + (BEIN_B - ZARGEN_B)/2, z=zargen_z,
     name="Zarge_Vorne")

# Hintere Zarge
call("freecad_ai_bridge.part_ops", "make_box",
     length=LAENGE - 2*einr_x - 2*BEIN_B, width=ZARGEN_B, height=ZARGEN_H,
     x=einr_x + BEIN_B, y=TIEFE - einr_y - BEIN_B + (BEIN_B - ZARGEN_B)/2, z=zargen_z,
     name="Zarge_Hinten")

# Linke Zarge (Y-Richtung)
call("freecad_ai_bridge.part_ops", "make_box",
     length=ZARGEN_B, width=TIEFE - 2*einr_y - 2*BEIN_B, height=ZARGEN_H,
     x=einr_x + (BEIN_B - ZARGEN_B)/2, y=einr_y + BEIN_B, z=zargen_z,
     name="Zarge_Links")

# Rechte Zarge
call("freecad_ai_bridge.part_ops", "make_box",
     length=ZARGEN_B, width=TIEFE - 2*einr_y - 2*BEIN_B, height=ZARGEN_H,
     x=LAENGE - einr_x - BEIN_B + (BEIN_B - ZARGEN_B)/2, y=einr_y + BEIN_B, z=zargen_z,
     name="Zarge_Rechts")

print("Zargen erstellt")

# ============================================================
# UNTERE ZARGEN (fuer Stabilitaet + Boden-Auflage links)
# ============================================================
untere_z = 100.0  # 100mm ueber Boden

# Vorne unten
call("freecad_ai_bridge.part_ops", "make_box",
     length=LAENGE - 2*einr_x - 2*BEIN_B, width=ZARGEN_B, height=ZARGEN_H,
     x=einr_x + BEIN_B, y=einr_y + (BEIN_B - ZARGEN_B)/2, z=untere_z,
     name="Zarge_Vorne_U")

# Hinten unten
call("freecad_ai_bridge.part_ops", "make_box",
     length=LAENGE - 2*einr_x - 2*BEIN_B, width=ZARGEN_B, height=ZARGEN_H,
     x=einr_x + BEIN_B, y=TIEFE - einr_y - BEIN_B + (BEIN_B - ZARGEN_B)/2, z=untere_z,
     name="Zarge_Hinten_U")

# Links unten (Y-Richtung)
call("freecad_ai_bridge.part_ops", "make_box",
     length=ZARGEN_B, width=TIEFE - 2*einr_y - 2*BEIN_B, height=ZARGEN_H,
     x=einr_x + (BEIN_B - ZARGEN_B)/2, y=einr_y + BEIN_B, z=untere_z,
     name="Zarge_Links_U")

print("Untere Zargen erstellt")

# ============================================================
# SCHUBLADEN (rechte Seite, 3 Stueck)
# ============================================================
# Schubladen-Bereich: rechte Haelfte, zwischen den Beinen
schub_start_x = LAENGE / 2 + 10.0  # Mitte + etwas Abstand
schub_start_y = einr_y + BEIN_B + 5.0  # Hinter vorderem Bein
schub_start_z = SCHUB_SPALT + untere_z + ZARGEN_H  # Ueber unterer Zarge

for i in range(SCHUB_ANZAHL):
    z_pos = schub_start_z + i * (SCHUB_H + SCHUB_SPALT)
    name_prefix = f"Schublade_{i+1}"

    # Schubladen-Korpus (U-Form: Boden + 2 Seiten)
    # Boden
    call("freecad_ai_bridge.part_ops", "make_box",
         length=SCHUB_BREITE_AUSSEN, width=SCHUB_TIEFE, height=SCHUB_SEITEN_DICKE,
         x=schub_start_x, y=schub_start_y, z=z_pos,
         name=f"{name_prefix}_Boden")

    # Linke Seite
    call("freecad_ai_bridge.part_ops", "make_box",
         length=SCHUB_SEITEN_DICKE, width=SCHUB_TIEFE, height=SCHUB_H - SCHUB_SEITEN_DICKE,
         x=schub_start_x, y=schub_start_y, z=z_pos + SCHUB_SEITEN_DICKE,
         name=f"{name_prefix}_SL")

    # Rechte Seite
    call("freecad_ai_bridge.part_ops", "make_box",
         length=SCHUB_SEITEN_DICKE, width=SCHUB_TIEFE, height=SCHUB_H - SCHUB_SEITEN_DICKE,
         x=schub_start_x + SCHUB_BREITE_AUSSEN - SCHUB_SEITEN_DICKE,
         y=schub_start_y, z=z_pos + SCHUB_SEITEN_DICKE,
         name=f"{name_prefix}_SR")

    # Rueckwand
    call("freecad_ai_bridge.part_ops", "make_box",
         length=SCHUB_BREITE_AUSSEN, width=SCHUB_SEITEN_DICKE, height=SCHUB_H - SCHUB_SEITEN_DICKE,
         x=schub_start_x, y=schub_start_y + SCHUB_TIEFE - SCHUB_SEITEN_DICKE,
         z=z_pos + SCHUB_SEITEN_DICKE,
         name=f"{name_prefix}_Rueck")

    # Front (dicker, sichtbar)
    call("freecad_ai_bridge.part_ops", "make_box",
         length=SCHUB_BREITE_AUSSEN + 10, width=SCHUB_FRONT_DICKE, height=SCHUB_H,
         x=schub_start_x - 5, y=schub_start_y - SCHUB_FRONT_DICKE, z=z_pos,
         name=f"{name_prefix}_Front")

    # Griff (kleiner Zylinder an der Front)
    griff_x = schub_start_x + SCHUB_BREITE_AUSSEN / 2
    griff_z = z_pos + SCHUB_H / 2
    call("freecad_ai_bridge.part_ops", "make_cylinder",
         radius=8.0, height=20.0,
         x=griff_x, y=schub_start_y - SCHUB_FRONT_DICKE - 20, z=griff_z,
         name=f"{name_prefix}_Griff")
    # Griff drehen (90 Grad um X-Achse damit er nach vorne zeigt)
    call("freecad_ai_bridge.part_ops", "rotate_object",
         obj_name=f"{name_prefix}_Griff",
         axis_x=1, axis_y=0, axis_z=0, angle=90)

    print(f"  Schublade {i+1} erstellt")

print(f"{SCHUB_ANZAHL} Schubladen erstellt")

# ============================================================
# ABLAGEBODEN (linke Seite unten)
# ============================================================
boden_x = einr_x + BEIN_B
boden_y = einr_y + BEIN_B
boden_breite = LAENGE/2 - einr_x - BEIN_B - 20  # linke Haelfte
boden_tiefe = TIEFE - 2*einr_y - 2*BEIN_B

call("freecad_ai_bridge.part_ops", "make_box",
     length=boden_breite, width=boden_tiefe, height=BODEN_DICKE,
     x=boden_x, y=boden_y, z=untere_z + ZARGEN_H,
     name="Ablageboden")
print("Ablageboden erstellt")

# ============================================================
# ANSICHT + FARBEN
# ============================================================
conn.execute("""
import FreeCADGui
doc = FreeCAD.ActiveDocument

# Farben setzen
farben = {
    'Arbeitsplatte': (0.76, 0.60, 0.35),   # Holz/Buche
    'Ablageboden': (0.70, 0.55, 0.30),     # Holz dunkler
}

# Stahlteile grau
stahl_teile = ['Bein_VL', 'Bein_VR', 'Bein_HL', 'Bein_HR',
               'Zarge_Vorne', 'Zarge_Hinten', 'Zarge_Links', 'Zarge_Rechts',
               'Zarge_Vorne_U', 'Zarge_Hinten_U', 'Zarge_Links_U']
for name in stahl_teile:
    obj = doc.getObject(name)
    if obj and hasattr(obj, 'ViewObject'):
        obj.ViewObject.ShapeColor = (0.5, 0.5, 0.55)

# Schubladen blaugrau
for i in range(1, 4):
    for suffix in ['_Boden', '_SL', '_SR', '_Rueck', '_Front']:
        obj = doc.getObject(f'Schublade_{i}{suffix}')
        if obj and hasattr(obj, 'ViewObject'):
            obj.ViewObject.ShapeColor = (0.35, 0.40, 0.50)
    # Griffe silber
    obj = doc.getObject(f'Schublade_{i}_Griff')
    if obj and hasattr(obj, 'ViewObject'):
        obj.ViewObject.ShapeColor = (0.75, 0.75, 0.78)

# Holz-Farben
for name, color in farben.items():
    obj = doc.getObject(name)
    if obj and hasattr(obj, 'ViewObject'):
        obj.ViewObject.ShapeColor = color

doc.recompute()
FreeCADGui.updateGui()
FreeCADGui.ActiveDocument.ActiveView.fitAll()
FreeCADGui.ActiveDocument.ActiveView.viewIsometric()

result = {
    'objekte': len(doc.Objects),
    'valid': all(obj.Shape.isValid() for obj in doc.Objects if hasattr(obj, 'Shape')),
}
""")

print(f"\n=== WERKBANK FERTIG ===")
print(f"  Laenge:  {LAENGE}mm (2m)")
print(f"  Tiefe:   {TIEFE}mm (1m)")
print(f"  Hoehe:   {HOEHE}mm (90cm)")
print(f"  Platte:  {PLATTE_DICKE}mm Buche")
print(f"  Beine:   {BEIN_B}x{BEIN_B}mm Vierkantrohr")
print(f"  Schubladen: {SCHUB_ANZAHL} Stueck (rechts)")
print(f"  Schubladenhoehe: {SCHUB_H:.0f}mm je Schublade")
