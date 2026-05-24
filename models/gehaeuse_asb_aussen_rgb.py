"""
Gehäuse für PCB "ASB_AUSSEN_RGB"
================================
5× Power-RGB-LEDs, 2× M3.2-Befestigungsbohrungen.

Gemessene PCB-Daten (aus FreeCAD-Modell):
  PCB:     25.02 × 89.79 × 1.51 mm
  LEDs:    5× RGBWA, 9×14.5×5.89 mm, oben auf PCB (Oberkante Z=7.29 mm)
  Stecker: PinHeader 1×8, 8.63 mm unter PCB-Boden
  Löcher:  2× M3.2 bei PCB-lokal (4.445 / 14.987) und (4.445 / 85.345) mm

Gehäuse-Design:
  Außen:          30 × 95 × 24 mm (B × L × H inkl. Deckel)
  Körper:         30 × 95 × 22 mm, oben offen, Wandstärke 2 mm
  Eckenradius:    3 mm außen / 1 mm innen
  Deckel:         30 × 95 × 2 mm, Polycarbonat klar (transparent, LEDs zeigen durch)
  Montage:        2× M3-Abstandshalter (Ø7 mm/M3, Höhe 10 mm)
  Kabelausgang:   Vorderwand (22 × 15 mm Schlitz) für Anschlusskabel
  PCB-Position:   X=2.48, Y=2.5, Z=12.0 mm (10 mm Freiraum für Stecker unten)
  LED-Spitze:     Z=19.3 mm → 2.7 mm Luft zur Deckelunterseite
"""

import sys, os, base64
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from freecad_mcp.connection import FreeCADConnection

conn = FreeCADConnection()
conn.connect()
print("Connected to FreeCAD")

OUT = os.path.join(os.path.dirname(__file__), "fem_output")

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK 1 – Gehäuse-Körper + Deckel + Abstandshalter + Referenzobjekte
# ═══════════════════════════════════════════════════════════════════════════════
BUILD_CODE = r"""
global doc, Part, FreeCAD, FreeCADGui, math, make_rb, V
import FreeCAD, Part, FreeCADGui, math

# Altes Dokument schließen falls vorhanden
try:
    FreeCAD.closeDocument("Gehaeuse_ASB")
except Exception:
    pass

doc = FreeCAD.newDocument("Gehaeuse_ASB")
FreeCAD.setActiveDocument("Gehaeuse_ASB")

# ── Maße (mm) ─────────────────────────────────────────────────────────────────
W      = 30.0    # Außenbreite  X
L      = 95.0    # Außenlänge   Y  (Kabelseite bei Y=0)
H_BOD  = 22.0    # Körperhöhe   Z  (oben offen, Deckel separat)
H_LID  = 2.0     # Deckeldicke
TW     = 2.0     # Wandstärke
CR     = 3.0     # Eckradius außen
CR_IN  = 1.0     # Eckradius innen

# PCB-Lage im Gehäuse (Gehäuse-Lokalkoordinaten)
PCB_W  = 25.02
PCB_L  = 89.79
PCB_T  = 1.51
PCB_X  = 2.48    # PCB-Linksrand (WALL=2 + 0.48 mm Spalt links)
PCB_Y  = 2.50    # PCB-Vorderkante (WALL=2 + 0.5 mm Spalt vorne)
PCB_Z  = 12.0    # PCB-Boden Z (Stecker-Freiraum = PCB_Z - TW = 10 mm)

# Befestigungsbohrungen (PCB-lokal, gemessen aus FreeCAD)
HOLE1  = (4.445, 14.987)   # X_lokal, Y_lokal von PCB-Ursprung
HOLE2  = (4.445, 85.345)

# Abstandshalter
BOSS_R  = 3.5    # Außenradius
BOSS_RI = 1.5    # M3-Bohrungsradius
BOSS_H  = PCB_Z - TW   # 10 mm (von Gehäuseboden-Innenseite bis PCB-Boden)

V = FreeCAD.Vector

# ── Helper: gerundete Box via makeFillet auf Vertikalkanten ───────────────────
def make_rb(w, l, h, r, x=0.0, y=0.0, z=0.0):
    global Part, FreeCAD
    s = Part.makeBox(w, l, h, FreeCAD.Vector(x, y, z))
    if r > 0.05 and h > 0.05:
        vert = [e for e in s.Edges if abs(e.Length - h) < 0.05]
        if len(vert) >= 4:
            try:
                s = s.makeFillet(min(r, w / 2.0 - 0.05, l / 2.0 - 0.05), vert[:4])
            except Exception:
                pass   # Fillet fehlgeschlagen → normaler Quader
    return s

# ── 1. Gehäuse-Körper ─────────────────────────────────────────────────────────
outer = make_rb(W, L, H_BOD, CR)
inner = make_rb(W - 2*TW, L - 2*TW, H_BOD - TW, CR_IN, TW, TW, TW)
body  = outer.cut(inner)

# Kabelschlitz in Vorderwand (Y=0-Seite): 22 × 15 mm, Z=3..18 mm
body = body.cut(Part.makeBox(22.0, TW + 0.2, 15.0, V(4.0, -0.1, 3.0)))

o_body = doc.addObject("Part::Feature", "Gehaeuse_Koerper")
o_body.Label  = "Gehäuse-Körper"
o_body.Shape  = body
o_body.ViewObject.ShapeColor  = (0.18, 0.18, 0.22)
o_body.ViewObject.Transparency = 0

# ── 2. Transparente Frontscheibe (Deckel, oben) ───────────────────────────────
lid = make_rb(W, L, H_LID, CR, 0.0, 0.0, H_BOD)

# M3-Durchgangsbohrungen im Deckel (Schrauben von oben einstecken)
for (hx_l, hy_l) in [HOLE1, HOLE2]:
    lid = lid.cut(
        Part.makeCylinder(1.6, H_LID + 0.2,
                          V(PCB_X + hx_l, PCB_Y + hy_l, H_BOD - 0.1),
                          V(0, 0, 1))
    )

o_lid = doc.addObject("Part::Feature", "Frontscheibe")
o_lid.Label  = "Frontscheibe klar (PC)"
o_lid.Shape  = lid
o_lid.ViewObject.ShapeColor   = (0.82, 0.96, 1.00)
o_lid.ViewObject.Transparency = 75

# ── 3. M3-Abstandshalter (Montagebolzen für PCB) ──────────────────────────────
for i, (hx_l, hy_l) in enumerate([HOLE1, HOLE2]):
    bx = PCB_X + hx_l
    by = PCB_Y + hy_l
    boss   = Part.makeCylinder(BOSS_R,  BOSS_H,       V(bx, by, TW),       V(0, 0, 1))
    m3hole = Part.makeCylinder(BOSS_RI, BOSS_H + 0.2, V(bx, by, TW - 0.1), V(0, 0, 1))
    boss_s = boss.cut(m3hole)
    o = doc.addObject("Part::Feature", f"Abstandshalter_{i+1}")
    o.Label = f"Abstandshalter M3 Nr.{i+1}"
    o.Shape = boss_s
    o.ViewObject.ShapeColor = (0.28, 0.28, 0.34)

# ── Ansicht setzen ────────────────────────────────────────────────────────────
doc.recompute()
view = FreeCADGui.ActiveDocument.ActiveView
view.viewIsometric()
view.fitAll()

result = {
    'status':   'ok',
    'objects':  len(doc.Objects),
    'gehaeuse': f'{W}x{L}x{H_BOD+H_LID}mm',
}
"""

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK 2 – Echte Platine importieren (Shapes aus Quelldokument kopieren)
# ═══════════════════════════════════════════════════════════════════════════════
IMPORT_CODE = r"""
global doc, Part, FreeCAD, FreeCADGui
import FreeCAD, Part, FreeCADGui

# Quell-Dokument suchen (enthält Aussen_RGB_PCB, aber ist nicht Gehaeuse_ASB)
src_doc = None
for dn in FreeCAD.listDocuments().keys():
    if dn == "Gehaeuse_ASB":
        continue
    d = FreeCAD.getDocument(dn)
    if any(o.Label == "Aussen_RGB_PCB" for o in d.Objects):
        src_doc = d
        break

if src_doc is None:
    result = {'status': 'error', 'msg': 'PCB-Quelldokument nicht gefunden'}
else:
    dst_doc = FreeCAD.getDocument("Gehaeuse_ASB")

    # Transformation: Welt-KS  →  Gehäuse-Lokal-KS
    # PCB-Linksrand  Welt X=114.30  →  Gehäuse X=2.48   → dx = 2.48 - 114.30
    # PCB-Vorderkante Welt Y=-115.19 → Gehäuse Y=2.50  → dy = 2.50 - (-115.19)
    # PCB-Unterkante  Welt Z=0.00   →  Gehäuse Z=12.00  → dz = 12.00 - 0.00
    dx = 2.48  - 114.30
    dy = 2.50  - (-115.19)
    dz = 12.00 - 0.00

    # Objekte ohne eigene Geometrie überspringen
    SKIP = {
        "Aussen_RGB 1", "Ursprung001", "Ursprung",
        "X-Achse", "Y-Achse", "Z-Achse",
        "XY-Ebene", "XZ-Ebene", "YZ-Ebene",
    }

    imported = []
    for obj in src_doc.Objects:
        if obj.Label in SKIP:
            continue
        try:
            if not hasattr(obj, 'Shape') or obj.Shape.isNull():
                continue
            shape = obj.Shape.copy()
            shape.translate(FreeCAD.Vector(dx, dy, dz))
            new_obj = dst_doc.addObject("Part::Feature", obj.Name + "_pcb")
            new_obj.Label = obj.Label
            new_obj.Shape = shape
            try:
                new_obj.ViewObject.ShapeColor = obj.ViewObject.ShapeColor
            except Exception:
                pass
            imported.append(obj.Label)
        except Exception:
            pass

    dst_doc.recompute()
    view = FreeCADGui.ActiveDocument.ActiveView
    view.viewIsometric()
    view.fitAll()

    result = {'status': 'ok', 'src_doc': src_doc.Name,
              'imported': imported, 'count': len(imported)}
"""

# ── Ausführung ──────────────────────────────────────────────────────────────────
print("[1/2]  Baue Gehäuse + Deckel + Abstandshalter …")
r = conn.execute(BUILD_CODE)
print(f"       Status:   {r.get('status', '?')}")
print(f"       Objekte:  {r.get('objects', '?')}")
print(f"       Außenmaß: {r.get('gehaeuse', '?')}\n")

print("[2/2]  Importiere echte Platine (ASB_AUSSEN_RGB) …")
r2 = conn.execute(IMPORT_CODE)
if r2.get('status') == 'ok':
    print(f"       Quelldokument: {r2.get('src_doc', '?')}")
    print(f"       Importiert:    {r2.get('count', 0)} Objekte")
    for lbl in r2.get('imported', []):
        print(f"         · {lbl}")
else:
    print(f"       FEHLER: {r2.get('msg', r2)}")
print()

# ── Screenshot ─────────────────────────────────────────────────────────────────
print("Erstelle Screenshot …")
scr = conn.call_function(
    "freecad_ai_bridge.view_ops", "get_screenshot",
    width=1280, height=900, view="isometric")

if isinstance(scr, dict) and "image_base64" in scr:
    img_bytes = base64.b64decode(scr["image_base64"])
    out_path  = os.path.join(OUT, "gehaeuse_asb_aussen_rgb.png")
    with open(out_path, "wb") as fh:
        fh.write(img_bytes)
    print(f"  → fem_output/gehaeuse_asb_aussen_rgb.png  ({len(img_bytes)//1024} kB)\n")
else:
    print(f"  Screenshot-Fehler: {scr}\n")

# ── Zusammenfassung ─────────────────────────────────────────────────────────────
print("═" * 62)
print("  Gehäuse ASB_AUSSEN_RGB  –  Fertig")
print("═" * 62)
print("  Außenmaße:        30 × 95 × 24 mm  (Breite × Länge × Höhe)")
print("  Körper:           30 × 95 × 22 mm, oben offen")
print("  Deckel:           30 × 95 × 2 mm, PC klar, 75 % transparent")
print("  Wandstärke:       2 mm")
print("  Eckradius:        3 mm (außen),  1 mm (innen)")
print("  Abstandshalter:   2 × M3, Ø7/3 mm, Höhe 10 mm")
print("  Kabelausgang:     Vorderwand, 22 × 15 mm Schlitz, Z=3–18 mm")
print("  PCB-Position:     X=2.48 / Y=2.5 / Z=12.0 mm")
print("  Stecker-Freiraum: 10 mm unter PCB")
print("  LED → Deckel:     2.7 mm Luft (LED-Oberkante bei Z=19.3 mm)")
print("  LEDs leuchten:    +Z (nach oben durch transparenten Deckel)")
print("═" * 62)
