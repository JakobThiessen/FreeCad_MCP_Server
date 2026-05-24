"""
Fahrradsattel – FreeCAD Design + FEM Analyse
=============================================
1. Sattel-Geometrie als parametrischer Loft in FreeCAD
2. Hex-Mesh (C3D8) synchron zur FreeCAD-Geometrie
3. FEM-Mesh in FreeCAD laden (Visualisierung)
4. CalculiX extern (direktes .inp)
5. Ergebnisse in FreeCAD anzeigen + matplotlib
"""

import sys, os, subprocess, json, base64
import numpy as np

sys.path.insert(0, r"D:\Proj\FreeCad\AI_Server\src")
from freecad_mcp.connection import FreeCADConnection

# ======================================================
# PARAMETER  (identisch für FreeCAD-Loft UND FEM-Mesh)
# ======================================================
L        = 270.0   # Sattellaenge mm
W_NOSE   =  55.0   # Breite Nase mm
W_BACK   = 165.0   # Breite Gesaess mm
T_MAX    =  38.0   # Max. Hoehe (Plateau) mm
T_BACK   =  18.0   # Hoehe hinten mm
T_NOSE_B =   5.0   # Basishöhe vorne mm
T_EDGE   =   4.0   # Mindest-Wanddicke mm
Z_NOSE   =  22.0   # Nasenanhebung mm
PEAK_U   =  0.55   # Hoehemaximum (55 % von Nase)
TRANS_DIP=   9.0   # Querwölbung mm

E_MAT  = 7500.0    # E-Modul MPa (GFK/Nylon-Schale)
NU_MAT = 0.35
RHO    = 1.4e-9    # Dichte kg/mm³
F_LOAD = 800.0     # Fahrerdruck N

Nu, Nv, Nw = 18, 10, 3   # Mesh-Raster longitudinal × lateral × Dicke

OUT = r"D:\Proj\FreeCad\AI_Server\models\fem_output"
os.makedirs(OUT, exist_ok=True)

# ======================================================
# FORMFUNKTIONEN  (gleiche Gleichungen in FreeCAD + Python)
# ======================================================
def half_width(u):
    return W_NOSE/2 + (W_BACK/2 - W_NOSE/2) * (3*u**2 - 2*u**3)

def z_top(u, v=0.0):
    """Oberflächen-Höhe bei (u,v); u∈[0,1], v∈[-1,1]"""
    if u <= PEAK_U:
        t = u / PEAK_U
        zc = T_NOSE_B + (T_MAX - T_NOSE_B) * t**2
    else:
        t = (u - PEAK_U) / (1.0 - PEAK_U)
        zc = T_MAX - (T_MAX - T_BACK) * t**2
    z = zc - TRANS_DIP * float(v)**2
    if u < 0.22:
        z += Z_NOSE * ((0.22 - u) / 0.22)**2
    return max(float(z), T_EDGE)

# ======================================================
# VERBINDUNG ZU FREECAD
# ======================================================
print("=" * 62)
print("  Fahrradsattel  –  FreeCAD Design + FEM")
print("=" * 62)

conn = FreeCADConnection()
if not conn.connect():
    print("FEHLER: keine FreeCAD-Verbindung!")
    sys.exit(1)
print(f"  Verbunden: FreeCAD {conn.get_version()}")

# ======================================================
# 1. FREECAD GEOMETRIE  –  Sattel als Loft
# ======================================================
print("\n[1] FreeCAD – Sattel-Geometrie (Loft)...")

design_code = f"""
import FreeCAD, Part, FreeCADGui, math

for n in list(FreeCAD.listDocuments().keys()):
    FreeCAD.closeDocument(n)

doc = FreeCAD.newDocument('Fahrradsattel')

def hw(u):
    return {W_NOSE}/2 + ({W_BACK}/2 - {W_NOSE}/2)*(3*u**2 - 2*u**3)

def ztop(u, v=0.0):
    if u <= {PEAK_U}:
        t = u/{PEAK_U};  zc = {T_NOSE_B} + ({T_MAX}-{T_NOSE_B})*t**2
    else:
        t = (u-{PEAK_U})/(1.0-{PEAK_U});  zc = {T_MAX} - ({T_MAX}-{T_BACK})*t**2
    z = zc - {TRANS_DIP}*v**2
    if u < 0.22: z += {Z_NOSE}*((0.22-u)/0.22)**2
    return max(z, {T_EDGE})

N_SEC=18; N_PTS=26
wires = []
for i in range(N_SEC):
    u   = i/(N_SEC-1)
    x   = (u-0.5)*{L}
    w   = hw(u)
    bw  = min(w*0.28, 22.0)
    pts = []
    # oberer Bogen (rechts → links)
    for j in range(N_PTS+1):
        vr = 1.0 - 2.0*j/N_PTS
        pts.append(FreeCAD.Vector(x, vr*w, ztop(u, vr)))
    # Basis (links → rechts)
    pts.append(FreeCAD.Vector(x, -bw, 0.0))
    pts.append(FreeCAD.Vector(x,  bw, 0.0))
    try:
        wires.append(Part.makePolygon(pts, True))
    except:
        pass

loft = Part.makeLoft(wires, True, False, False)   # solid=True
sattel = doc.addObject('Part::Feature', 'Sattel')
sattel.Shape = loft
sattel.ViewObject.ShapeColor = (0.15, 0.25, 0.65)
sattel.ViewObject.Transparency = 15
doc.recompute()
FreeCADGui.ActiveDocument.ActiveView.fitAll()
FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
result = {{'vol': round(loft.Volume,0), 'faces': len(loft.Faces)}}
"""

r = conn.execute(design_code)
print(f"  Loft erstellt: {r}")

# Screenshot: Design
print("  Screenshot Design...")
scr = conn.call_function("freecad_ai_bridge.view_ops", "get_screenshot",
                         width=900, height=600, view="isometric")
if isinstance(scr, dict) and 'image_base64' in scr:
    img = base64.b64decode(scr['image_base64'])
    fp  = os.path.join(OUT, 'sattel_design.png')
    open(fp,'wb').write(img)
    print(f"  → sattel_design.png  ({len(img)//1024} kB)")

# ======================================================
# 2. PARAMETRISCHES HEX-MESH  (Python-seitig)
# ======================================================
print("\n[2] Hex-Mesh generieren...")

nodes = {}; nmap = {}; nid = 1
for iu in range(Nu+1):
    u = iu/Nu;  x = (u-0.5)*L;  hw = half_width(u)
    for iv in range(Nv+1):
        vr = 2*iv/Nv-1;  y = vr*hw;  zt = z_top(u, vr)
        for iw in range(Nw+1):
            nodes[nid] = (x, y, (iw/Nw)*zt)
            nmap[(iu,iv,iw)] = nid;  nid += 1

def n(iu,iv,iw): return nmap[(iu,iv,iw)]

elems = {}; eid = 1
for iu in range(Nu):
    for iv in range(Nv):
        for iw in range(Nw):
            elems[eid] = [n(iu,iv,iw),   n(iu+1,iv,iw),   n(iu+1,iv+1,iw),   n(iu,iv+1,iw),
                          n(iu,iv,iw+1), n(iu+1,iv,iw+1), n(iu+1,iv+1,iw+1), n(iu,iv+1,iw+1)]
            eid += 1

print(f"  Knoten: {len(nodes)},  Elemente: {len(elems)} C3D8")

# Mesh als JSON speichern (für FreeCAD-Seite)
mesh_json = os.path.join(OUT, 'sattel_mesh.json')
with open(mesh_json, 'w') as f:
    json.dump({'nodes': {str(k): list(v) for k,v in nodes.items()},
               'elems': {str(k): v       for k,v in elems.items()}}, f)

# ======================================================
# 3. FEM-MESH IN FREECAD LADEN  (Visualisierung)
# ======================================================
print("\n[3] FEM-Mesh in FreeCAD laden...")

fem_mesh_code = f"""
import FreeCAD, ObjectsFem, Fem, json, pathlib

doc = FreeCAD.ActiveDocument
data = json.loads(pathlib.Path(r"{mesh_json}").read_text())

nd = {{int(k): v for k,v in data['nodes'].items()}}
el = {{int(k): v for k,v in data['elems'].items()}}

fc_mesh = Fem.FemMesh()
for nid_k,(x,y,z) in nd.items():
    fc_mesh.addNode(x, y, z, nid_k)
for eid_k, ns in el.items():
    fc_mesh.addVolume(ns, eid_k)

mesh_obj = ObjectsFem.makeMeshGmsh(doc, 'SattelMesh')
mesh_obj.FemMesh = fc_mesh

analysis = ObjectsFem.makeAnalysis(doc, 'Analysis')
analysis.addObject(mesh_obj)

mat = ObjectsFem.makeMaterialSolid(doc, 'GFK_Nylon')
mat.Material = {{'Name':'GFK-Nylon','YoungsModulus':'{E_MAT} MPa',
                 'PoissonRatio':'{NU_MAT}','Density':'1400 kg/m^3'}}
analysis.addObject(mat)

doc.recompute()
result = {{'mesh_nodes': fc_mesh.NodeCount, 'mesh_elems': fc_mesh.VolumeCount}}
"""

r = conn.execute(fem_mesh_code)
print(f"  FemMesh in FreeCAD: {r}")

# ======================================================
# 4. RANDBEDINGUNGEN & LASTEN  (für .inp Datei)
# ======================================================
# Sattelschienen (Lagerung): u ∈ [0.26, 0.77], |vr| < 0.40, iw=0
fix_nodes = list(set(
    n(iu, iv, 0)
    for iu in range(Nu+1)
    for iv in range(Nv+1)
    if 0.24 <= iu/Nu <= 0.78 and abs(2*iv/Nv-1) < 0.42
))

# Sitzknochen: u≈0.62, v≈±0.46
SIT_U, SIT_V, dU, dV = 0.62, 0.46, 0.10, 0.22
load_L = list(set(n(iu,iv,Nw) for iu in range(Nu+1) for iv in range(Nv+1)
               if abs(iu/Nu-SIT_U)<dU and abs((2*iv/Nv-1)+SIT_V)<dV))
load_R = list(set(n(iu,iv,Nw) for iu in range(Nu+1) for iv in range(Nv+1)
               if abs(iu/Nu-SIT_U)<dU and abs((2*iv/Nv-1)-SIT_V)<dV))
# Nasenbereich
load_N = list(set(n(iu,iv,Nw) for iu in range(Nu+1) for iv in range(Nv+1)
               if iu/Nu < 0.22 and abs(2*iv/Nv-1) < 0.30))

fz_L = -0.42*F_LOAD / max(len(load_L),1)
fz_R = -0.42*F_LOAD / max(len(load_R),1)
fz_N = -0.16*F_LOAD / max(len(load_N),1)

print(f"\n[4] RB: {len(fix_nodes)} Lager | Last: {len(load_L)}L {len(load_R)}R {len(load_N)}N Knoten")

# ======================================================
# 5. CALCULIX .INP DATEI  (direkt in Python geschrieben)
# ======================================================
inp_file = os.path.join(OUT, 'sattel.inp')

def wset(f, name, lst):
    f.write(f"\n*NSET, NSET={name}\n")
    for i,k in enumerate(lst or [1]):
        f.write(f"{k}" + (",\n" if (i+1)%8==0 else ", "))
    f.write("\n")

with open(inp_file,'w') as f:
    f.write("** CalculiX – Fahrradsattel FEM\n")
    f.write(f"** L={L}  E={E_MAT}MPa  F={F_LOAD}N\n\n")
    f.write("*NODE, NSET=NALL\n")
    for k,(x,y,z) in nodes.items():
        f.write(f"{k}, {x:.4f}, {y:.4f}, {z:.4f}\n")
    f.write("\n*ELEMENT, TYPE=C3D8, ELSET=EALL\n")
    for k,ns in elems.items():
        f.write(f"{k}, "+",".join(str(m) for m in ns)+"\n")
    wset(f,"FIX",    fix_nodes)
    wset(f,"LOAD_L", load_L)
    wset(f,"LOAD_R", load_R)
    wset(f,"LOAD_N", load_N)
    f.write(f"\n*MATERIAL, NAME=SEAT\n*ELASTIC\n{E_MAT}, {NU_MAT}\n*DENSITY\n{RHO}\n")
    f.write("\n*SOLID SECTION, ELSET=EALL, MATERIAL=SEAT\n\n")
    f.write("*BOUNDARY\nFIX, 1, 3, 0.0\n")
    f.write("\n*STEP\n*STATIC\n\n*CLOAD\n")
    for k in load_L: f.write(f"{k}, 3, {fz_L:.5f}\n")
    for k in load_R: f.write(f"{k}, 3, {fz_R:.5f}\n")
    for k in load_N: f.write(f"{k}, 3, {fz_N:.5f}\n")
    f.write("\n*NODE FILE\nU\n*EL FILE\nS\n\n*END STEP\n")

print(f"  .inp geschrieben: {os.path.basename(inp_file)}")

# ======================================================
# 6. CALCULIX AUSFÜHREN
# ======================================================
print("\n[5] CalculiX starten...")
ccx  = r"C:\Program Files\FreeCAD 1.1\bin\ccx.exe"
base = os.path.splitext(inp_file)[0]
proc = subprocess.run([ccx, base], cwd=OUT,
                      capture_output=True, text=True, timeout=300)
print(f"  Returncode: {proc.returncode}")
if proc.returncode != 0:
    print(f"  stderr: {proc.stderr[:400]}")

# ======================================================
# 7. .FRD PARSEN  (Fixed-Width + Komponenten für FreeCAD)
# ======================================================
frd_file  = base + ".frd"
disp_mag  = {}   # node → |u|
disp_xyz  = {}   # node → (ux, uy, uz)
stress    = {}   # node → von Mises

if os.path.exists(frd_file):
    sec = None
    with open(frd_file,'r',errors='replace') as f:
        for line in f:
            line = line.rstrip()
            if   'DISP'   in line and line.startswith(' -4'): sec='DISP';   continue
            elif 'STRESS' in line and line.startswith(' -4'): sec='STRESS'; continue
            elif line.startswith(' -4') or line.startswith(' -3'):
                sec=None; continue

            if sec == 'DISP' and line.startswith(' -1'):
                try:
                    nd = int(line[3:13])
                    ux,uy,uz = float(line[13:25]),float(line[25:37]),float(line[37:49])
                    disp_xyz[nd] = (ux,uy,uz)
                    disp_mag[nd] = (ux**2+uy**2+uz**2)**0.5
                except (ValueError,IndexError): pass

            elif sec == 'STRESS' and line.startswith(' -1'):
                try:
                    nd = int(line[3:13])
                    s  = [float(line[13+k*12:25+k*12]) for k in range(6)]
                    vm = ((s[0]-s[1])**2+(s[1]-s[2])**2+(s[2]-s[0])**2
                          +6*(s[3]**2+s[4]**2+s[5]**2))**0.5/2**0.5
                    stress[nd] = vm
                except (ValueError,IndexError): pass

    print(f"\n  Parsed: {len(disp_mag)} Verschiebungen, {len(stress)} Spannungen")
    if stress:
        vm_max = max(stress.values()); d_max = max(disp_mag.values())
        print(f"  δ_max = {d_max:.4f} mm   σ_max = {vm_max:.2f} MPa")
else:
    print("  .frd nicht gefunden!")
    vm_max = 1.0; d_max = 0.0

# ======================================================
# 8. ERGEBNISSE IN FREECAD LADEN  (FemResult + Screenshot)
# ======================================================
print("\n[6] Ergebnisse in FreeCAD laden...")

# Ergebnis-Daten als JSON (kompakt)
res_json = os.path.join(OUT, 'sattel_result.json')
node_ids_sorted = sorted(nodes.keys())
with open(res_json,'w') as f:
    json.dump({
        'node_ids':  node_ids_sorted,
        'von_mises': [float(stress.get(k,0)) for k in node_ids_sorted],
        'disp_len':  [float(disp_mag.get(k,0)) for k in node_ids_sorted],
        'disp_vecs': [list(disp_xyz.get(k,(0,0,0))) for k in node_ids_sorted]
    }, f)

result_code = f"""
import FreeCAD, ObjectsFem, FreeCADGui, json, pathlib

doc   = FreeCAD.ActiveDocument
mobj  = doc.getObject('SattelMesh')
aobj  = doc.getObject('Analysis')

rd = json.loads(pathlib.Path(r"{res_json}").read_text())

nids  = rd['node_ids']
vm    = rd['von_mises']
dl    = rd['disp_len']
dvecs = rd['disp_vecs']

try:
    res = ObjectsFem.makeResultMechanical(doc, 'SattelResult')
    res.Mesh = mobj
    res.NodeNumbers       = nids
    res.vonMises          = vm
    res.DisplacementLengths = dl
    res.DisplacementVectors = [FreeCAD.Vector(*v) for v in dvecs]
    if aobj: aobj.addObject(res)
    doc.recompute()

    # Farbdarstellung: von Mises
    FreeCADGui.updateGui()
    # Mesh anzeigen, Solid ausblenden
    sattel = doc.getObject('Sattel')
    if sattel: sattel.ViewObject.Visibility = False
    mobj.ViewObject.Visibility = True

    FreeCADGui.ActiveDocument.ActiveView.fitAll()
    FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
    result = {{'ok': True, 'vm_max': round(max(vm),2)}}
except Exception as e:
    result = {{'ok': False, 'error': str(e)[:200]}}
"""

r = conn.execute(result_code)
print(f"  FemResult: {r}")

# Screenshot: FEM-Ergebnis
print("  Screenshot FEM-Ergebnis...")
conn.execute("""
import FreeCADGui
FreeCADGui.updateGui()
FreeCADGui.ActiveDocument.ActiveView.fitAll()
FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
result = 'ok'
""")
scr2 = conn.call_function("freecad_ai_bridge.view_ops", "get_screenshot",
                           width=900, height=600, view="isometric")
if isinstance(scr2, dict) and 'image_base64' in scr2:
    img2 = base64.b64decode(scr2['image_base64'])
    fp2  = os.path.join(OUT, 'sattel_fem_result.png')
    open(fp2,'wb').write(img2)
    print(f"  → sattel_fem_result.png  ({len(img2)//1024} kB)")

# ======================================================
# 9. MATPLOTLIB VISUALISIERUNG  (Hauptergebnisbild)
# ======================================================
print("\n[7] matplotlib Visualisierung...")
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import matplotlib.colors as mc
    from matplotlib.tri import Triangulation

    s_vals = list(stress.values())
    s_min  = 0.0
    s_max  = float(np.percentile(s_vals, 96)) if s_vals else 1.0
    norm   = mc.Normalize(s_min, s_max)
    cmap   = plt.get_cmap('jet')

    # ---- Meshgrid Oberfläche ----
    X = np.zeros((Nu+1,Nv+1)); Y = np.zeros_like(X)
    Z = np.zeros_like(X);      S = np.zeros_like(X)
    for iu in range(Nu+1):
        for iv in range(Nv+1):
            nd = nmap[(iu,iv,Nw)]
            X[iu,iv], Y[iu,iv], Z[iu,iv] = nodes[nd]
            S[iu,iv] = stress.get(nd, 0.0)

    S_face = np.zeros((Nu,Nv))
    for iu in range(Nu):
        for iv in range(Nv):
            ns4 = [nmap[(iu,iv,Nw)],nmap[(iu+1,iv,Nw)],
                   nmap[(iu+1,iv+1,Nw)],nmap[(iu,iv+1,Nw)]]
            S_face[iu,iv] = np.mean([stress.get(k,0) for k in ns4])
    fc = cmap(norm(S_face))

    # ---- Triangulierung ----
    tx,ty,ts=[],[],[]
    ptmap={}; pid=0
    for iu in range(Nu+1):
        for iv in range(Nv+1):
            nd = nmap[(iu,iv,Nw)]
            tx.append(nodes[nd][0]); ty.append(nodes[nd][1])
            ts.append(stress.get(nd,0.0))
            ptmap[(iu,iv)]=pid; pid+=1
    tris=[]
    for iu in range(Nu):
        for iv in range(Nv):
            a,b = ptmap[(iu,iv)],ptmap[(iu+1,iv)]
            c,d = ptmap[(iu+1,iv+1)],ptmap[(iu,iv+1)]
            tris+=[[a,b,c],[a,c,d]]
    triang = Triangulation(tx,ty,tris)

    # ---- Figur ----
    fig = plt.figure(figsize=(19,8), facecolor='#12121e')
    fig.suptitle(
        f"Fahrradsattel FEM  |  Fahrerdruck {F_LOAD:.0f} N  |  "
        f"E = {E_MAT:.0f} MPa (GFK/Nylon)  |  Mesh {Nu}×{Nv}×{Nw} C3D8",
        color='white', fontsize=13, fontweight='bold', y=0.99)

    # -- 3D isometrische Ansicht --
    ax3 = fig.add_subplot(131, projection='3d', facecolor='#12121e')
    ax3.plot_surface(X, Y, Z, facecolors=fc,
                     rstride=1, cstride=1, linewidth=0.0,
                     antialiased=False, shade=False)
    # Bodenfläche (halbtransparent)
    Xb=np.zeros_like(X); Yb=np.zeros_like(Y); Zb=np.zeros_like(Z)
    for iu in range(Nu+1):
        for iv in range(Nv+1):
            nd=nmap[(iu,iv,0)]
            Xb[iu,iv],Yb[iu,iv],Zb[iu,iv]=nodes[nd]
    ax3.plot_surface(Xb,Yb,Zb,color='#555577',alpha=0.22,
                     rstride=2,cstride=2,linewidth=0,shade=False)
    ax3.scatter([nodes[k][0] for k in fix_nodes[::2]],
                [nodes[k][1] for k in fix_nodes[::2]],
                [nodes[k][2] for k in fix_nodes[::2]],
                c='dodgerblue', s=10, alpha=0.6, label='Schiene')
    ax3.set_title('3D – von-Mises Spannung', color='white', fontsize=10, pad=6)
    ax3.set_xlabel('X mm', color='#aaa', fontsize=7, labelpad=2)
    ax3.set_ylabel('Y mm', color='#aaa', fontsize=7, labelpad=2)
    ax3.set_zlabel('Z mm', color='#aaa', fontsize=7, labelpad=2)
    ax3.tick_params(colors='#888', labelsize=6)
    ax3.view_init(elev=28, azim=-50)
    ax3.set_facecolor('#12121e')
    for p in [ax3.xaxis.pane,ax3.yaxis.pane,ax3.zaxis.pane]:
        p.fill=False; p.set_edgecolor('#333355')
    ax3.legend(fontsize=7,labelcolor='white',
               facecolor='#2a2a4a',edgecolor='#555',loc='upper left')
    sm=cm.ScalarMappable(norm=norm,cmap=cmap); sm.set_array([])
    cb=fig.colorbar(sm,ax=ax3,shrink=0.5,pad=0.04)
    cb.set_label('von Mises [MPa]',color='#ccc',fontsize=8)
    plt.setp(cb.ax.yaxis.get_ticklabels(),color='#ccc'); cb.ax.yaxis.set_tick_params(color='#ccc',labelsize=7)

    # -- Draufsicht: Kraftverteilung --
    ax2=fig.add_subplot(132, facecolor='#0d0d1e')
    cf=ax2.tricontourf(triang,ts,levels=24,cmap='jet',vmin=s_min,vmax=s_max)
    ax2.tricontour(triang,ts,levels=10,colors='white',linewidths=0.3,alpha=0.30)
    # Umriss
    for iu in range(Nu):
        ax2.plot([nodes[nmap[(iu,Nv,Nw)]][0], nodes[nmap[(iu+1,Nv,Nw)]][0]],
                 [nodes[nmap[(iu,Nv,Nw)]][1], nodes[nmap[(iu+1,Nv,Nw)]][1]],
                 '-', color='white', lw=0.8, alpha=0.5)
        ax2.plot([nodes[nmap[(iu,0,Nw)]][0], nodes[nmap[(iu+1,0,Nw)]][0]],
                 [nodes[nmap[(iu,0,Nw)]][1], nodes[nmap[(iu+1,0,Nw)]][1]],
                 '-', color='white', lw=0.8, alpha=0.5)
    # Lager
    ax2.scatter([nodes[k][0] for k in fix_nodes],
                [nodes[k][1] for k in fix_nodes],
                c='dodgerblue',s=15,marker='+',linewidths=1.0,alpha=0.7,label='Schiene')
    # Sitzknochen
    cx_L=np.mean([nodes[k][0] for k in load_L]); cy_L=np.mean([nodes[k][1] for k in load_L])
    cx_R=np.mean([nodes[k][0] for k in load_R]); cy_R=np.mean([nodes[k][1] for k in load_R])
    cx_N=np.mean([nodes[k][0] for k in load_N]); cy_N=np.mean([nodes[k][1] for k in load_N])
    ax2.scatter([cx_L,cx_R],[cy_L,cy_R],c='red',s=240,marker='o',zorder=7,
                edgecolors='white',lw=1.2,label=f'Sitzknochen ({0.42*F_LOAD:.0f} N/Seite)')
    ax2.scatter([cx_N],[cy_N],c='orange',s=180,marker='^',zorder=7,
                edgecolors='white',lw=1,label=f'Nase ({0.16*F_LOAD:.0f} N)')
    for cx,cy,lbl in [(cx_L,cy_L,f'{0.42*F_LOAD:.0f} N'),(cx_R,cy_R,f'{0.42*F_LOAD:.0f} N'),(cx_N,cy_N,f'{0.16*F_LOAD:.0f} N')]:
        ax2.annotate(lbl,xy=(cx,cy),xytext=(cx+20,cy+20),color='white',fontsize=8,
                     arrowprops=dict(arrowstyle='->',color='white',lw=1.0),
                     bbox=dict(boxstyle='round,pad=0.25',fc='#222244',ec='none',alpha=0.9))
    ax2.text(-L/2+10, 0,'NASE',color='#aaa',fontsize=8,ha='left',va='center',fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.3',fc='#0d0d1e',ec='#445',alpha=0.85))
    ax2.text(L/2-10, 0,'GESÄSS',color='#aaa',fontsize=8,ha='right',va='center',fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.3',fc='#0d0d1e',ec='#445',alpha=0.85))
    if stress:
        ax2.text(0.02,0.04,f"σ_max={max(stress.values()):.1f} MPa\nδ_max={max(disp_mag.values()):.4f} mm",
                 transform=ax2.transAxes,color='white',fontsize=9,
                 bbox=dict(boxstyle='round',fc='#1a1a3e',ec='dodgerblue',alpha=0.92))
    ax2.set_xlabel('X mm  ← Nase      Gesäss →', color='#aaa', fontsize=9)
    ax2.set_ylabel('Y mm', color='#aaa', fontsize=9)
    ax2.set_title('Draufsicht – Kraftverteilung\n● Druck  +  Schiene',color='white',fontsize=10)
    ax2.set_aspect('equal')
    ax2.tick_params(colors='#888',labelsize=7)
    ax2.legend(fontsize=8,loc='upper right',facecolor='#2a2a4a',edgecolor='#556',labelcolor='white')
    cb2=fig.colorbar(cf,ax=ax2,pad=0.02)
    cb2.set_label('von Mises [MPa]',color='#ccc',fontsize=8)
    plt.setp(cb2.ax.yaxis.get_ticklabels(),color='#ccc'); cb2.ax.yaxis.set_tick_params(color='#ccc',labelsize=7)

    # -- Seitenansicht (Profil + Verformung) --
    ax_side = fig.add_subplot(133, facecolor='#0d0d1e')
    # Seitenprofil entlang Mittellinie (iv=Nv//2)
    iv_mid = Nv//2
    xs_top = [nodes[nmap[(iu,iv_mid,Nw)]][0] for iu in range(Nu+1)]
    zs_top = [nodes[nmap[(iu,iv_mid,Nw)]][2] for iu in range(Nu+1)]
    zs_bot = [nodes[nmap[(iu,iv_mid,0)]][2]  for iu in range(Nu+1)]
    ss_top = [stress.get(nmap[(iu,iv_mid,Nw)],0) for iu in range(Nu+1)]

    sc_side = ax_side.scatter(xs_top, zs_top, c=ss_top, cmap='jet',
                              vmin=s_min, vmax=s_max, s=40, zorder=5)
    ax_side.fill_between(xs_top, zs_bot, zs_top, alpha=0.3, color='steelblue', label='Sattelquerschnitt')
    ax_side.plot(xs_top, zs_top, '-', color='white', lw=1.2, alpha=0.8)
    ax_side.plot(xs_top, zs_bot, '--', color='#666', lw=0.8, alpha=0.7)

    # Lastpfeile in Seitenansicht
    for nd_list, fz, col in [(load_L,fz_L,'red'),(load_R,fz_R,'red'),(load_N,fz_N,'orange')]:
        for nd_k in nd_list[::max(len(nd_list)//4,1)]:
            xp,yp,zp = nodes[nd_k]
            if abs(yp) < half_width(0.5)*0.6:  # nur Mittellinie
                ax_side.annotate('',xy=(xp,zp),xytext=(xp,zp+12),
                    arrowprops=dict(arrowstyle='->',color=col,lw=1.5))

    # Lager-Marker
    for nd_k in fix_nodes[::3]:
        xp,_,zp = nodes[nd_k]; ax_side.plot(xp,zp,'b+',ms=6,mew=1,alpha=0.7)

    ax_side.set_xlabel('X mm  (Längsachse)', color='#aaa', fontsize=9)
    ax_side.set_ylabel('Z mm  (Höhe)',       color='#aaa', fontsize=9)
    ax_side.set_title('Seitenansicht – Profil\n(Mittellinie, von Mises eingefärbt)',
                      color='white', fontsize=10)
    ax_side.tick_params(colors='#888', labelsize=7)
    cb3 = fig.colorbar(sc_side, ax=ax_side, pad=0.02, shrink=0.8)
    cb3.set_label('von Mises [MPa]', color='#ccc', fontsize=8)
    plt.setp(cb3.ax.yaxis.get_ticklabels(),color='#ccc'); cb3.ax.yaxis.set_tick_params(color='#ccc',labelsize=7)

    plt.tight_layout(rect=[0,0,1,0.97])
    out_img = os.path.join(OUT, 'sattel_spannung.png')
    plt.savefig(out_img, dpi=150, bbox_inches='tight', facecolor='#12121e')
    plt.close()
    print(f"  → sattel_spannung.png")

except ImportError as ie:
    print(f"  matplotlib fehlt: {ie}")

# ======================================================
# 10. ZUSAMMENFASSUNG
# ======================================================
print("\n" + "="*62)
print("  FAHRRADSATTEL – ZUSAMMENFASSUNG")
print("="*62)
print(f"  Geometrie:   {L:.0f} × {W_BACK:.0f} × {T_MAX:.0f} mm  (parametrischer Loft)")
print(f"  Material:    E = {E_MAT:.0f} MPa, ν = {NU_MAT}  (GFK/Nylon-Schale)")
print(f"  Fahrerlast:  {F_LOAD:.0f} N  (bimodal Sitzknochen + Nase)")
print(f"  FEM-Mesh:    {Nu}×{Nv}×{Nw} = {len(elems)} Elemente, {len(nodes)} Knoten  (C3D8)")
if stress:
    vm_mx = max(stress.values()); d_mx = max(disp_mag.values())
    print(f"\n  δ_max   = {d_mx:.4f} mm")
    print(f"  σ_max   = {vm_mx:.2f} MPa   (von Mises)")
    print(f"  η GFK   = {80/vm_mx:.1f}    (σ_yield = 80 MPa)")
    print(f"\n  Kritische Zone: Übergangsbereich Sitzknochen → Sattelschiene")
print(f"\n  Gespeicherte Bilder (fem_output/):")
print(f"    sattel_design.png    – FreeCAD Designansicht")
print(f"    sattel_fem_result.png – FreeCAD FEM-Mesh")
print(f"    sattel_spannung.png  – matplotlib Kraftverteilung")
print("="*62)
