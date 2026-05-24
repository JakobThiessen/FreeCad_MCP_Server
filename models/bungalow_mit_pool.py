#!/usr/bin/env python3
"""Bungalow mit Pool – FreeCAD Architekturmodell via MCP

Alle Maße in mm. Part::Box für alle Körper. Pultdach 5° als Wedge-Solid.
"""
import os, sys, base64

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from freecad_mcp.connection import FreeCADConnection

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fem_output')
os.makedirs(OUT, exist_ok=True)

conn = FreeCADConnection()
conn.connect()
print("Verbunden mit FreeCAD\n")

# ─── Architekturmodell ──────────────────────────────────────────────────────
build_code = """
global doc, v, Part, FreeCAD, FreeCADGui, math
import FreeCAD, Part, FreeCADGui, math

# Bestehende Dokumente schließen
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
    col=(0.40, 0.62, 0.28))

# ╔══════════════════════════════════════════════════════╗
# ║  2. BUNGALOW_WÄNDE  12m × 15m × 3m                  ║
# ║     Südseite = niedrigeres Y, Nordseite = höheres Y  ║
# ║     Ostseite = höheres X   Wandstärke 250mm          ║
# ╚══════════════════════════════════════════════════════╝
BL = 12000; BW = 15000; BH = 3000
bx = 8000;  by = 7500;  bz = 100   # SW-Ecke (auf Terrain)

box("Bungalow_Wände", BL, BW, BH, bx, by, bz,
    col=(0.95, 0.90, 0.82))

# ╔══════════════════════════════════════════════════════╗
# ║  3. DACH  Pultdach 5°, Überstand 750mm allseitig    ║
# ║     Dachfläche 13500mm × 16500mm                    ║
# ╚══════════════════════════════════════════════════════╝
OV  = 750           # Dachüberstand
rt  = 300           # Dachstärke (senkrecht)
rw  = BL + 2 * OV  # = 13500 mm (Dachbreite)
rd  = BW + 2 * OV  # = 16500 mm (Dachtiefe)
rise = rd * math.tan(math.radians(5))   # ≈ 1443 mm Firsthöhe
rx  = bx - OV;  ry = by - OV;  rz = bz + BH   # Dachposition

# Pultdach als 6-seitiges Wedge-Solid (8 Eckpunkte, lokal in [0,0,0]-Ursprung)
global v
v = [
    FreeCAD.Vector(0,   0,    0       ),  # 0 SW unten (Südtraufe, niedrig)
    FreeCAD.Vector(rw,  0,    0       ),  # 1 SO unten
    FreeCAD.Vector(rw,  rd,   rise    ),  # 2 NO unten (Nordtraufe, hoch)
    FreeCAD.Vector(0,   rd,   rise    ),  # 3 NW unten
    FreeCAD.Vector(0,   0,    rt      ),  # 4 SW oben
    FreeCAD.Vector(rw,  0,    rt      ),  # 5 SO oben
    FreeCAD.Vector(rw,  rd,   rise + rt), # 6 NO oben
    FreeCAD.Vector(0,   rd,   rise + rt), # 7 NW oben
]

def rf(*idx):
    return Part.Face(Part.makePolygon([v[i] for i in idx] + [v[idx[0]]]))

dach_solid = Part.makeSolid(Part.makeShell([
    rf(0, 3, 2, 1),   # Untersicht (Soffit)
    rf(4, 5, 6, 7),   # Dachfläche oben
    rf(0, 1, 5, 4),   # Südtraufe (niedrige Seite)
    rf(1, 2, 6, 5),   # Ostgiebel
    rf(3, 7, 6, 2),   # Nordtraufe (hohe Seite)
    rf(0, 4, 7, 3),   # Westgiebel
]))

dach = doc.addObject("Part::Feature", "Dach")
dach.Label = "Dach"
dach.Shape = dach_solid
dach.Placement = FreeCAD.Placement(
    FreeCAD.Vector(rx, ry, rz),
    FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 0))
dach.ViewObject.ShapeColor   = (0.35, 0.35, 0.38)
dach.ViewObject.Transparency = 0

# ╔══════════════════════════════════════════════════════╗
# ║  4. FENSTER  Südseite  3 ×  1,2m × 1,4m            ║
# ╚══════════════════════════════════════════════════════╝
FW = 1200;  FH = 1400;  FD = 60
sill_z = bz + 900          # Brüstungshöhe 900mm
gap    = (BL - 3 * FW) / 4  # gleichmäßige Abstände = 2100mm

for i, fn in enumerate(["Fenster_Sued_1", "Fenster_Sued_2", "Fenster_Sued_3"]):
    box(fn, FW, FD, FH,
        bx + gap + i * (FW + gap),
        by - FD,
        sill_z,
        col=(0.60, 0.83, 0.96), tr=30)

# ╔══════════════════════════════════════════════════════╗
# ║  5. EINGANGSTÜR  Nordseite  1m × 2,1m               ║
# ╚══════════════════════════════════════════════════════╝
box("Eingangstur_Nord", 1000, 60, 2100,
    bx + (BL - 1000) / 2,
    by + BW,
    bz,
    col=(0.50, 0.30, 0.12))

# ╔══════════════════════════════════════════════════════╗
# ║  6. POOL_BECKEN  7m × 10m × 1,5m                    ║
# ║     4m Abstand Ostseite Bungalow                     ║
# ║     Oberkante +300mm über Geländeniveau              ║
# ╚══════════════════════════════════════════════════════╝
px = bx + BL + 4000        # = 24000  (4m östlich der Bungalow-Ostseite)
py = by + (BW - 10000) // 2  # = 10000  (N-S zentriert auf Bungalow)

pool_rim   = 100 + 300     # z Oberkante Pool = 400mm (300mm über Terrain)
pool_depth = 1500
pool_z     = pool_rim - pool_depth  # = −1100mm

box("Pool_Becken", 7000, 10000, pool_depth,
    px, py, pool_z,
    col=(0.15, 0.48, 0.85), tr=15)

# ╔══════════════════════════════════════════════════════╗
# ║  7. POOL_UMRANDUNG  30cm Beckenrand (4 Segmente)    ║
# ║     Höhe: Terrain-OK bis Pool-Rim = 300mm            ║
# ╚══════════════════════════════════════════════════════╝
rim = 300
urh = pool_rim - 100   # Umrandungshöhe = 300mm (von Terrain bis Pool-Oberkante)

# Süd-Rand  (volle Breite inkl. Ecken)
box("Pool_Umrandung",   7000 + 2*rim, rim, urh,
    px - rim, py - rim, 100,        col=(0.82, 0.79, 0.72))
# Nord-Rand
box("Pool_Umrandung_N", 7000 + 2*rim, rim, urh,
    px - rim, py + 10000, 100,      col=(0.82, 0.79, 0.72))
# West-Rand  (ohne Ecken → sauberer Rahmen)
box("Pool_Umrandung_W", rim, 10000, urh,
    px - rim, py, 100,              col=(0.82, 0.79, 0.72))
# Ost-Rand
box("Pool_Umrandung_E", rim, 10000, urh,
    px + 7000, py, 100,             col=(0.82, 0.79, 0.72))

# ─── Recompute + isometrische Ansicht ───────────────────────────────────────
doc.recompute()
FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
FreeCADGui.ActiveDocument.ActiveView.fitAll()

result = {
    'objekte':    [o.Name for o in doc.Objects],
    'rise_mm':    round(rise, 0),
    'pool_rim_z': pool_rim,
    'status':     'ok'
}
"""

print("[1] Erstelle Architekturmodell (Bungalow + Pool)...")
r = conn.execute(build_code)
print(f"    {r}\n")

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
                         width=1200, height=800, view="isometric")
if isinstance(scr, dict) and 'image_base64' in scr:
    img = base64.b64decode(scr['image_base64'])
    scr_path = os.path.join(OUT, 'bungalow_mit_pool.png')
    with open(scr_path, 'wb') as f:
        f.write(img)
    print(f"    → bungalow_mit_pool.png  ({len(img)//1024} kB)\n")
else:
    print(f"    Screenshot-Ergebnis: {scr}\n")

# ─── Zusammenfassung ────────────────────────────────────────────────────────
print("═" * 62)
print("  Bungalow mit Pool – FreeCAD Architekturmodell fertig")
print("═" * 62)
print(f"  Bungalow:  12m × 15m, Wandhöhe 3m, Pultdach 5°")
print(f"             Dachüberstand 750mm → Dach 13,5m × 16,5m")
print(f"             3 Fenster Süd (1,2×1,4m), 1 Tür Nord (1×2,1m)")
print(f"  Pool:      7m × 10m, Tiefe 1,5m")
print(f"             Abstand 4m von Bungalow-Ostseite")
print(f"             Beckenrand 300mm breit, +300mm über Terrain")
print(f"  Terrain:   35m × 30m × 0,1m")
print(f"  Datei:     models/Bungalow_mit_Pool.FCStd")
print(f"  Bild:      fem_output/bungalow_mit_pool.png")
print("═" * 62)
print(f"  Objekte:")
if isinstance(r, dict) and 'objekte' in r:
    for name in r['objekte']:
        print(f"    • {name}")
print("═" * 62)
