#!/usr/bin/env python3
"""Bungalow mit Pool – v2: Satteldach + Innenaufteilung + Terrasse

Alle Maße in mm.
Satteldach: 20° Neigung, First läuft E-W (Giebel an O und W), Traufen an N und S.
Außenwände semi-transparent → Innenraumaufteilung sichtbar.
"""
import os, sys, base64

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from freecad_mcp.connection import FreeCADConnection

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fem_output')
os.makedirs(OUT, exist_ok=True)

conn = FreeCADConnection()
conn.connect()
print("Verbunden mit FreeCAD\n")

# ─── Architekturmodell v2 ────────────────────────────────────────────────────
build_code = """
global doc, v, Part, FreeCAD, FreeCADGui, math
import FreeCAD, Part, FreeCADGui, math

for _n in list(FreeCAD.listDocuments().keys()):
    FreeCAD.closeDocument(_n)

doc = FreeCAD.newDocument('Bungalow_mit_Pool')

# ── Part::Box Hilfsfunktion ──────────────────────────────────────────────────
def box(name, L, W, H, x=0, y=0, z=0, col=(0.8, 0.8, 0.8), tr=0):
    o = doc.addObject("Part::Box", name)
    o.Label  = name
    o.Length = L;  o.Width  = W;  o.Height = H
    o.Placement = FreeCAD.Placement(
        FreeCAD.Vector(x, y, z),
        FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 0))
    o.ViewObject.ShapeColor   = col
    o.ViewObject.Transparency = tr
    return o

# ╔══════════════════════════════════════════════════════╗
# ║  1. TERRAIN  35m × 30m × 0,1m                       ║
# ╚══════════════════════════════════════════════════════╝
box("Terrain", 35000, 30000, 100, 0, 0, 0,
    col=(0.38, 0.60, 0.26))

# ╔══════════════════════════════════════════════════════╗
# ║  2. BUNGALOW  Außenwände 12m × 15m × 3m             ║
# ║     semi-transparent → Innenraumaufteilung sichtbar  ║
# ╚══════════════════════════════════════════════════════╝
BL = 12000; BW = 15000; BH = 3000
bx = 8000;  by = 7500;  bz = 100
WT = 250    # Außenwandstärke mm

box("Bungalow_Wände", BL, BW, BH, bx, by, bz,
    col=(0.95, 0.90, 0.82), tr=60)

# ╔══════════════════════════════════════════════════════╗
# ║  3. INNENRAUMAUFTEILUNG  (5 Trennwände, 6 Räume)    ║
# ║                                                      ║
# ║  Grundriss (Innen):                                  ║
# ║  N ┌──────────────────────┐                          ║
# ║    │ Küche     │ SZ3     │ Bad                       ║
# ║    │  5,2×6,6  │ 6,1×3,9 │ 6,1×2,6                  ║
# ║    ├───────────┼─────────┴──┤                        ║
# ║    │ Wohn-/Esszimmer │SZ1 │SZ2 │                     ║
# ║    │  5,75×7,75mm    │3,0 │2,6 │                     ║
# ║  S └─────────────────┴────┴────┘                     ║
# ╚══════════════════════════════════════════════════════╝
IWT = 150   # Innenwandstärke mm
IWH = BH    # Innenwandhöhe (volle Raumhöhe)
IWC = (0.88, 0.83, 0.76)   # Innenwandfarbe (beige-braun)

# Innen-Grenzen (Innenflächen der Außenwände)
ix0 = bx + WT          # = 8250  (West-Innen)
ix1 = bx + BL - WT     # = 19750 (Ost-Innen)
iy0 = by + WT          # = 7750  (Süd-Innen)
iy1 = by + BW - WT     # = 22250 (Nord-Innen)

# ── Trennwand 1: Quer-Trennwand (E-W), 8m von Süd ──────────────────────────
y_Q = by + 8000        # = 15500  absolute y-Pos der Wand
box("Wand_Quer", ix1 - ix0, IWT, IWH,
    ix0, y_Q, bz, col=IWC)

# ── Trennwand 2: Längs-Trennwand Süd (N-S), Wohnzimmer / SZ-Bereich ────────
x_S1 = bx + 6000       # = 14000  (6m von Westwand)
box("Wand_WZ_SZ", IWT, y_Q - iy0, IWH,
    x_S1, iy0, bz, col=IWC)
# Rooms so far in south zone:
#   WZ:  x 8250..14000  = 5750mm breit  × 7750mm tief  ≈ 44m²
#   SE:  x 14150..19750 = 5600mm breit  × 7750mm tief  → wird weiter geteilt

# ── Trennwand 3: Längs-Trennwand Süd Ost (N-S), SZ1 / SZ2 ─────────────────
x_S2 = bx + 9100       # = 17100  (SZ1: 3100mm breit, SZ2: 2650mm breit)
box("Wand_SZ1_SZ2", IWT, y_Q - iy0, IWH,
    x_S2, iy0, bz, col=IWC)
# SZ1: x 14150..17100 = 2950mm breit × 7750mm  ≈ 23m²
# SZ2: x 17250..19750 = 2500mm breit × 7750mm  ≈ 19m²

# ── Trennwand 4: Längs-Trennwand Nord (N-S), Küche / SZ3+Bad ────────────────
x_N1 = bx + 5500       # = 13500  (5,5m von Westwand)
box("Wand_Kue_SZ3", IWT, iy1 - (y_Q + IWT), IWH,
    x_N1, y_Q + IWT, bz, col=IWC)
# Küche: x 8250..13500  = 5250mm breit × 6600mm tief  ≈ 34m²
# NE:    x 13650..19750 = 6100mm breit × 6600mm tief  → wird geteilt

# ── Trennwand 5: Quer-Trennwand Nord-Ost (E-W), SZ3 / Bad ──────────────────
y_N2 = by + 12000      # = 19500  (SZ3: 3850mm, Bad: 2750mm tief)
box("Wand_SZ3_Bad", ix1 - (x_N1 + IWT), IWT, IWH,
    x_N1 + IWT, y_N2, bz, col=IWC)
# SZ3: x 13650..19750 y 15650..19500 = 6100 × 3850mm  ≈ 23m²
# Bad: x 13650..19750 y 19650..22250 = 6100 × 2600mm  ≈ 16m²

# ╔══════════════════════════════════════════════════════╗
# ║  4. SATTELDACH  20° Neigung                         ║
# ║     First läuft E-W (Längsachse 12m)               ║
# ║     Giebel: Ost + West; Traufen: Nord + Süd         ║
# ║     Dachüberstand 750mm allseitig                    ║
# ╚══════════════════════════════════════════════════════╝
OV  = 750             # Dachüberstand mm
rw  = BL + 2 * OV    # = 13500 mm (E-W, Trauflänge)
rd  = BW + 2 * OV    # = 16500 mm (N-S, Giebelbreite)
rh  = (rd / 2) * math.tan(math.radians(20))  # ≈ 3003 mm Firsthöhe
rx  = bx - OV        # = 7250
ry  = by - OV        # = 6750
rz  = bz + BH        # = 3100 (Traufhöhe = Wandoberkante)

# 6 Eckpunkte des Satteldach-Prismas (lokal, Ursprung SW-Traufe)
global v
v = [
    FreeCAD.Vector(0,    0,      0),     # 0  SW Traufe  (Süd-West)
    FreeCAD.Vector(rw,   0,      0),     # 1  SE Traufe  (Süd-Ost)
    FreeCAD.Vector(rw,   rd,     0),     # 2  NE Traufe  (Nord-Ost)
    FreeCAD.Vector(0,    rd,     0),     # 3  NW Traufe  (Nord-West)
    FreeCAD.Vector(rw,   rd/2,   rh),    # 4  First-Ost  (Ostgiebel-Spitze)
    FreeCAD.Vector(0,    rd/2,   rh),    # 5  First-West (Westgiebel-Spitze)
]

def mf(*pts):
    return Part.Face(Part.makePolygon(list(pts) + [pts[0]]))

faces = [
    mf(v[0], v[3], v[2], v[1]),    # Untersicht  (Soffit, zeigt nach unten)
    mf(v[0], v[1], v[4], v[5]),    # Süd-Dachfläche
    mf(v[3], v[5], v[4], v[2]),    # Nord-Dachfläche
    mf(v[0], v[5], v[3]),          # Westgiebel  (Dreieck)
    mf(v[1], v[2], v[4]),          # Ostgiebel   (Dreieck)
]

dach_solid = Part.makeSolid(Part.makeShell(faces))
dach = doc.addObject("Part::Feature", "Dach")
dach.Label = "Dach"
dach.Shape = dach_solid
dach.Placement = FreeCAD.Placement(
    FreeCAD.Vector(rx, ry, rz),
    FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 0))
dach.ViewObject.ShapeColor   = (0.28, 0.22, 0.18)   # Dunkelbraun (Ziegel)
dach.ViewObject.Transparency = 0

# ╔══════════════════════════════════════════════════════╗
# ║  5. FENSTER  Südseite 3 ×  1,4m × 1,5m             ║
# ╚══════════════════════════════════════════════════════╝
FW = 1400; FH = 1500; FD = 100
sill_z = bz + 800
gap    = (BL - 3 * FW) / 4   # = 1950mm

for i, fn in enumerate(["Fenster_Sued_1", "Fenster_Sued_2", "Fenster_Sued_3"]):
    fx = bx + gap + i * (FW + gap)
    # Fensterrahmen (dunkel)
    box(fn + "_Rahmen", FW, FD, FH,
        fx, by - FD, sill_z,
        col=(0.22, 0.18, 0.14), tr=0)
    # Glasscheibe (hellblau, innen)
    box(fn, FW - 100, FD + 40, FH - 100,
        fx + 50, by - FD / 2, sill_z + 50,
        col=(0.60, 0.83, 0.96), tr=25)

# ╔══════════════════════════════════════════════════════╗
# ║  6. EINGANGSTÜR  Nordseite  1m × 2,1m               ║
# ╚══════════════════════════════════════════════════════╝
box("Eingangstur_Nord", 1000, 100, 2100,
    bx + (BL - 1000) / 2,
    by + BW,
    bz,
    col=(0.42, 0.26, 0.10))

# ╔══════════════════════════════════════════════════════╗
# ║  7. TERRASSE  (Südfassade, 12m × 3m)                ║
# ╚══════════════════════════════════════════════════════╝
box("Terrasse", BL, 3000, 60,
    bx, by - 3000, 100,
    col=(0.72, 0.68, 0.62))

# ╔══════════════════════════════════════════════════════╗
# ║  8. GARTENWEG  (Nordeingang → Grundstücksgrenze)    ║
# ╚══════════════════════════════════════════════════════╝
box("Gartenweg", 1500, 30000 - (by + BW), 40,
    bx + (BL - 1500) / 2,
    by + BW,
    100,
    col=(0.58, 0.55, 0.50))

# ╔══════════════════════════════════════════════════════╗
# ║  9. POOL_BECKEN  7m × 10m × 1,5m                   ║
# ╚══════════════════════════════════════════════════════╝
px = bx + BL + 4000           # = 24000
py = by + (BW - 10000) // 2   # = 10000

pool_rim   = 100 + 300        # z Oberkante = 400mm
pool_depth = 1500
pool_z     = pool_rim - pool_depth   # = −1100mm

box("Pool_Becken", 7000, 10000, pool_depth,
    px, py, pool_z,
    col=(0.12, 0.45, 0.85), tr=15)

# ── Pool-Wasseroberfläche (sichtbar von oben) ─────────────────────────────
box("Pool_Wasser", 7000, 10000, 20,
    px, py, pool_rim - 20,
    col=(0.20, 0.60, 0.95), tr=5)

# ╔══════════════════════════════════════════════════════╗
# ║  10. POOL_UMRANDUNG  30cm Beckenrand (4 Segmente)   ║
# ╚══════════════════════════════════════════════════════╝
rim = 300
urh = pool_rim - 100   # = 300mm

box("Pool_Umrandung",   7000 + 2*rim, rim, urh,
    px - rim,    py - rim, 100,  col=(0.82, 0.79, 0.72))
box("Pool_Umrandung_N", 7000 + 2*rim, rim, urh,
    px - rim,    py + 10000, 100, col=(0.82, 0.79, 0.72))
box("Pool_Umrandung_W", rim, 10000, urh,
    px - rim,    py, 100,         col=(0.82, 0.79, 0.72))
box("Pool_Umrandung_E", rim, 10000, urh,
    px + 7000,   py, 100,         col=(0.82, 0.79, 0.72))

# ─── Recompute + isometrische Ansicht ───────────────────────────────────────
doc.recompute()
FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
FreeCADGui.ActiveDocument.ActiveView.fitAll()

result = {
    'objekte':      [o.Name for o in doc.Objects],
    'first_h_mm':   round(rh, 0),
    'räume': {
        'Wohnzimmer':  '5750 × 7750mm = 44m²  (SW, Südfenster)',
        'SZ1':         '2950 × 7750mm = 23m²  (Mitte-Süd)',
        'SZ2':         '2500 × 7750mm = 19m²  (SO)',
        'Küche':       '5250 × 6600mm = 35m²  (NW)',
        'SZ3':         '6100 × 3850mm = 23m²  (NO-Süd)',
        'Bad':         '6100 × 2600mm = 16m²  (NO-Nord)',
    },
    'status': 'ok'
}
"""

print("[1] Erstelle Architekturmodell v2 (Satteldach + Innenaufteilung)...")
r = conn.execute(build_code)
print(f"    Firsthöhe: {r.get('first_h_mm', '?')} mm  (20° Neigung)")
print(f"    Objekte: {len(r.get('objekte', []))} FreeCAD-Objekte")
print(f"    Räume: {list(r.get('räume', {}).keys())}\n")

# ─── Dokument speichern ─────────────────────────────────────────────────────
save_code = r"""
import FreeCAD
FreeCAD.ActiveDocument.saveAs(r"D:\Proj\FreeCad\AI_Server\models\Bungalow_mit_Pool.FCStd")
result = {'saved': True}
"""
print("[2] Speichere Dokument...")
r2 = conn.execute(save_code)
print(f"    {r2}\n")

# ─── Screenshot ─────────────────────────────────────────────────────────────
print("[3] Screenshot (isometrisch)...")
scr = conn.call_function("freecad_ai_bridge.view_ops", "get_screenshot",
                         width=1280, height=900, view="isometric")
if isinstance(scr, dict) and 'image_base64' in scr:
    img = base64.b64decode(scr['image_base64'])
    scr_path = os.path.join(OUT, 'bungalow_mit_pool.png')
    with open(scr_path, 'wb') as f:
        f.write(img)
    print(f"    → bungalow_mit_pool.png  ({len(img)//1024} kB)\n")

# ─── Zusammenfassung ────────────────────────────────────────────────────────
print("═" * 68)
print("  Bungalow mit Pool – v2  (Satteldach + Innenaufteilung)")
print("═" * 68)
print(f"  Bungalow:  12m × 15m, Wandhöhe 3m")
print(f"  Satteldach: 20° Neigung, First läuft E-W, Firsthöhe ≈3,0m")
print(f"             Dachüberstand 750mm → Dach 13,5m × 16,5m")
if isinstance(r, dict) and 'räume' in r:
    print(f"  Innenraum (6 Räume):")
    for name, desc in r['räume'].items():
        print(f"    • {name:12s} {desc}")
print(f"  Terrasse:  12m × 3m (Südseite)")
print(f"  Pool:      7m × 10m, Tiefe 1,5m, Beckenrand 30cm")
print(f"  Terrain:   35m × 30m")
print(f"  Datei:     models/Bungalow_mit_Pool.FCStd")
print(f"  Bild:      fem_output/bungalow_mit_pool.png")
print("═" * 68)
