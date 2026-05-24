#!/usr/bin/env python3
"""Detailed 29er Hardtail Mountain Bike model in FreeCAD via XML-RPC MCP bridge.

Coordinate system: X=right, Y=forward, Z=up.  Ground plane at z=0.
All dimensions in mm.

Components:
  Frame     – down tube, top tube, seat tube, chain stays, seat stays,
               BB shell, head tube
  Fork      – suspension fork (steerer, crown, stanchions, lowers, arch)
  Wheels    – rear + front (tire torus, rim torus, spokes, hub, QR axle)
  Drivetrain– BB spindle, crank arms, pedals, chainring, 12-spd cassette,
               chain (top+bottom run), rear & front derailleur
  Cockpit   – headset spacers, stem, 760mm flat bar, grips, brake levers
  Saddle    – seatpost, saddle loft, saddle rails
  Brakes    – 180/140mm rotors, hydraulic calipers, brake hoses
"""

import os
import sys
import base64

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from freecad_mcp.connection import FreeCADConnection

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fem_output')
os.makedirs(OUT, exist_ok=True)

conn = FreeCADConnection()
conn.connect()
print("Connected to FreeCAD\n")

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK 1 – Document Setup + Frame + Fork
# ═══════════════════════════════════════════════════════════════════════════════
FRAME_CODE = r"""
global doc, Part, FreeCAD, FreeCADGui, math
global BLACK, SILVER, RED, RUBBER, DGRAY
global WR, BB_Z, REAR_Y, FRONT_Y, WZ, BB, REAR_AX, FRONT_AX
global SA, ST_LEN, SEAT_TOP, HEAD_BOT, HEAD_TOP, TT_HEAD, TT_SEAT, HTA, FORK_LEN
global CS_BB_R, CS_BB_L, CS_RR, CS_RL, SS_TOP_R, SS_TOP_L
global tube, cyl_y, cyl_z, cyl_x
import FreeCAD, Part, FreeCADGui, math

for _n in list(FreeCAD.listDocuments().keys()):
    FreeCAD.closeDocument(_n)

doc = FreeCAD.newDocument('MountainBike')

# ── Colours ──────────────────────────────────────────────────────────────────
BLACK  = (0.10, 0.10, 0.10)   # frame tubes
SILVER = (0.70, 0.70, 0.75)   # alloy components
RED    = (0.85, 0.12, 0.12)   # accents (grips, calipers)
RUBBER = (0.13, 0.13, 0.13)   # tires
DGRAY  = (0.30, 0.30, 0.32)   # dark anodised parts
CHAIN  = (0.40, 0.40, 0.42)   # chain / cassette

# ── Geometry constants (29er hardtail trail, size L) ─────────────────────────
#  Wheel radius (tire outer touches ground)
WR      = 368.0
BB_Z    = 340.0    # BB drop geometry: axle 368 – BB 340 = 28 mm drop
REAR_Y  = -430.0   # rear axle Y
FRONT_Y =  680.0   # front axle Y  →  wheelbase = 1110 mm
WZ      = WR       # wheel axle height (axle = outer radius when on flat ground)

BB        = (0.0, 0.0, BB_Z)
REAR_AX   = (0.0, REAR_Y, WZ)
FRONT_AX  = (0.0, FRONT_Y, WZ)

# Seat tube (73°, 445 mm from BB)
SA       = math.radians(73.0)
ST_LEN   = 445.0
SEAT_TOP = (0.0,
            BB[1] - ST_LEN * math.cos(SA),
            BB[2] + ST_LEN * math.sin(SA))
# ≈ (0, -130, 765)

# Head tube (67° head angle, 115 mm long, 100 mm fork travel)
# Crown computed from front axle + fork axis (67°)
FORK_LEN = 515.0   # axle-to-crown (mm)
HTA      = math.radians(67.0)
HEAD_BOT = (0.0,
            FRONT_Y - FORK_LEN * math.cos(HTA),
            WZ       + FORK_LEN * math.sin(HTA))
# ≈ (0, 479, 842)
HT_LEN   = 115.0
HEAD_TOP = (0.0,
            HEAD_BOT[1] - HT_LEN * math.cos(HTA),
            HEAD_BOT[2] + HT_LEN * math.sin(HTA))
# ≈ (0, 434, 948)

# Top tube attach points
TT_HEAD  = (0.0, HEAD_TOP[1] + 5.0, HEAD_TOP[2] - 12.0)
TT_SEAT  = (0.0, SEAT_TOP[1] + 15.0, SEAT_TOP[2] + 2.0)

# Chain-stay attachment near BB
CS_BB_R  = ( 62.0,  6.0, BB_Z - 10.0)
CS_BB_L  = (-62.0,  6.0, BB_Z - 10.0)
CS_RR    = ( 68.0, REAR_Y, WZ)
CS_RL    = (-68.0, REAR_Y, WZ)

# Seat-stay attachment near top of seat tube
SS_TOP_R = ( 16.0, TT_SEAT[1] - 5.0, TT_SEAT[2] - 2.0)
SS_TOP_L = (-16.0, TT_SEAT[1] - 5.0, TT_SEAT[2] - 2.0)

# ── Helpers ───────────────────────────────────────────────────────────────────
def tube(name, p1, p2, r, col=None):
    global doc, FreeCAD
    if col is None:
        col = BLACK
    p1v = FreeCAD.Vector(p1[0], p1[1], p1[2])
    p2v = FreeCAD.Vector(p2[0], p2[1], p2[2])
    d   = p2v - p1v
    L   = d.Length
    if L < 0.5:
        return None
    n  = FreeCAD.Vector(d.x / L, d.y / L, d.z / L)
    zz = FreeCAD.Vector(0.0, 0.0, 1.0)
    dz = n.dot(zz)
    if abs(dz + 1.0) < 1e-6:
        rot = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 180)
    elif abs(dz - 1.0) < 1e-6:
        rot = FreeCAD.Rotation()
    else:
        rot = FreeCAD.Rotation(zz, n)
    o = doc.addObject("Part::Cylinder", name)
    o.Label   = name
    o.Radius  = r
    o.Height  = L
    o.Placement = FreeCAD.Placement(p1v, rot)
    o.ViewObject.ShapeColor = col
    return o


def cyl_y(name, r, h, cx, cy, cz, col=None):
    global doc, FreeCAD
    if col is None:
        col = SILVER
    o = doc.addObject("Part::Cylinder", name)
    o.Label  = name
    o.Radius = r
    o.Height = h
    o.Placement = FreeCAD.Placement(
        FreeCAD.Vector(cx, cy - h / 2.0, cz),
        FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), -90))
    o.ViewObject.ShapeColor = col
    return o


def cyl_z(name, r, h, cx, cy, bot_z, col=None):
    # Cylinder axis=Z, bottom face at bot_z, centred at (cx,cy)
    global doc, FreeCAD
    if col is None:
        col = SILVER
    o = doc.addObject("Part::Cylinder", name)
    o.Label  = name
    o.Radius = r
    o.Height = h
    o.Placement = FreeCAD.Placement(
        FreeCAD.Vector(cx, cy, bot_z),
        FreeCAD.Rotation())
    o.ViewObject.ShapeColor = col
    return o


def cyl_x(name, r, h, cx, cy, cz, col=None):
    # Cylinder axis=X (Ry+90 maps Z->X), centred at (cx,cy,cz)
    global doc, FreeCAD
    if col is None:
        col = SILVER
    o = doc.addObject("Part::Cylinder", name)
    o.Label  = name
    o.Radius = r
    o.Height = h
    o.Placement = FreeCAD.Placement(
        FreeCAD.Vector(cx - h / 2.0, cy, cz),
        FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90))
    o.ViewObject.ShapeColor = col
    return o


# ── MAIN FRAME TUBES ─────────────────────────────────────────────────────────
tube("DownTube",    BB,       HEAD_BOT,  29.0, BLACK)
tube("TopTube",     TT_HEAD,  TT_SEAT,   23.0, BLACK)
tube("SeatTube",    BB,       SEAT_TOP,  27.0, BLACK)
tube("ChainStay_R", CS_BB_R,  CS_RR,     16.0, BLACK)
tube("ChainStay_L", CS_BB_L,  CS_RL,     16.0, BLACK)
tube("SeatStay_R",  CS_RR,    SS_TOP_R,  12.0, BLACK)
tube("SeatStay_L",  CS_RL,    SS_TOP_L,  12.0, BLACK)

# BB shell (X-axis cylinder at BB centre — axle runs left-right)
cyl_x("BB_Shell", 38.0, 73.0, 0.0, 0.0, BB_Z, DGRAY)

# Head tube
tube("HeadTube", HEAD_BOT, HEAD_TOP, 32.0, DGRAY)

# Rear dropout plates (disc in YZ plane — perpendicular to axle)
cyl_x("Dropout_R",  14.0, 14.0,  68.0, REAR_Y, WZ, DGRAY)
cyl_x("Dropout_L",  14.0, 14.0, -68.0, REAR_Y, WZ, DGRAY)

# ── FORK ─────────────────────────────────────────────────────────────────────
# Steerer tube (extends above head tube into stem)
STEER_EXTRA = 75.0
STEER_TOP = (0.0,
             HEAD_TOP[1] - STEER_EXTRA * math.cos(HTA),
             HEAD_TOP[2] + STEER_EXTRA * math.sin(HTA))
tube("Steerer", HEAD_TOP, STEER_TOP, 19.0, DGRAY)

# Fork crown (solid block at the base of the head tube)
FC_Y = HEAD_BOT[1]
FC_Z = HEAD_BOT[2] - 22.0
cyl_x("ForkCrown", 44.0, 92.0, 0.0, FC_Y, FC_Z, DGRAY)

# Fork stanchions (polished upper sliders) – from crown toward mid-point
MID_Y = FRONT_Y - 45.0
MID_Z = WZ + 225.0
tube("Fork_Stanch_R",  ( 36.0, FC_Y, FC_Z - 10.0), ( 41.0, MID_Y, MID_Z), 21.0, SILVER)
tube("Fork_Stanch_L",  (-36.0, FC_Y, FC_Z - 10.0), (-41.0, MID_Y, MID_Z), 21.0, SILVER)

# Fork lowers (fat anodised lower section)
tube("Fork_Lower_R",   ( 41.0, MID_Y, MID_Z), ( 45.0, FRONT_Y, WZ + 8.0), 28.0, DGRAY)
tube("Fork_Lower_L",   (-41.0, MID_Y, MID_Z), (-45.0, FRONT_Y, WZ + 8.0), 28.0, DGRAY)

# Lower brace arch
tube("Fork_Arch",
     (-44.0, FRONT_Y - 85.0, WZ + 118.0),
     ( 44.0, FRONT_Y - 85.0, WZ + 118.0), 11.0, DGRAY)

doc.recompute()
result = {'objects': len(doc.Objects), 'status': 'frame_ok',
          'wheelbase_mm': FRONT_Y - REAR_Y,
          'head_bot': list(HEAD_BOT), 'head_top': list(HEAD_TOP)}
"""

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK 2 – Wheels (rear + front): tire, rim, spokes, hub, QR axle
# ═══════════════════════════════════════════════════════════════════════════════
WHEEL_CODE = r"""
global doc, Part, FreeCAD, FreeCADGui, math
global BLACK, SILVER, RUBBER, DGRAY
global WR, REAR_Y, FRONT_Y, WZ
global TORUS_R, TORUS_r, RIM_R, RIM_r, HUB_R, SPOKE_R, HUB_FR
global tube, cyl_x, make_wheel
import FreeCAD, Part, FreeCADGui, math
doc = FreeCAD.ActiveDocument

BLACK  = (0.10, 0.10, 0.10)
SILVER = (0.70, 0.70, 0.75)
RUBBER = (0.13, 0.13, 0.13)
DGRAY  = (0.30, 0.30, 0.32)

WR      = 368.0
REAR_Y  = -430.0
FRONT_Y =  680.0
WZ      = WR

# Tyre torus:  major R + minor r  =  WR  (outer edge touches ground)
TORUS_R =  323.0   # major (centre of tube cross-section from wheel centre)
TORUS_r  =  45.0   # minor (tube radius) → outer = 368, inner = 278
# Rim torus (rim hook bed ≈ ISO 622 bead, simplified)
RIM_R   =  295.0
RIM_r   =   13.0
# Hub geometry
HUB_R   =   22.0
SPOKE_R =  282.0   # rim spoke-hole radius
HUB_FR  =   12.0   # hub flange radius

def tube(name, p1, p2, r, col=None):
    global doc, FreeCAD
    if col is None: col = SILVER
    p1v = FreeCAD.Vector(p1[0], p1[1], p1[2])
    p2v = FreeCAD.Vector(p2[0], p2[1], p2[2])
    d = p2v - p1v; L = d.Length
    if L < 0.5: return None
    n = FreeCAD.Vector(d.x/L, d.y/L, d.z/L)
    z = FreeCAD.Vector(0,0,1); dz = n.dot(z)
    if abs(dz + 1.0) < 1e-6:
        rot = FreeCAD.Rotation(FreeCAD.Vector(1,0,0), 180)
    elif abs(dz - 1.0) < 1e-6:
        rot = FreeCAD.Rotation()
    else:
        rot = FreeCAD.Rotation(z, n)
    o = doc.addObject("Part::Cylinder", name)
    o.Label = name; o.Radius = r; o.Height = L
    o.Placement = FreeCAD.Placement(p1v, rot)
    o.ViewObject.ShapeColor = col
    return o


def cyl_x(name, r, h, cx, cy, cz, col=None):
    global doc, FreeCAD
    if col is None: col = SILVER
    o = doc.addObject("Part::Cylinder", name)
    o.Label = name; o.Radius = r; o.Height = h
    o.Placement = FreeCAD.Placement(
        FreeCAD.Vector(cx - h/2.0, cy, cz),
        FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90))
    o.ViewObject.ShapeColor = col
    return o


def make_wheel(prefix, axle_y, hub_half=38.0, n_spokes=16):
    global doc, Part, FreeCAD, math
    # Ry(+90°): Z→X  → torus axis=X, wheel plane=YZ (visible as circle from side)
    rot_X = FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90)

    # Tyre
    ts = Part.makeTorus(TORUS_R, TORUS_r)
    t  = doc.addObject("Part::Feature", prefix + "_Tyre")
    t.Label   = prefix + "_Tyre"
    t.Shape   = ts
    t.Placement = FreeCAD.Placement(FreeCAD.Vector(0, axle_y, WZ), rot_X)
    t.ViewObject.ShapeColor = RUBBER

    # Rim
    rs = Part.makeTorus(RIM_R, RIM_r)
    ri = doc.addObject("Part::Feature", prefix + "_Rim")
    ri.Label   = prefix + "_Rim"
    ri.Shape   = rs
    ri.Placement = FreeCAD.Placement(FreeCAD.Vector(0, axle_y, WZ), rot_X)
    ri.ViewObject.ShapeColor = SILVER

    # Rim sidewalls
    rsi = Part.makeTorus(RIM_R - 8.0, 6.0)
    rw  = doc.addObject("Part::Feature", prefix + "_RimWall")
    rw.Label = prefix + "_RimWall"; rw.Shape = rsi
    rw.Placement = FreeCAD.Placement(FreeCAD.Vector(0, axle_y, WZ), rot_X)
    rw.ViewObject.ShapeColor = SILVER

    # Hub barrel (along X — the actual axle direction)
    cyl_x(prefix + "_Hub", HUB_R, hub_half * 2.0, 0.0, axle_y, WZ, DGRAY)

    # Hub flanges (at ±fl_x in X direction)
    fl_x = hub_half * 0.72
    cyl_x(prefix + "_Flange_R", HUB_FR + 7.0, 7.0,  fl_x, axle_y, WZ, SILVER)
    cyl_x(prefix + "_Flange_L", HUB_FR + 7.0, 7.0, -fl_x, axle_y, WZ, SILVER)

    # Spokes — rim attachment in YZ plane, hub at X=±fl_x
    offset_ang = math.radians(12.0)
    for i in range(n_spokes):
        ang = i * (360.0 / n_spokes)
        a   = math.radians(ang)
        # Rim point (in YZ plane at x=0)
        ry = axle_y + SPOKE_R * math.sin(a)
        rz = WZ     + SPOKE_R * math.cos(a)
        # Hub flange point (at x=±fl_x, slight cross-lacing)
        side_x = fl_x if (i % 2 == 0) else -fl_x
        ha = a + offset_ang * (1 if i % 2 == 0 else -1)
        hy = axle_y + HUB_FR * math.sin(ha)
        hz = WZ     + HUB_FR * math.cos(ha)
        tube(f"{prefix}_Sp{i}",
             (0.0,    ry, rz),
             (side_x, hy, hz),
             1.8, SILVER)

    # Quick-release axle (along X)
    cyl_x(prefix + "_QR", 6.5, hub_half * 2.0 + 32.0, 0.0, axle_y, WZ, SILVER)

    # Valve stem (at rim top, pointing upward)
    tube(f"{prefix}_Valve",
         (0.0, axle_y - 4.0, WZ + RIM_R - 5.0),
         (0.0, axle_y - 4.0, WZ + RIM_R + 32.0),
         3.2, (0.55, 0.55, 0.58))


# Rear wheel (135 mm OLD → hub_half = 40)
make_wheel("Rear",  REAR_Y,  hub_half=40.0, n_spokes=16)
# Front wheel (100 mm OLD → hub_half = 26)
make_wheel("Front", FRONT_Y, hub_half=26.0, n_spokes=16)

doc.recompute()
result = {'status': 'wheels_ok', 'objects': len(doc.Objects)}
"""

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK 3 – Drivetrain
# ═══════════════════════════════════════════════════════════════════════════════
DRIVETRAIN_CODE = r"""
global doc, Part, FreeCAD, FreeCADGui, math
global BLACK, SILVER, RED, DGRAY, CHAIN
global BB_Z, REAR_Y, WZ, CR_X, CR_R
global tube, cyl_x, cyl_z, torus_disc
import FreeCAD, Part, FreeCADGui, math
doc = FreeCAD.ActiveDocument

BLACK  = (0.10, 0.10, 0.10)
SILVER = (0.70, 0.70, 0.75)
RED    = (0.85, 0.12, 0.12)
DGRAY  = (0.30, 0.30, 0.32)
CHAIN  = (0.40, 0.40, 0.42)

BB_Z   = 340.0
REAR_Y = -430.0
WZ     = 368.0

def tube(name, p1, p2, r, col=None):
    global doc, FreeCAD
    if col is None: col = SILVER
    p1v = FreeCAD.Vector(p1[0], p1[1], p1[2])
    p2v = FreeCAD.Vector(p2[0], p2[1], p2[2])
    d = p2v - p1v; L = d.Length
    if L < 0.5: return None
    n = FreeCAD.Vector(d.x/L, d.y/L, d.z/L)
    z = FreeCAD.Vector(0,0,1); dz = n.dot(z)
    if abs(dz + 1.0) < 1e-6:
        rot = FreeCAD.Rotation(FreeCAD.Vector(1,0,0), 180)
    elif abs(dz - 1.0) < 1e-6:
        rot = FreeCAD.Rotation()
    else:
        rot = FreeCAD.Rotation(z, n)
    o = doc.addObject("Part::Cylinder", name)
    o.Label = name; o.Radius = r; o.Height = L
    o.Placement = FreeCAD.Placement(p1v, rot)
    o.ViewObject.ShapeColor = col
    return o


def cyl_x(name, r, h, cx, cy, cz, col=None):
    global doc, FreeCAD
    if col is None: col = SILVER
    o = doc.addObject("Part::Cylinder", name)
    o.Label = name; o.Radius = r; o.Height = h
    o.Placement = FreeCAD.Placement(
        FreeCAD.Vector(cx - h/2.0, cy, cz),
        FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90))
    o.ViewObject.ShapeColor = col
    return o


def cyl_z(name, r, h, cx, cy, bot_z, col=None):
    global doc, FreeCAD
    if col is None: col = SILVER
    o = doc.addObject("Part::Cylinder", name)
    o.Label = name; o.Radius = r; o.Height = h
    o.Placement = FreeCAD.Placement(
        FreeCAD.Vector(cx, cy, bot_z),
        FreeCAD.Rotation())
    o.ViewObject.ShapeColor = col
    return o


def torus_disc(name, R, r, cx, cy, cz, col=None):
    global doc, Part, FreeCAD
    if col is None: col = SILVER
    s = Part.makeTorus(R, r)
    o = doc.addObject("Part::Feature", name)
    o.Label = name; o.Shape = s
    # Ry+90: torus axis=X, ring in YZ plane
    o.Placement = FreeCAD.Placement(
        FreeCAD.Vector(cx, cy, cz),
        FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90))
    o.ViewObject.ShapeColor = col
    return o


# ── BB Spindle (along X – axle direction) ─────────────────────────────────────
cyl_x("BB_Spindle", 10.5, 120.0, 0.0, 0.0, BB_Z, SILVER)

# ── Crank Arms ────────────────────────────────────────────────────────────────
CRANK_LEN = 175.0
CRANK_ANG = math.radians(42.0)   # angle from straight-down (arm forward)

# Right crank (at BB right face Y=+58)
CR_S = (58.0,  0.0, BB_Z)
CR_E = (58.0,
        CRANK_LEN * math.sin(CRANK_ANG),
        BB_Z - CRANK_LEN * math.cos(CRANK_ANG))
tube("Crank_R", CR_S, CR_E, 11.0, BLACK)

# Left crank (opposite phase)
CL_S = (-58.0, 0.0, BB_Z)
CL_E = (-58.0,
        -CRANK_LEN * math.sin(CRANK_ANG),
        BB_Z + CRANK_LEN * math.cos(CRANK_ANG))
tube("Crank_L", CL_S, CL_E, 11.0, BLACK)

# Crank arm reinforcing ribs (slightly thinner overtube)
tube("Crank_R_Rib", CR_S, CR_E, 6.5, DGRAY)
tube("Crank_L_Rib", CL_S, CL_E, 6.5, DGRAY)

# ── Pedals ────────────────────────────────────────────────────────────────────
PD_R = (CR_E[0], CR_E[1], CR_E[2])
PD_L = (CL_E[0], CL_E[1], CL_E[2])
# Pedal body (along X, extending outward from crank end)
cyl_x("Pedal_R_Body",  14.0, 100.0, PD_R[0] + 50.0, PD_R[1], PD_R[2], BLACK)
cyl_x("Pedal_R_Axle",   7.0, 115.0, PD_R[0] + 57.5, PD_R[1], PD_R[2], SILVER)
cyl_x("Pedal_L_Body",  14.0, 100.0, PD_L[0] - 50.0, PD_L[1], PD_L[2], BLACK)
cyl_x("Pedal_L_Axle",   7.0, 115.0, PD_L[0] - 57.5, PD_L[1], PD_L[2], SILVER)

# ── Chainring (32T, radius ≈ 92 mm) ──────────────────────────────────────────
CR_R   = 92.0
CR_X   = 52.0   # X offset: chainring on right side of BB (X direction = lateral)
# Outer ring (torus in YZ plane at x=CR_X)
torus_disc("Chainring_Outer",  CR_R, 5.5, CR_X, 0.0, BB_Z, SILVER)
# Inner spider ring
torus_disc("Chainring_Spider", 55.0, 4.0, CR_X, 0.0, BB_Z, BLACK)
# Centre boss
cyl_x("Chainring_Boss", 18.0, 20.0, CR_X, 0.0, BB_Z, BLACK)

# ── 12-speed Cassette (rear) ──────────────────────────────────────────────────
# 10T … 51T; radii proportional to tooth count × 4.8 mm half-pitch
cog_data = [
    (13.0, 3.0), (15.0, 3.0), (17.0, 3.0), (20.0, 3.0),
    (23.0, 3.0), (26.0, 3.5), (30.0, 3.5), (35.0, 3.5),
    (40.0, 4.0), (45.0, 4.0), (50.0, 4.0), (56.0, 4.5),
]
# Cassette cogs stacked along X (outward = large x = right dropout side)
cas_x = 68.0   # outermost cog (smallest, at right dropout)
for idx, (cog_r, cog_t) in enumerate(cog_data):
    torus_disc(f"Cog_{idx+1}", cog_r, 2.2,
               cas_x, REAR_Y, WZ, SILVER)
    cas_x -= cog_t + 1.5

# Cassette body (lockring area, along X)
cyl_x("Cassette_Body", 16.0, 6.0, 68.0, REAR_Y, WZ, DGRAY)

# ── Chain (top and bottom run) ────────────────────────────────────────────────
# Bottom run: chainring lower tangent → cassette smallest cog bottom
CH_BOT_SZ = BB_Z - CR_R + 5.0
CH_BOT_EZ = WZ  - 13.0 + 5.0
tube("Chain_Bottom",
     (CR_X, 0.0,    CH_BOT_SZ),
     (68.0, REAR_Y, CH_BOT_EZ), 4.8, CHAIN)

# Top run: chainring upper tangent → cassette
CH_TOP_SZ = BB_Z + CR_R - 5.0
CH_TOP_EZ = WZ  + 13.0 - 5.0
tube("Chain_Top",
     (CR_X, 0.0,    CH_TOP_SZ),
     (68.0, REAR_Y, CH_TOP_EZ), 4.8, CHAIN)

# ── Rear Derailleur ───────────────────────────────────────────────────────────
RD_X = 76.0; RD_Y = REAR_Y - 18.0; RD_Z = WZ - 48.0
# Upper pivot arm
tube("RDer_Arm",    (68.0, REAR_Y, WZ - 8.0), (RD_X, RD_Y, RD_Z),       7.5, DGRAY)
# Cage
tube("RDer_Cage",   (RD_X, RD_Y, RD_Z),       (RD_X, RD_Y, RD_Z - 58.0), 5.0, DGRAY)
# B-link
tube("RDer_Blink",  (68.0, REAR_Y, WZ - 8.0), (RD_X, RD_Y + 18.0, RD_Z + 22.0), 8.5, DGRAY)
# Upper pulley (along X)
cyl_x("RDer_PulleyU", 12.5, 11.0, RD_X, RD_Y, RD_Z,        BLACK)
# Lower pulley
cyl_x("RDer_PulleyL", 12.5, 11.0, RD_X, RD_Y, RD_Z - 58.0, BLACK)
# Chain through upper pulley
tube("Chain_RDer_top",
     (RD_X, RD_Y, RD_Z),
     (68.0, REAR_Y - 5.0, WZ + 13.0 - 5.0), 4.5, CHAIN)

# ── Front Derailleur ──────────────────────────────────────────────────────────
FD_Z = BB_Z + 195.0
cyl_z("FDer_Clamp", 30.0, 12.0, 0.0, 0.0, FD_Z, DGRAY)
tube("FDer_Outer",
     (0.0, -6.0, FD_Z - 12.0), (CR_X + 5.0, 12.0, BB_Z + 90.0), 5.0, DGRAY)
tube("FDer_Inner",
     (0.0, -4.0, FD_Z - 12.0), (CR_X - 8.0, 10.0, BB_Z + 85.0), 4.0, DGRAY)

doc.recompute()
result = {'status': 'drivetrain_ok', 'objects': len(doc.Objects)}
"""

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK 4 – Cockpit: Stem, Handlebar, Grips, Brake Levers
# ═══════════════════════════════════════════════════════════════════════════════
COCKPIT_CODE = r"""
global doc, Part, FreeCAD, FreeCADGui, math
global BLACK, SILVER, RED, DGRAY, RUBBER
global BB_Z, REAR_Y, FRONT_Y, WZ, FORK_LEN, HTA, SA, ST_LEN, SEAT_TOP, HEAD_BOT, HEAD_TOP
global tube, cyl_y, cyl_z, cyl_x
import FreeCAD, Part, FreeCADGui, math
doc = FreeCAD.ActiveDocument

BLACK  = (0.10, 0.10, 0.10)
SILVER = (0.70, 0.70, 0.75)
RED    = (0.85, 0.12, 0.12)
DGRAY  = (0.30, 0.30, 0.32)

BB_Z    = 340.0
REAR_Y  = -430.0
FRONT_Y =  680.0
WZ      = 368.0
FORK_LEN= 515.0
HTA     = math.radians(67.0)

HEAD_BOT = (0.0, FRONT_Y - FORK_LEN*math.cos(HTA), WZ + FORK_LEN*math.sin(HTA))
HEAD_TOP = (0.0, HEAD_BOT[1] - 115.0*math.cos(HTA), HEAD_BOT[2] + 115.0*math.sin(HTA))

SA     = math.radians(73.0)
ST_LEN = 445.0
SEAT_TOP = (0.0,
            -ST_LEN * math.cos(SA),
            BB_Z + ST_LEN * math.sin(SA))

def tube(name, p1, p2, r, col=None):
    global doc, FreeCAD
    if col is None: col = BLACK
    p1v = FreeCAD.Vector(p1[0], p1[1], p1[2])
    p2v = FreeCAD.Vector(p2[0], p2[1], p2[2])
    d = p2v - p1v; L = d.Length
    if L < 0.5: return None
    n = FreeCAD.Vector(d.x/L, d.y/L, d.z/L)
    z = FreeCAD.Vector(0,0,1); dz = n.dot(z)
    if abs(dz + 1.0) < 1e-6:
        rot = FreeCAD.Rotation(FreeCAD.Vector(1,0,0), 180)
    elif abs(dz - 1.0) < 1e-6:
        rot = FreeCAD.Rotation()
    else:
        rot = FreeCAD.Rotation(z, n)
    o = doc.addObject("Part::Cylinder", name)
    o.Label = name; o.Radius = r; o.Height = L
    o.Placement = FreeCAD.Placement(p1v, rot)
    o.ViewObject.ShapeColor = col
    return o


def cyl_y(name, r, h, cx, cy, cz, col=None):
    global doc, FreeCAD
    if col is None: col = SILVER
    o = doc.addObject("Part::Cylinder", name)
    o.Label = name; o.Radius = r; o.Height = h
    o.Placement = FreeCAD.Placement(
        FreeCAD.Vector(cx, cy - h/2.0, cz),
        FreeCAD.Rotation(FreeCAD.Vector(1,0,0), -90))
    o.ViewObject.ShapeColor = col
    return o


def cyl_z(name, r, h, cx, cy, bot_z, col=None):
    global doc, FreeCAD
    if col is None: col = SILVER
    o = doc.addObject("Part::Cylinder", name)
    o.Label = name; o.Radius = r; o.Height = h
    o.Placement = FreeCAD.Placement(
        FreeCAD.Vector(cx, cy, bot_z),
        FreeCAD.Rotation())
    o.ViewObject.ShapeColor = col
    return o


def cyl_x(name, r, h, cx, cy, cz, col=None):
    global doc, FreeCAD
    if col is None: col = SILVER
    o = doc.addObject("Part::Cylinder", name)
    o.Label = name; o.Radius = r; o.Height = h
    o.Placement = FreeCAD.Placement(
        FreeCAD.Vector(cx - h/2.0, cy, cz),
        FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90))
    o.ViewObject.ShapeColor = col
    return o


# ── Seatpost ──────────────────────────────────────────────────────────────────
SP_BOT = SEAT_TOP
SP_TOP = (0.0, SP_BOT[1], SP_BOT[2] + 185.0)
tube("Seatpost", SP_BOT, SP_TOP, 18.5, SILVER)
cyl_z("SP_Clamp", 25.0, 15.0, 0.0, SP_BOT[1], SP_BOT[2] - 8.0, DGRAY)

# ── Saddle ────────────────────────────────────────────────────────────────────
SAD_Y  = SP_TOP[1] - 15.0   # slightly rearward
SAD_Z  = SP_TOP[2] + 9.0    # slightly above seatpost top

# Saddle rails (two parallel alloy rails)
for dx in (-22.0, 22.0):
    s = "R" if dx > 0 else "L"
    tube(f"Saddle_Rail_{s}",
         (dx, SAD_Y + 125.0, SAD_Z - 6.0),
         (dx, SAD_Y - 135.0, SAD_Z - 6.0),
         3.5, SILVER)

# Saddle shell via loft of circles (nose → wide → tail)
sad_profiles = [
    (130.0, 16.0),   # nose
    ( 65.0, 54.0),
    (  0.0, 70.0),   # widest
    (-65.0, 62.0),
    (-130.0, 50.0),  # tail
]
sad_wires = []
for (dy, r) in sad_profiles:
    ctr = FreeCAD.Vector(0.0, SAD_Y + dy, SAD_Z)
    nrm = FreeCAD.Vector(0.0, 1.0, 0.0)
    edge = Part.makeCircle(r, ctr, nrm)
    sad_wires.append(Part.Wire(edge))

sad_shape = Part.makeLoft(sad_wires, True, False, False)
sad_obj   = doc.addObject("Part::Feature", "Saddle")
sad_obj.Label   = "Saddle"
sad_obj.Shape   = sad_shape
sad_obj.ViewObject.ShapeColor = (0.12, 0.12, 0.12)

# Saddle nose bump
cyl_z("Saddle_Nose", 14.0, 10.0, 0.0, SAD_Y + 128.0, SAD_Z - 2.0, (0.18, 0.18, 0.18))

# ── Headset Spacers ───────────────────────────────────────────────────────────
# Stack on the steerer above HEAD_TOP
SPC_Y = HEAD_TOP[1]
SPC_Z = HEAD_TOP[2]
for si in range(3):
    cyl_z(f"Spacer_{si}", 23.0, 10.0, 0.0, SPC_Y, SPC_Z + si * 12.0, DGRAY)

# Stem steerer clamp (at top of spacer stack)
STEM_BASE_Z = SPC_Z + 36.0
STEM_BASE_Y = SPC_Y
cyl_z("Stem_ClampSteerer", 23.5, 40.0, 0.0, STEM_BASE_Y, STEM_BASE_Z, DGRAY)

# Stem body (70 mm, 6° rise)
STEM_LEN = 70.0
STEM_RISE = math.radians(6.0)
STEM_END_Y = STEM_BASE_Y + STEM_LEN * math.cos(STEM_RISE)
STEM_END_Z = STEM_BASE_Z + 20.0 + STEM_LEN * math.sin(STEM_RISE)
tube("Stem", (0.0, STEM_BASE_Y, STEM_BASE_Z + 20.0),
             (0.0, STEM_END_Y,  STEM_END_Z), 15.0, DGRAY)

# Stem faceplate (handlebar clamp)
HB_Y  = STEM_END_Y + 6.0
HB_Z  = STEM_END_Z
cyl_z("Stem_Faceplate", 19.0, 13.0, 0.0, HB_Y, HB_Z - 9.5, BLACK)

# ── Handlebar (760 mm wide flat bar, 8° backsweep, 5° upsweep) ───────────────
HB_HALF = 380.0
BSW = math.radians(8.0)
USW = math.radians(5.0)

HB_END_R = ( HB_HALF * math.cos(BSW),
             HB_Y - HB_HALF * math.sin(BSW),
             HB_Z + HB_HALF * math.sin(USW))
HB_END_L = (-HB_HALF * math.cos(BSW),
             HB_Y - HB_HALF * math.sin(BSW),
             HB_Z + HB_HALF * math.sin(USW))

tube("HBar_R", (0.0, HB_Y, HB_Z), HB_END_R, 11.0, BLACK)
tube("HBar_L", (0.0, HB_Y, HB_Z), HB_END_L, 11.0, BLACK)

# Handlebar centre reinforcement (31.8 mm diameter clamp zone, ±40 mm)
CLAMP_W = 40.0
cyl_x("HBar_Clamp_R", 12.5, CLAMP_W,  CLAMP_W/2, HB_Y, HB_Z, BLACK)
cyl_x("HBar_Clamp_L", 12.5, CLAMP_W, -CLAMP_W/2, HB_Y, HB_Z, BLACK)

# Grips (130 mm long, inboard of bar ends)
GRIP_LEN = 130.0
GP_IN_R  = HB_END_R  # grip starts at bar-end side
GP_OUT_R = (HB_END_R[0] - GRIP_LEN * math.cos(BSW),
             HB_END_R[1] + GRIP_LEN * math.sin(BSW),
             HB_END_R[2])
GP_IN_L  = HB_END_L
GP_OUT_L = (-HB_END_R[0] + GRIP_LEN * math.cos(BSW),
             HB_END_L[1] + GRIP_LEN * math.sin(BSW),
             HB_END_L[2])

tube("Grip_R", GP_IN_R, GP_OUT_R, 17.0, RED)
tube("Grip_L", GP_IN_L, GP_OUT_L, 17.0, RED)

# Bar-end plugs
tube("BarEnd_R", HB_END_R, (HB_END_R[0]+12, HB_END_R[1], HB_END_R[2]), 11.0, DGRAY)
tube("BarEnd_L", HB_END_L, (HB_END_L[0]-12, HB_END_L[1], HB_END_L[2]), 11.0, DGRAY)

# ── Brake Lever Bodies ────────────────────────────────────────────────────────
BL_CLAMP_R = (GP_OUT_R[0] + 40.0, GP_OUT_R[1] - 30.0, GP_OUT_R[2])
BL_CLAMP_L = (GP_OUT_L[0] - 40.0, GP_OUT_L[1] - 30.0, GP_OUT_L[2])

tube("BLever_Body_R", HB_END_R, BL_CLAMP_R, 13.0, DGRAY)
tube("BLever_Body_L", HB_END_L, BL_CLAMP_L, 13.0, DGRAY)

# Lever blades (angled downward)
BL_TIP_R = (BL_CLAMP_R[0] - 5.0, BL_CLAMP_R[1] - 80.0, BL_CLAMP_R[2] - 25.0)
BL_TIP_L = (BL_CLAMP_L[0] + 5.0, BL_CLAMP_L[1] - 80.0, BL_CLAMP_L[2] - 25.0)
tube("BLever_Blade_R", BL_CLAMP_R, BL_TIP_R, 5.0, BLACK)
tube("BLever_Blade_L", BL_CLAMP_L, BL_TIP_L, 5.0, BLACK)

doc.recompute()
result = {
    'status': 'cockpit_ok',
    'objects': len(doc.Objects),
    'bar_width_mm': HB_HALF * 2,
    'bar_height_mm': round(HB_Z, 1),
    'saddle_height_mm': round(SAD_Z, 1),
}
"""

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK 5 – Brakes: rotors, calipers, hoses
# ═══════════════════════════════════════════════════════════════════════════════
BRAKE_CODE = r"""
global doc, Part, FreeCAD, FreeCADGui, math
global SILVER, RED, DGRAY, BLACK
global REAR_Y, FRONT_Y, WZ, BB_Z, FORK_LEN, HTA
global tube, cyl_x, torus_disc
import FreeCAD, Part, FreeCADGui, math
doc = FreeCAD.ActiveDocument

SILVER = (0.70, 0.70, 0.75)
RED    = (0.85, 0.12, 0.12)
DGRAY  = (0.30, 0.30, 0.32)
BLACK  = (0.10, 0.10, 0.10)

REAR_Y  = -430.0
FRONT_Y =  680.0
WZ      = 368.0
BB_Z    = 340.0

# Ry+90: axis=X, ring in YZ plane (correct wheel/rotor orientation)
rot_X = FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90)

def tube(name, p1, p2, r, col=None):
    global doc, FreeCAD
    if col is None: col = DGRAY
    p1v = FreeCAD.Vector(p1[0], p1[1], p1[2])
    p2v = FreeCAD.Vector(p2[0], p2[1], p2[2])
    d = p2v - p1v; L = d.Length
    if L < 0.5: return None
    n = FreeCAD.Vector(d.x/L, d.y/L, d.z/L)
    z = FreeCAD.Vector(0,0,1); dz = n.dot(z)
    if abs(dz + 1.0) < 1e-6:
        rot = FreeCAD.Rotation(FreeCAD.Vector(1,0,0), 180)
    elif abs(dz - 1.0) < 1e-6:
        rot = FreeCAD.Rotation()
    else:
        rot = FreeCAD.Rotation(z, n)
    o = doc.addObject("Part::Cylinder", name)
    o.Label = name; o.Radius = r; o.Height = L
    o.Placement = FreeCAD.Placement(p1v, rot)
    o.ViewObject.ShapeColor = col
    return o


def cyl_x(name, r, h, cx, cy, cz, col=None):
    global doc, FreeCAD
    if col is None: col = SILVER
    o = doc.addObject("Part::Cylinder", name)
    o.Label = name; o.Radius = r; o.Height = h
    o.Placement = FreeCAD.Placement(
        FreeCAD.Vector(cx - h/2.0, cy, cz),
        FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90))
    o.ViewObject.ShapeColor = col
    return o


def torus_disc(name, R, r, cx, cy, cz, col=None):
    global doc, Part, FreeCAD
    if col is None: col = SILVER
    s = Part.makeTorus(R, r)
    o = doc.addObject("Part::Feature", name)
    o.Label = name; o.Shape = s
    # Ry+90: torus axis=X, ring in YZ plane (correct for braking rotors)
    o.Placement = FreeCAD.Placement(
        FreeCAD.Vector(cx, cy, cz),
        FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90))
    o.ViewObject.ShapeColor = col
    return o


# ── Brake Rotors ───────────────────────────────────────────────────────────────
# Front 180 mm rotor (mounted on left hub face)
torus_disc("Rotor_Front_Outer", 175.0, 8.0, -38.0, FRONT_Y, WZ, SILVER)
torus_disc("Rotor_Front_Mid",   120.0, 6.0, -38.0, FRONT_Y, WZ, SILVER)
torus_disc("Rotor_Front_Spider", 60.0, 4.5, -38.0, FRONT_Y, WZ, (0.60, 0.60, 0.65))

# Rear 140 mm rotor
torus_disc("Rotor_Rear_Outer", 135.0, 8.0, -62.0, REAR_Y, WZ, SILVER)
torus_disc("Rotor_Rear_Mid",    90.0, 6.0, -62.0, REAR_Y, WZ, SILVER)
torus_disc("Rotor_Rear_Spider", 48.0, 4.5, -62.0, REAR_Y, WZ, (0.60, 0.60, 0.65))

# ── Brake Calipers ────────────────────────────────────────────────────────────
# Front caliper (clamped to fork lower — body straddles rotor disc in X direction)
CAL_F_X = -40.0; CAL_F_Y = FRONT_Y - 30.0; CAL_F_Z = WZ + 160.0
cyl_x("Caliper_Front",       22.0, 42.0, CAL_F_X, CAL_F_Y, CAL_F_Z, RED)
tube("Caliper_Front_Mnt1",
     (CAL_F_X, CAL_F_Y, CAL_F_Z + 22.0),
     (-44.0, FRONT_Y - 20.0, WZ + 195.0), 5.0, DGRAY)
tube("Caliper_Front_Mnt2",
     (CAL_F_X, CAL_F_Y, CAL_F_Z - 22.0),
     (-44.0, FRONT_Y - 20.0, WZ + 125.0), 5.0, DGRAY)

# Rear caliper (on chainstay bridge, left side)
CAL_R_X = -65.0; CAL_R_Y = REAR_Y + 30.0; CAL_R_Z = WZ + 55.0
cyl_x("Caliper_Rear",        20.0, 38.0, CAL_R_X, CAL_R_Y, CAL_R_Z, RED)
tube("Caliper_Rear_Mnt1",
     (CAL_R_X, CAL_R_Y, CAL_R_Z + 19.0),
     (-68.0, REAR_Y + 20.0, WZ + 82.0), 5.0, DGRAY)
tube("Caliper_Rear_Mnt2",
     (CAL_R_X, CAL_R_Y, CAL_R_Z - 19.0),
     (-68.0, REAR_Y + 20.0, WZ + 28.0), 5.0, DGRAY)

# ── Brake Hoses ───────────────────────────────────────────────────────────────
# Handlebar lever positions (approximate, mirrored from cockpit block)
FORK_LEN = 515.0; HTA = math.radians(67.0)
HEAD_BOT = (0.0, FRONT_Y - FORK_LEN*math.cos(HTA), WZ + FORK_LEN*math.sin(HTA))
HEAD_TOP = (0.0, HEAD_BOT[1] - 115.0*math.cos(HTA), HEAD_BOT[2] + 115.0*math.sin(HTA))
STEM_BASE_Z = HEAD_TOP[2] + 36.0
STEM_BASE_Y = HEAD_TOP[1]
STEM_END_Y  = STEM_BASE_Y + 70.0 * math.cos(math.radians(6.0))
STEM_END_Z  = STEM_BASE_Z + 20.0 + 70.0 * math.sin(math.radians(6.0))
HB_Y  = STEM_END_Y + 6.0; HB_Z  = STEM_END_Z
HB_HALF = 380.0; BSW = math.radians(8.0); USW = math.radians(5.0)
HB_END_R = ( HB_HALF*math.cos(BSW), HB_Y - HB_HALF*math.sin(BSW), HB_Z + HB_HALF*math.sin(USW))
HB_END_L = (-HB_HALF*math.cos(BSW), HB_Y - HB_HALF*math.sin(BSW), HB_Z + HB_HALF*math.sin(USW))
GRIP_LEN = 130.0
GP_OUT_R = (HB_END_R[0] - GRIP_LEN*math.cos(BSW), HB_END_R[1] + GRIP_LEN*math.sin(BSW), HB_END_R[2])
GP_OUT_L = (-HB_END_R[0] + GRIP_LEN*math.cos(BSW), HB_END_L[1] + GRIP_LEN*math.sin(BSW), HB_END_L[2])
BL_R = (GP_OUT_R[0] + 40.0, GP_OUT_R[1] - 30.0, GP_OUT_R[2])
BL_L = (GP_OUT_L[0] - 40.0, GP_OUT_L[1] - 30.0, GP_OUT_L[2])

# Front hose (right lever → left fork/caliper)
tube("Hose_Front", BL_R, (CAL_F_X, CAL_F_Y, CAL_F_Z), 3.0, BLACK)
# Rear hose (left lever → rear caliper)
tube("Hose_Rear",  BL_L, (CAL_R_X, CAL_R_Y, CAL_R_Z), 3.0, BLACK)

doc.recompute()
result = {'status': 'brakes_ok', 'objects': len(doc.Objects)}
"""

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK 6 – Finalize view
# ═══════════════════════════════════════════════════════════════════════════════
FINALIZE_CODE = r"""
global doc, Part, FreeCAD, FreeCADGui, math
import FreeCAD, Part, FreeCADGui, math
doc = FreeCAD.ActiveDocument

doc.recompute()
view = FreeCADGui.ActiveDocument.ActiveView
view.viewIsometric()
view.fitAll()

result = {'objects': len(doc.Objects), 'status': 'ok'}
"""

# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

print("[1/6]  Building frame + fork …")
r1 = conn.execute(FRAME_CODE)
print(f"       Wheelbase: {r1.get('wheelbase_mm', '?')} mm")
print(f"       Head tube bottom: {r1.get('head_bot', '?')}")
print(f"       Objects so far: {r1.get('objects', '?')}\n")

print("[2/6]  Building wheels …")
r2 = conn.execute(WHEEL_CODE)
print(f"       Objects so far: {r2.get('objects', '?')}\n")

print("[3/6]  Building drivetrain …")
r3 = conn.execute(DRIVETRAIN_CODE)
print(f"       Objects so far: {r3.get('objects', '?')}\n")

print("[4/6]  Building cockpit + saddle …")
r4 = conn.execute(COCKPIT_CODE)
print(f"       Bar width: {r4.get('bar_width_mm', '?')} mm")
print(f"       Bar height: {r4.get('bar_height_mm', '?')} mm")
print(f"       Saddle height: {r4.get('saddle_height_mm', '?')} mm")
print(f"       Objects so far: {r4.get('objects', '?')}\n")

print("[5/6]  Building brakes …")
r5 = conn.execute(BRAKE_CODE)
print(f"       Objects so far: {r5.get('objects', '?')}\n")

print("[6/6]  Finalising view …")
r6 = conn.execute(FINALIZE_CODE)
print(f"       Total objects: {r6.get('objects', '?')}\n")

# ── Screenshot ────────────────────────────────────────────────────────────────
print("Capturing screenshot …")
scr = conn.call_function(
    "freecad_ai_bridge.view_ops", "get_screenshot",
    width=1280, height=900, view="isometric")

if isinstance(scr, dict) and "image_base64" in scr:
    img_bytes = base64.b64decode(scr["image_base64"])
    out_path  = os.path.join(OUT, "mountainbike.png")
    with open(out_path, "wb") as fh:
        fh.write(img_bytes)
    print(f"  → fem_output/mountainbike.png  ({len(img_bytes)//1024} kB)\n")
else:
    print(f"  Screenshot error: {scr}\n")

# ── Summary ───────────────────────────────────────────────────────────────────
print("═" * 68)
print("  Mountain Bike – 29er Hardtail Trail  (detailliertes FreeCAD-Modell)")
print("═" * 68)
print("  Rahmen:       Down Tube Ø58, Top Tube Ø46, Seat Tube Ø54 (alle ext.)")
print("  Radgröße:     29\" / 622 ISO  (Reifenradius 368 mm)")
print("  Radstand:     1110 mm")
print("  BB-Höhe:      340 mm  (28 mm BB-Drop)")
print("  Lenker:       760 mm breit, 8° Backsweep, 5° Upsweep")
print("  Kassette:     12-fach  (10T–51T Bereich)")
print("  Bremsen:      Hydraulisch Scheibe, 180/140 mm Rotoren")
print("  Farben:       Schwarz (Rahmen), Silber (Alu-Komp.), Rot (Akzente)")
print("  Screenshot:   fem_output/mountainbike.png")
print("═" * 68)
