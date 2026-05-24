"""
Fahrradsattel – Gekruemmtes FEM-Mesh + Kraftverteilung
=======================================================
Erzeugt einen parametrischen Fahrradsattel als strukturiertes
Hex-Mesh (C3D8), loest mit CalculiX und zeigt die Spannungs-
verteilung / Krafteinwirkung auf der Sitzflaeche.

Geometrie:  270 x 165 x 38 mm  (L x W_max x H_mitte)
Lagerung:   Sattelschienen (mittlerer Laengsstreifen, unten)
Belastung:  Fahrerdruck 800 N  –  bimodal (Sitzknochen) + Nase
"""

import sys, os, subprocess
import numpy as np

# ======================================================
# PARAMETER
# ======================================================
L       = 270.0   # Sattellaenge  mm
W_NOSE  =  55.0   # Breite Nase   mm
W_BACK  = 165.0   # Breite Gesaess mm
T_MAX   =  38.0   # Maximale Hoehe (Mitte) mm
T_EDGE  =   5.0   # Mindest-Wanddicke mm
Z_NOSE  =  22.0   # Nasenanhebung mm
TRANSVERSE_DIP = 9.0   # Querwölbung (Sattelform) mm

E_MAT  = 7500.0   # Elastizitaetsmodul  MPa  (GFK/Nylon-Schale)
NU_MAT = 0.35
RHO    = 1.4e-9   # Dichte kg/mm³

F_LOAD = 800.0    # Fahrerdruck gesamt  N

# Mesh-Auflosung
Nu, Nv, Nw = 18, 10, 3   # longitudinal x lateral x Dicke

OUT = r"D:\Proj\FreeCad\AI_Server\models\fem_output"
os.makedirs(OUT, exist_ok=True)

# ======================================================
# FORMFUNKTIONEN – Sattelgeometrie
# ======================================================
def half_width(u):
    """Halbe Sattelbreite bei normierter Position u ∈ [0,1]  (0=Nase, 1=Gesäss)"""
    # Smooth-Step: schmal vorne, breit hinten
    t = 3*u**2 - 2*u**3           # Hermite-Interpolation
    return W_NOSE/2 + (W_BACK/2 - W_NOSE/2) * t

def z_top(u, v):
    """
    Oberflaechenhoehe z(u,v)
    u ∈ [0,1]   Laengsrichtung (0=Nase, 1=Gesaess)
    v ∈ [-1,1]  Querrichtung   (0=Mitte)
    """
    # Laengsgewölbung: Sinus-Bogen (Peak bei ca. 50 %)
    z = T_MAX * np.sin(np.pi * (u * 0.92 + 0.04))

    # Nasenerhebung (vorderes Ende ist hochgezogen)
    if u < 0.22:
        z += Z_NOSE * ((0.22 - u) / 0.22) ** 2

    # Querwoelbung: leicht sattelfoermig konkav
    z -= TRANSVERSE_DIP * v**2

    return float(max(z, T_EDGE))

# ======================================================
# KNOTEN GENERIEREN
# ======================================================
print("=" * 55)
print("  Fahrradsattel – parametrisches Hex-Mesh")
print("=" * 55)

nodes = {}   # node_id → (x, y, z)
nmap  = {}   # (iu, iv, iw) → node_id
nid   = 1

for iu in range(Nu + 1):
    u   = iu / Nu
    x   = (u - 0.5) * L           # -135 … +135 mm
    hw  = half_width(u)
    for iv in range(Nv + 1):
        vr  = 2 * iv / Nv - 1     # -1 … +1
        y   = vr * hw
        zt  = z_top(u, vr)
        for iw in range(Nw + 1):
            z = (iw / Nw) * zt    # lineare Verteilung Boden → Decke
            nodes[nid]      = (x, y, z)
            nmap[(iu,iv,iw)] = nid
            nid += 1

def n(iu, iv, iw):
    return nmap[(iu, iv, iw)]

print(f"  Knoten: {len(nodes)}")
print(f"  Elemente: {Nu * Nv * Nw}  (C3D8)")

# ======================================================
# ELEMENTE (C3D8 – 8-Knoten-Hexaeder)
# ======================================================
elems = {}
eid   = 1
for iu in range(Nu):
    for iv in range(Nv):
        for iw in range(Nw):
            elems[eid] = [
                n(iu,   iv,   iw),   n(iu+1, iv,   iw),
                n(iu+1, iv+1, iw),   n(iu,   iv+1, iw),
                n(iu,   iv,   iw+1), n(iu+1, iv,   iw+1),
                n(iu+1, iv+1, iw+1), n(iu,   iv+1, iw+1),
            ]
            eid += 1

# ======================================================
# RANDBEDINGUNGEN – Sattelschienen (Lagerung)
# ======================================================
# Schienen: Laengsbereich u ∈ [0.27, 0.77], innerer Bereich |vr| < 0.38, Boden (iw=0)
fix_nodes = []
for iu in range(Nu + 1):
    u = iu / Nu
    if 0.25 <= u <= 0.78:
        for iv in range(Nv + 1):
            vr = 2 * iv / Nv - 1
            if abs(vr) < 0.40:
                fix_nodes.append(n(iu, iv, 0))

fix_nodes = list(set(fix_nodes))

# ======================================================
# BELASTUNGSKNOTEN – Sitzknochen + Nase
# ======================================================
# Linker Sitzknochen:  u ≈ 0.63, vr ≈ -0.46
# Rechter Sitzknochen: u ≈ 0.63, vr ≈ +0.46
# Nasenbereich:        u < 0.22,  vr ≈ 0

SIT_U    = 0.63   # Laengsposition Sitzknochen (63 % von Nase)
SIT_V    = 0.46   # Querposition (relativ)
SIT_DU   = 0.11   # Toleranzbereich Laenge
SIT_DV   = 0.22   # Toleranzbereich Quer

load_L, load_R, load_N = [], [], []
for iu in range(Nu + 1):
    u = iu / Nu
    for iv in range(Nv + 1):
        vr = 2 * iv / Nv - 1
        if abs(u - SIT_U) < SIT_DU and abs(vr + SIT_V) < SIT_DV:
            load_L.append(n(iu, iv, Nw))    # links (vr < 0)
        if abs(u - SIT_U) < SIT_DU and abs(vr - SIT_V) < SIT_DV:
            load_R.append(n(iu, iv, Nw))    # rechts (vr > 0)
        if u < 0.22 and abs(vr) < 0.30:
            load_N.append(n(iu, iv, Nw))    # Nase

load_L = list(set(load_L))
load_R = list(set(load_R))
load_N = list(set(load_N))

# Kraft pro Knoten
fz_L = -0.42 * F_LOAD / max(len(load_L), 1)   # 42 % links
fz_R = -0.42 * F_LOAD / max(len(load_R), 1)   # 42 % rechts
fz_N = -0.16 * F_LOAD / max(len(load_N), 1)   # 16 % Nase

print(f"\n  Lagerknoten (Schienen): {len(fix_nodes)}")
print(f"  Lastknoten links:       {len(load_L)}  @ Fz={fz_L:.1f} N/Knoten")
print(f"  Lastknoten rechts:      {len(load_R)}  @ Fz={fz_R:.1f} N/Knoten")
print(f"  Lastknoten Nase:        {len(load_N)}  @ Fz={fz_N:.1f} N/Knoten")
print(f"  Gesamtkraft: {fz_L*len(load_L)+fz_R*len(load_R)+fz_N*len(load_N):.0f} N")

# ======================================================
# CALCULIX .INP DATEI SCHREIBEN
# ======================================================
inp_file = os.path.join(OUT, "sattel.inp")

def write_nset(f, name, nlist):
    f.write(f"\n*NSET, NSET={name}\n")
    if not nlist:
        f.write("1\n")
        return
    for i, nd in enumerate(nlist):
        f.write(f"{nd}" + (",\n" if (i + 1) % 8 == 0 else ", "))
    f.write("\n")

print(f"\n  Schreibe {os.path.basename(inp_file)}...")

with open(inp_file, 'w') as f:
    f.write("** CalculiX – Fahrradsattel FEM\n")
    f.write(f"** L={L}mm W_back={W_BACK}mm T_max={T_MAX}mm E={E_MAT}MPa F={F_LOAD}N\n\n")

    # Knoten
    f.write("*NODE, NSET=NALL\n")
    for nd, (x, y, z) in nodes.items():
        f.write(f"{nd}, {x:.4f}, {y:.4f}, {z:.4f}\n")

    # Elemente
    f.write("\n*ELEMENT, TYPE=C3D8, ELSET=EALL\n")
    for eid, ns in elems.items():
        f.write(f"{eid}, " + ",".join(str(k) for k in ns) + "\n")

    # Knotengruppen
    write_nset(f, "FIX",    fix_nodes)
    write_nset(f, "LOAD_L", load_L)
    write_nset(f, "LOAD_R", load_R)
    write_nset(f, "LOAD_N", load_N)

    # Material
    f.write(f"\n*MATERIAL, NAME=SEAT\n")
    f.write(f"*ELASTIC\n{E_MAT}, {NU_MAT}\n")
    f.write(f"*DENSITY\n{RHO}\n")
    f.write("\n*SOLID SECTION, ELSET=EALL, MATERIAL=SEAT\n\n")

    # Randbedingungen (alle 3 Freiheitsgrade fixiert)
    f.write("*BOUNDARY\nFIX, 1, 3, 0.0\n")

    # Schritt – statische Analyse
    f.write("\n*STEP\n*STATIC\n")

    # Knotenlasten
    f.write("\n*CLOAD\n")
    for nd in load_L:
        f.write(f"{nd}, 3, {fz_L:.5f}\n")
    for nd in load_R:
        f.write(f"{nd}, 3, {fz_R:.5f}\n")
    for nd in load_N:
        f.write(f"{nd}, 3, {fz_N:.5f}\n")

    # Ergebnisausgabe
    f.write("\n*NODE FILE\nU\n")
    f.write("*EL FILE\nS\n")
    f.write("\n*END STEP\n")

# ======================================================
# CALCULIX AUSFUEHREN
# ======================================================
ccx_exe  = r"C:\Program Files\FreeCAD 1.1\bin\ccx.exe"
inp_base = os.path.splitext(inp_file)[0]

print("  Starte CalculiX...")
proc = subprocess.run(
    [ccx_exe, inp_base],
    cwd=OUT, capture_output=True, text=True, timeout=300
)
print(f"  CalculiX Returncode: {proc.returncode}")
if proc.returncode != 0:
    print(f"  stderr: {proc.stderr[:400]}")

# ======================================================
# .FRD PARSEN  (Fixed-Width Format)
# ======================================================
frd_file = inp_base + ".frd"
disp   = {}   # node_id → Verschiebungsbetrag
stress = {}   # node_id → von-Mises-Spannung

if os.path.exists(frd_file):
    sec = None
    with open(frd_file, 'r', errors='replace') as f:
        for line in f:
            line = line.rstrip()
            if   'DISP'   in line and line.startswith(' -4'): sec = 'DISP';   continue
            elif 'STRESS' in line and line.startswith(' -4'): sec = 'STRESS'; continue
            elif line.startswith(' -4') or line.startswith(' -3'):
                sec = None; continue

            if sec == 'DISP' and line.startswith(' -1'):
                try:
                    nd = int(line[3:13])
                    ux, uy, uz = float(line[13:25]), float(line[25:37]), float(line[37:49])
                    disp[nd] = (ux**2 + uy**2 + uz**2) ** 0.5
                except (ValueError, IndexError):
                    pass

            elif sec == 'STRESS' and line.startswith(' -1'):
                try:
                    nd  = int(line[3:13])
                    s   = [float(line[13 + k*12 : 25 + k*12]) for k in range(6)]
                    vm  = ((s[0]-s[1])**2 + (s[1]-s[2])**2 + (s[2]-s[0])**2
                            + 6*(s[3]**2 + s[4]**2 + s[5]**2)) ** 0.5 / 2**0.5
                    stress[nd] = vm
                except (ValueError, IndexError):
                    pass

    print(f"  Verschiebungs-Knoten: {len(disp)}")
    print(f"  Spannungs-Knoten:     {len(stress)}")

if stress:
    vm_max  = max(stress.values())
    vm_mean = sum(stress.values()) / len(stress)
    d_max   = max(disp.values()) if disp else 0.0
    safety  = 80.0 / vm_max if vm_max > 0 else float('inf')
    print(f"\n  δ_max  = {d_max:.3f} mm")
    print(f"  σ_max  = {vm_max:.2f} MPa  (von Mises)")
    print(f"  σ_mean = {vm_mean:.2f} MPa")
    print(f"  η      = {safety:.2f}  (σ_yield=80 MPa, GFK/Nylon)")
else:
    vm_max = 1.0; d_max = 0.0

# ======================================================
# MATPLOTLIB-VISUALISIERUNG
# ======================================================
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import matplotlib.colors as mc
    from matplotlib.tri import Triangulation

    s_vals  = list(stress.values())
    s_min   = 0.0
    s_max   = float(np.percentile(s_vals, 96)) if s_vals else 1.0
    norm    = mc.Normalize(s_min, s_max)
    cmap    = plt.get_cmap('jet')

    # --------------------------------------------------
    # Meshgrid Oberfläche (top, iw=Nw)
    # --------------------------------------------------
    X  = np.zeros((Nu+1, Nv+1))
    Y  = np.zeros((Nu+1, Nv+1))
    Z  = np.zeros((Nu+1, Nv+1))
    S  = np.zeros((Nu+1, Nv+1))   # Spannung an jedem Knoten

    for iu in range(Nu+1):
        for iv in range(Nv+1):
            nd         = nmap[(iu, iv, Nw)]
            X[iu, iv]  = nodes[nd][0]
            Y[iu, iv]  = nodes[nd][1]
            Z[iu, iv]  = nodes[nd][2]
            S[iu, iv]  = stress.get(nd, 0.0)

    # Farbmatrix: face-average (Nu × Nv)
    S_face = np.zeros((Nu, Nv))
    for iu in range(Nu):
        for iv in range(Nv):
            nds        = [nmap[(iu,iv,Nw)], nmap[(iu+1,iv,Nw)],
                          nmap[(iu+1,iv+1,Nw)], nmap[(iu,iv+1,Nw)]]
            S_face[iu, iv] = np.mean([stress.get(k, 0) for k in nds])

    face_colors = cmap(norm(S_face))   # (Nu, Nv, 4)

    # --------------------------------------------------
    # Triangulierung für 2D Konturplot
    # --------------------------------------------------
    tx, ty, ts = [], [], []
    pt_map = {}
    pid = 0
    for iu in range(Nu+1):
        for iv in range(Nv+1):
            nd = nmap[(iu, iv, Nw)]
            tx.append(nodes[nd][0])
            ty.append(nodes[nd][1])
            ts.append(stress.get(nd, 0.0))
            pt_map[(iu, iv)] = pid
            pid += 1

    tris = []
    for iu in range(Nu):
        for iv in range(Nv):
            a = pt_map[(iu,   iv)]
            b = pt_map[(iu+1, iv)]
            c = pt_map[(iu+1, iv+1)]
            d = pt_map[(iu,   iv+1)]
            tris += [[a, b, c], [a, c, d]]

    triang = Triangulation(tx, ty, tris)

    # --------------------------------------------------
    # FIGUR
    # --------------------------------------------------
    fig = plt.figure(figsize=(18, 8), facecolor='#1a1a2e')
    fig.suptitle(
        f"Fahrradsattel  –  FEM Kraftverteilung  |  Fahrerdruck {F_LOAD:.0f} N  |  "
        f"E = {E_MAT:.0f} MPa  |  Mesh: {Nu}×{Nv}×{Nw} C3D8",
        fontsize=13, fontweight='bold', color='white', y=0.98)

    # ---- 3D Sitzfläche -------------------------------------------
    ax3 = fig.add_subplot(121, projection='3d', facecolor='#1a1a2e')

    surf = ax3.plot_surface(
        X, Y, Z,
        facecolors=face_colors,
        rstride=1, cstride=1,
        linewidth=0.0, antialiased=False, shade=False
    )

    # Bodenfläche zur Orientierung (transparent grau)
    X_bot = np.zeros((Nu+1, Nv+1))
    Y_bot = np.zeros((Nu+1, Nv+1))
    Z_bot = np.zeros((Nu+1, Nv+1))
    for iu in range(Nu+1):
        for iv in range(Nv+1):
            nd = nmap[(iu, iv, 0)]
            X_bot[iu,iv], Y_bot[iu,iv], Z_bot[iu,iv] = nodes[nd]
    ax3.plot_surface(X_bot, Y_bot, Z_bot,
                     color='#888888', alpha=0.25,
                     rstride=2, cstride=2, linewidth=0, shade=False)

    # Lagerknoten (blau)
    fx_x = [nodes[k][0] for k in fix_nodes[::2]]
    fx_y = [nodes[k][1] for k in fix_nodes[::2]]
    fx_z = [nodes[k][2] for k in fix_nodes[::2]]
    ax3.scatter(fx_x, fx_y, fx_z, c='dodgerblue', s=12, alpha=0.7,
                label='Sattelschiene (fixiert)')

    ax3.set_xlabel('X  mm', color='lightgray', labelpad=4, fontsize=8)
    ax3.set_ylabel('Y  mm', color='lightgray', labelpad=4, fontsize=8)
    ax3.set_zlabel('Z  mm', color='lightgray', labelpad=4, fontsize=8)
    ax3.tick_params(colors='lightgray', labelsize=7)
    ax3.set_title('3D-Ansicht  –  von-Mises Spannung',
                  color='white', fontsize=10, pad=8)
    ax3.view_init(elev=30, azim=-48)
    ax3.set_facecolor('#1a1a2e')
    for pane in [ax3.xaxis.pane, ax3.yaxis.pane, ax3.zaxis.pane]:
        pane.fill = False
        pane.set_edgecolor('#444466')
    ax3.legend(fontsize=7, labelcolor='white',
               facecolor='#2a2a4a', edgecolor='#555577', loc='upper left')

    sm = cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cb3 = fig.colorbar(sm, ax=ax3, shrink=0.5, pad=0.04, aspect=20)
    cb3.set_label('von-Mises  [MPa]', color='lightgray', fontsize=8)
    cb3.ax.yaxis.set_tick_params(color='lightgray', labelsize=7)
    plt.setp(cb3.ax.yaxis.get_ticklabels(), color='lightgray')

    # ---- 2D Draufsicht (Kraftverteilung) -------------------------
    ax2 = fig.add_subplot(122, facecolor='#0d0d1e')

    cf = ax2.tricontourf(triang, ts, levels=22, cmap='jet',
                         vmin=s_min, vmax=s_max)
    ax2.tricontour(triang, ts, levels=9,
                   colors='white', linewidths=0.35, alpha=0.35)

    # Satteldurchriss als weisse Linie (Umriss)
    for iu in range(Nu):
        x0, y0_pos = nodes[nmap[(iu,   Nv, Nw)]][0], nodes[nmap[(iu,   Nv, Nw)]][1]
        x1, y1_pos = nodes[nmap[(iu+1, Nv, Nw)]][0], nodes[nmap[(iu+1, Nv, Nw)]][1]
        x0n, y0n   = nodes[nmap[(iu,   0,  Nw)]][0], nodes[nmap[(iu,   0,  Nw)]][1]
        x1n, y1n   = nodes[nmap[(iu+1, 0,  Nw)]][0], nodes[nmap[(iu+1, 0,  Nw)]][1]
        ax2.plot([x0, x1], [y0_pos, y1_pos], '-', color='white', lw=0.7, alpha=0.6)
        ax2.plot([x0n, x1n], [y0n, y1n], '-', color='white', lw=0.7, alpha=0.6)

    # Lagerknoten
    ax2.scatter([nodes[k][0] for k in fix_nodes],
                [nodes[k][1] for k in fix_nodes],
                c='dodgerblue', s=14, marker='+', linewidths=0.8,
                alpha=0.7, label='Sattelschiene', zorder=5)

    # Sitzknochen-Belastung: rote Kreise + Pfeile
    cx_L = np.mean([nodes[k][0] for k in load_L])
    cy_L = np.mean([nodes[k][1] for k in load_L])
    cx_R = np.mean([nodes[k][0] for k in load_R])
    cy_R = np.mean([nodes[k][1] for k in load_R])
    cx_N = np.mean([nodes[k][0] for k in load_N])
    cy_N = np.mean([nodes[k][1] for k in load_N])

    # Markierungen
    ax2.scatter([cx_L, cx_R], [cy_L, cy_R],
                c='red', s=220, marker='o', zorder=7, edgecolors='white', linewidths=1,
                label=f'Sitzknochen ({0.42*F_LOAD:.0f} N/Seite)')
    ax2.scatter([cx_N], [cy_N],
                c='orange', s=160, marker='^', zorder=7, edgecolors='white', linewidths=1,
                label=f'Nasenbereich ({0.16*F_LOAD:.0f} N)')

    # Beschriftungs-Pfeile
    for cx, cy, label in [(cx_L, cy_L, f'{0.42*F_LOAD:.0f} N'),
                           (cx_R, cy_R, f'{0.42*F_LOAD:.0f} N'),
                           (cx_N, cy_N, f'{0.16*F_LOAD:.0f} N')]:
        ax2.annotate(label,
                     xy=(cx, cy),
                     xytext=(cx + 18, cy + 18),
                     color='white', fontsize=7.5, fontweight='bold',
                     arrowprops=dict(arrowstyle='->', color='white', lw=1.0),
                     bbox=dict(boxstyle='round,pad=0.2', fc='#333355', ec='none', alpha=0.8))

    # Achsenbeschriftungen
    ax2.set_xlabel('X (mm)  ←  Nase             Gesäss  →', color='lightgray', fontsize=9)
    ax2.set_ylabel('Y (mm)  Querrichtung',  color='lightgray', fontsize=9)
    ax2.set_title('Draufsicht  –  Kraftverteilung auf der Sitzfläche\n'
                  '   ●  = Fahrerdruck    +  = Sattelschiene',
                  color='white', fontsize=10)
    ax2.set_aspect('equal')
    ax2.tick_params(colors='lightgray', labelsize=7)
    for spine in ax2.spines.values():
        spine.set_edgecolor('#444466')

    # Nase / Gesäss Label
    ax2.text(-L/2 + 8, 0, 'NASE', color='lightgray', fontsize=8, ha='left',
             va='center', fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.3', fc='#0d0d1e', ec='#555577', alpha=0.85))
    ax2.text(L/2 - 8, 0, 'GESÄSS', color='lightgray', fontsize=8, ha='right',
             va='center', fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.3', fc='#0d0d1e', ec='#555577', alpha=0.85))

    # Ergebnis-Infobox
    if stress:
        info = (f"σ_max  = {vm_max:.1f} MPa\n"
                f"δ_max  = {d_max:.3f} mm\n"
                f"η (80 MPa) = {80/vm_max:.2f}")
        ax2.text(0.02, 0.04, info,
                 transform=ax2.transAxes, fontsize=8.5, color='white',
                 bbox=dict(boxstyle='round,pad=0.4', fc='#1a1a3e',
                           ec='dodgerblue', alpha=0.92))

    leg = ax2.legend(fontsize=8, loc='upper right',
                     facecolor='#2a2a4a', edgecolor='#555577', labelcolor='white')

    cb2 = fig.colorbar(cf, ax=ax2, pad=0.02, aspect=25)
    cb2.set_label('von-Mises  [MPa]', color='lightgray', fontsize=8)
    cb2.ax.yaxis.set_tick_params(color='lightgray', labelsize=7)
    plt.setp(cb2.ax.yaxis.get_ticklabels(), color='lightgray')

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    out_img = os.path.join(OUT, 'sattel_spannung.png')
    plt.savefig(out_img, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()
    print(f"\n  Bild gespeichert: {out_img}")

except ImportError as ie:
    print(f"\n  matplotlib nicht verfügbar: {ie}")
    print("  → pip install matplotlib")

# ======================================================
# ZUSAMMENFASSUNG
# ======================================================
print("\n" + "=" * 55)
print("  FAHRRADSATTEL FEM – ZUSAMMENFASSUNG")
print("=" * 55)
print(f"  Geometrie:    {L:.0f} x {W_BACK:.0f} x {T_MAX:.0f} mm")
print(f"  Material:     E = {E_MAT:.0f} MPa, ν = {NU_MAT}")
print(f"  Fahrerdruck:  {F_LOAD:.0f} N  (bimodal: Sitzknochen + Nase)")
print(f"  Mesh:         {Nu}×{Nv}×{Nw} = {Nu*Nv*Nw} Elemente, {len(nodes)} Knoten")
if stress:
    print(f"\n  δ_max  = {d_max:.3f} mm   (max. Durchbiegung)")
    print(f"  σ_max  = {vm_max:.2f} MPa  (von-Mises, max.)")
    print(f"  η      = {80/vm_max:.2f}   (σ_yield = 80 MPa)")
    print(f"\n  Kritische Zone: Sitzknochen-Bereich")
    print(f"  Sicherheit ausreichend: {'JA' if 80/vm_max >= 1.5 else 'NEIN – Geometrie pruefen!'}")
print("=" * 55)
