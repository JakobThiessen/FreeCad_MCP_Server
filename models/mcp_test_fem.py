"""
MCP Server Volltest + FEM Analyse
==================================
Teil 1: Systematischer Test aller MCP-Tool-Kategorien
Teil 2: Einfaches FEM-Modell (Kragarm / Cantilever Beam)
        - Geometrie via MCP Tools
        - FEM Setup + CalculiX Solver via execute()
        - Analytische Vergleichsrechnung mit numpy

Kragarm: 200mm x 30mm x 30mm Stahlbalken
  - Eingespannt an einer Seite (Face)
  - 1000N Last senkrecht an der anderen Seite
  - Analytisch: δ = FL³/(3EI) ≈ 0.188 mm
"""

import sys, json, time
sys.path.insert(0, r"D:\Proj\FreeCad\AI_Server\src")

from freecad_mcp.connection import FreeCADConnection

# ============================================================
# HILFSFUNKTIONEN
# ============================================================
PASS = 0
FAIL = 0
results = []

def call(conn, module, function, **kwargs):
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    return conn.call_function(module, function, **kwargs)

def test(name, fn):
    global PASS, FAIL
    try:
        result = fn()
        if result and not (isinstance(result, dict) and 'error' in result):
            print(f"  [OK]  {name}")
            PASS += 1
            results.append((name, True, str(result)[:80]))
            return result
        else:
            print(f"  [FAIL] {name}: {result}")
            FAIL += 1
            results.append((name, False, str(result)[:80]))
            return None
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        FAIL += 1
        results.append((name, False, str(e)[:80]))
        return None

# ============================================================
# VERBINDUNG
# ============================================================
print("=" * 60)
print("TEIL 1: MCP SERVER TOOL-TESTS")
print("=" * 60)

conn = FreeCADConnection()
if not conn.connect():
    print("FEHLER: Keine Verbindung zu FreeCAD!")
    sys.exit(1)
print(f"\nVerbunden mit FreeCAD {conn.get_version()}\n")

# ============================================================
# TEST: Dokument-Operationen
# ============================================================
print("\n--- Dokument-Operationen ---")

conn.execute("for n in list(FreeCAD.listDocuments().keys()): FreeCAD.closeDocument(n)")

test("create_document", lambda: call(conn, "freecad_ai_bridge.operations", "create_document", name="MCPTest"))
test("list_objects (leer)", lambda: call(conn, "freecad_ai_bridge.operations", "list_objects"))

# ============================================================
# TEST: Part Primitives
# ============================================================
print("\n--- Part Primitives ---")

test("part_box", lambda: call(conn, "freecad_ai_bridge.part_ops", "make_box",
     length=50, width=30, height=20, x=0, y=0, z=0, name="TestBox"))

test("part_cylinder", lambda: call(conn, "freecad_ai_bridge.part_ops", "make_cylinder",
     radius=15, height=40, x=100, y=0, z=0, name="TestCyl"))

test("part_sphere", lambda: call(conn, "freecad_ai_bridge.part_ops", "make_sphere",
     radius=20, x=200, y=0, z=0, name="TestSphere"))

test("part_cone", lambda: call(conn, "freecad_ai_bridge.part_ops", "make_cone",
     radius1=20, radius2=5, height=40, x=300, y=0, z=0, name="TestCone"))

test("part_torus", lambda: call(conn, "freecad_ai_bridge.part_ops", "make_torus",
     radius1=25, radius2=8, x=400, y=0, z=0, name="TestTorus"))

# ============================================================
# TEST: Transforms
# ============================================================
print("\n--- Transforms ---")

test("move_object", lambda: call(conn, "freecad_ai_bridge.part_ops", "move_object",
     obj_name="TestBox", dx=0, dy=50, dz=0))

test("rotate_object", lambda: call(conn, "freecad_ai_bridge.part_ops", "rotate_object",
     obj_name="TestCyl", axis_x=0, axis_y=0, axis_z=1, angle=45))

test("set_placement", lambda: call(conn, "freecad_ai_bridge.part_ops", "set_placement",
     obj_name="TestCone", x=300, y=60, z=0, rx=0, ry=0, rz=0))

# ============================================================
# TEST: Boolean Operationen
# ============================================================
print("\n--- Boolean Operationen ---")

# Neue Koerper fuer Booleans
call(conn, "freecad_ai_bridge.part_ops", "make_box",
     length=40, width=40, height=40, x=0, y=200, z=0, name="BoolBase")
call(conn, "freecad_ai_bridge.part_ops", "make_cylinder",
     radius=10, height=50, x=20, y=200, z=0, name="BoolTool")

test("boolean_cut", lambda: call(conn, "freecad_ai_bridge.part_ops", "boolean_cut",
     base_name="BoolBase", tool_name="BoolTool", name="BoolResult"))

call(conn, "freecad_ai_bridge.part_ops", "make_box",
     length=30, width=30, height=30, x=100, y=200, z=0, name="FuseA")
call(conn, "freecad_ai_bridge.part_ops", "make_sphere",
     radius=20, x=115, y=215, z=30, name="FuseB")

test("boolean_fuse", lambda: call(conn, "freecad_ai_bridge.part_ops", "boolean_fuse",
     obj_names=["FuseA", "FuseB"], name="FuseResult"))

# ============================================================
# TEST: Sketcher
# ============================================================
print("\n--- Sketcher ---")

# Body fuer PartDesign-Sketches
test("partdesign_body", lambda: call(conn, "freecad_ai_bridge.partdesign_ops", "create_body",
     name="TestBody"))

test("create_sketch (XY)", lambda: call(conn, "freecad_ai_bridge.sketcher_ops", "create_sketch",
     name="TestSketch1", plane="XY", body_name="TestBody"))

test("sketch_add_rectangle", lambda: call(conn, "freecad_ai_bridge.sketcher_ops", "add_rectangle",
     sketch_name="TestSketch1", x1=-20, y1=-15, x2=20, y2=15))

test("sketch_add_circle", lambda: call(conn, "freecad_ai_bridge.sketcher_ops", "add_circle",
     sketch_name="TestSketch1", cx=0, cy=0, radius=8))

# ============================================================
# TEST: PartDesign
# ============================================================
print("\n--- PartDesign ---")

test("partdesign_pad", lambda: call(conn, "freecad_ai_bridge.partdesign_ops", "pad",
     sketch_name="TestSketch1", length=30, name="TestPad"))

test("create_sketch (XZ)", lambda: call(conn, "freecad_ai_bridge.sketcher_ops", "create_sketch",
     name="TestSketch2", plane="XZ", body_name="TestBody"))

test("sketch_add_circle (Loch)", lambda: call(conn, "freecad_ai_bridge.sketcher_ops", "add_circle",
     sketch_name="TestSketch2", cx=0, cy=15, radius=5))

test("partdesign_pocket (through_all)", lambda: call(conn, "freecad_ai_bridge.partdesign_ops", "pocket",
     sketch_name="TestSketch2", length=10, through_all=True, name="TestPocket"))

# ============================================================
# TEST: Objekt-Inspektion
# ============================================================
print("\n--- Inspektion ---")

test("list_objects", lambda: call(conn, "freecad_ai_bridge.operations", "list_objects"))
test("inspect_object", lambda: call(conn, "freecad_ai_bridge.operations", "inspect_object",
     obj_name="TestBody"))

# ============================================================
# TEST: Screenshot (view_ops)
# ============================================================
print("\n--- View ---")

test("screenshot (isometric)", lambda: call(conn, "freecad_ai_bridge.view_ops", "get_screenshot",
     width=400, height=300, view="isometric"))

# ============================================================
# TEST: execute_python (direkter Code)
# ============================================================
print("\n--- execute_python ---")

test("execute_python (Volumen)", lambda: conn.execute("""
import FreeCAD
doc = FreeCAD.ActiveDocument
body = doc.getObject('TestBody')
result = round(body.Shape.Volume, 2)
"""))

# ============================================================
# ZUSAMMENFASSUNG TESTS
# ============================================================
print(f"\n{'=' * 60}")
print(f"TEST ERGEBNISSE: {PASS} bestanden / {PASS+FAIL} gesamt")
if FAIL > 0:
    print("Fehlgeschlagene Tests:")
    for name, ok, msg in results:
        if not ok:
            print(f"  - {name}: {msg}")
print(f"{'=' * 60}")


# ============================================================
# TEIL 2: FEM ANALYSE - KRAGARM
# ============================================================
print("\n" + "=" * 60)
print("TEIL 2: FEM ANALYSE - KRAGARM (Cantilever Beam)")
print("=" * 60)
print("\nModell: 200mm x 30mm x 30mm Stahlbalken")
print("  - Eingespannt: linke Seite (Face1)")
print("  - Last: 1000 N nach unten an rechter Seite (Face2)")
print("  - Material: Baustahl S235 (E=210000 MPa, ν=0.3)")

# --- Analytische Vorberechnung ---
import math
L = 200.0    # mm
b = 30.0     # mm
h = 30.0     # mm
F = 1000.0   # N
E = 210000.0 # MPa (N/mm²)
nu = 0.3

I = b * h**3 / 12          # Flächenträgheitsmoment [mm⁴]
delta_max = F * L**3 / (3 * E * I)  # Maximale Durchbiegung [mm]
sigma_max = F * L * (h/2) / I       # Max. Biegespannung [MPa]
tau_max = 1.5 * F / (b * h)         # Max. Schubspannung [MPa]

print(f"\nAnalytische Lösung:")
print(f"  I = {I:.1f} mm⁴")
print(f"  δ_max = {delta_max:.4f} mm  (Durchbiegung Kragarmende)")
print(f"  σ_max = {sigma_max:.2f} MPa  (Biegespannung Einspannung)")
print(f"  τ_max = {tau_max:.3f} MPa  (Schubspannung)")
print(f"  Sicherheit S235 (Re=235 MPa): {235/sigma_max:.2f}")

# --- FEM Geometrie erstellen (via MCP für Visualisierung) ---
print("\n[FEM] Erstelle Kragarm-Geometrie in FreeCAD...")

conn.execute("for n in list(FreeCAD.listDocuments().keys()): FreeCAD.closeDocument(n)")
call(conn, "freecad_ai_bridge.operations", "create_document", name="FEM_Kragarm")

call(conn, "freecad_ai_bridge.part_ops", "make_box",
     length=L, width=b, height=h,
     x=0, y=0, z=0, name="Kragarm")
print(f"  Kragarm erstellt: {L}x{b}x{h}mm (via MCP)")

# Farbe setzen
conn.execute("""
import FreeCADGui
obj = FreeCAD.ActiveDocument.getObject('Kragarm')
if obj and hasattr(obj, 'ViewObject'):
    obj.ViewObject.ShapeColor = (0.7, 0.7, 0.8)
FreeCADGui.ActiveDocument.ActiveView.fitAll()
FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
result = 'ok'
""")

# ============================================================
# FEM - VOLLSTÄNDIG EXTERN (kein FreeCAD FEM Modul)
# Strukturiertes Hex-Mesh + CalculiX .inp direkt in Python
# ============================================================
print("\n[FEM] Erstelle strukturiertes Hex-Mesh (20x3x3 C3D8-Elemente)...")

import os, subprocess
fem_out_dir = r"D:\Proj\FreeCad\AI_Server\models\fem_output"
os.makedirs(fem_out_dir, exist_ok=True)

# Gitter-Parameter
nx, ny, nz = 20, 3, 3
dx, dy, dz = L/nx, b/ny, h/nz

# Knoten generieren
nodes = {}   # node_id -> (x, y, z)
node_id = 1
node_map = {}  # (ix,iy,iz) -> node_id
for iz in range(nz+1):
    for iy in range(ny+1):
        for ix in range(nx+1):
            nodes[node_id] = (ix*dx, iy*dy, iz*dz)
            node_map[(ix,iy,iz)] = node_id
            node_id += 1

def nid(ix, iy, iz):
    return node_map[(ix, iy, iz)]

# Elemente (C3D8 CalculiX Reihenfolge)
elements = {}  # elem_id -> [n1..n8]
elem_id = 1
for ix in range(nx):
    for iy in range(ny):
        for iz in range(nz):
            elements[elem_id] = [
                nid(ix,   iy,   iz),   nid(ix+1, iy,   iz),
                nid(ix+1, iy+1, iz),   nid(ix,   iy+1, iz),
                nid(ix,   iy,   iz+1), nid(ix+1, iy,   iz+1),
                nid(ix+1, iy+1, iz+1), nid(ix,   iy+1, iz+1),
            ]
            elem_id += 1

# Einspannknoten (x=0)
fixed_nodes = [nid(0, iy, iz) for iy in range(ny+1) for iz in range(nz+1)]
# Lastknoten (x=L)
force_nodes = [nid(nx, iy, iz) for iy in range(ny+1) for iz in range(nz+1)]
fz_per_node = -F / len(force_nodes)  # negativ = nach unten (-Z)

print(f"  Knoten: {len(nodes)}, Elemente: {len(elements)}")
print(f"  Einspannung: {len(fixed_nodes)} Knoten @ x=0")
print(f"  Last: {len(force_nodes)} Knoten @ x={L}mm, Fz={fz_per_node:.2f} N/Knoten")

# CalculiX .inp Datei schreiben
inp_file = os.path.join(fem_out_dir, "kragarm.inp")
print(f"\n[FEM] Schreibe CalculiX .inp Datei...")

with open(inp_file, 'w') as f:
    f.write("** CalculiX Input - Kragarm\n")
    f.write(f"** L={L}mm, b={b}mm, h={h}mm, F={F}N, E={E}MPa, nu={nu}\n\n")

    # Knoten
    f.write("*NODE, NSET=NALL\n")
    for nid_k, (x, y, z) in nodes.items():
        f.write(f"{nid_k}, {x:.6f}, {y:.6f}, {z:.6f}\n")

    # Elemente
    f.write("\n*ELEMENT, TYPE=C3D8, ELSET=EALL\n")
    for eid, ns in elements.items():
        f.write(f"{eid}, " + ", ".join(str(n) for n in ns) + "\n")

    # Knotengruppen
    f.write("\n*NSET, NSET=FIXED\n")
    for i, n in enumerate(fixed_nodes):
        f.write(str(n))
        f.write(",\n" if (i+1) % 8 == 0 else ", ")
    f.write("\n")

    f.write("\n*NSET, NSET=FORCE\n")
    for i, n in enumerate(force_nodes):
        f.write(str(n))
        f.write(",\n" if (i+1) % 8 == 0 else ", ")
    f.write("\n")

    # Material
    f.write(f"\n*MATERIAL, NAME=STAHL\n")
    f.write(f"*ELASTIC\n{E}, {nu}\n")
    f.write(f"*DENSITY\n7.9e-9\n")

    # Section
    f.write("\n*SOLID SECTION, ELSET=EALL, MATERIAL=STAHL\n\n")

    # Einspannung + Schritt
    f.write("*BOUNDARY\nFIXED, 1, 3, 0.0\n")
    f.write("\n*STEP\n*STATIC\n")

    # Kraft
    f.write("\n*CLOAD\n")
    for n in force_nodes:
        f.write(f"{n}, 3, {fz_per_node:.6f}\n")

    # Ausgabe-Anforderungen
    f.write("\n*NODE FILE\nU\n")
    f.write("*EL FILE\nS\n")
    f.write("\n*END STEP\n")

print(f"  .inp geschrieben: {os.path.basename(inp_file)}")

# CalculiX ausführen
print(f"\n[FEM] Starte CalculiX...")
ccx_exe = r"C:\Program Files\FreeCAD 1.1\bin\ccx.exe"
inp_base = os.path.splitext(inp_file)[0]

proc = subprocess.run(
    [ccx_exe, inp_base],
    cwd=fem_out_dir,
    capture_output=True, text=True, timeout=120
)
print(f"  CalculiX returncode: {proc.returncode}")
if proc.returncode != 0:
    print(f"  stderr: {proc.stderr[:200]}")
    print(f"  stdout: {proc.stdout[:200]}")

# --- Ergebnisse aus .frd Datei parsen ---
frd_file = inp_base + ".frd"
fem_result = {}

if os.path.exists(frd_file):
    print(f"\n[FEM] Parse Ergebnisse ({os.path.basename(frd_file)})...")
    displacements = []
    von_mises = []
    section = None

    with open(frd_file, 'r', errors='replace') as f:
        for line in f:
            line = line.rstrip()
            if 'DISP' in line and line.startswith(' -4'):
                section = 'DISP'; continue
            elif 'STRESS' in line and line.startswith(' -4'):
                section = 'STRESS'; continue
            elif line.startswith(' -4'):
                section = None; continue
            elif line.startswith(' -3'):
                section = None; continue

            if section == 'DISP' and line.startswith(' -1'):
                try:
                    # Fixed-width: record(3) + node(10) + 3x value(12)
                    ux = float(line[13:25])
                    uy = float(line[25:37])
                    uz = float(line[37:49])
                    displacements.append((ux**2 + uy**2 + uz**2)**0.5)
                except (ValueError, IndexError):
                    pass

            elif section == 'STRESS' and line.startswith(' -1'):
                try:
                    # Fixed-width: 6 stress components, each 12 chars
                    sxx = float(line[13:25])
                    syy = float(line[25:37])
                    szz = float(line[37:49])
                    sxy = float(line[49:61])
                    sxz = float(line[61:73])
                    syz = float(line[73:85])
                    vm = ((sxx-syy)**2 + (syy-szz)**2 + (szz-sxx)**2
                          + 6*(sxy**2 + syz**2 + sxz**2))**0.5 / 2**0.5
                    von_mises.append(vm)
                except (ValueError, IndexError):
                    pass

    if displacements:
        fem_result = {
            'max_verschiebung_mm': round(max(displacements), 4),
            'max_von_mises_MPa': round(max(von_mises), 2) if von_mises else 0,
            'knoten': len(displacements),
            'status': 'Berechnung OK'
        }
        print(f"  Ergebnis: {fem_result}")
    else:
        fem_result = {'status': 'Keine Daten in .frd', 'stdout': proc.stdout[:200]}
        print(f"  {fem_result}")
else:
    fem_result = {'status': f'.frd nicht gefunden - stdout: {proc.stdout[:300]}'}
    print(f"  {fem_result}")

# --- Screenshot ---
print("\n[FEM] Screenshot...")
try:
    screenshot_result = call(conn, "freecad_ai_bridge.view_ops", "get_screenshot",
                              width=800, height=600, view="isometric")
    if isinstance(screenshot_result, dict) and 'image_base64' in screenshot_result:
        import base64
        img = base64.b64decode(screenshot_result['image_base64'])
        with open(os.path.join(fem_out_dir, "kragarm_screenshot.png"), "wb") as f2:
            f2.write(img)
        print(f"  Screenshot gespeichert ({len(img)} bytes)")
except Exception as e:
    print(f"  Screenshot übersprungen: {e}")

# ============================================================
# ABSCHLUSS - Vergleich FEM vs. Analytisch
# ============================================================
print("\n" + "=" * 60)
print("ERGEBNISVERGLEICH")
print("=" * 60)
print(f"\nAnalytisch (Euler-Bernoulli Balkentheorie):")
print(f"  Maximale Durchbiegung:  {delta_max:.4f} mm")
print(f"  Max. Biegespannung:     {sigma_max:.2f} MPa")

if isinstance(fem_result, dict) and 'max_verschiebung_mm' in fem_result:
    disp_fem = fem_result['max_verschiebung_mm']
    vm_fem   = fem_result.get('max_von_mises_MPa', 0)
    abw_disp = abs(disp_fem - delta_max) / delta_max * 100 if delta_max else 0
    abw_vm   = abs(vm_fem - sigma_max) / sigma_max * 100 if sigma_max else 0

    print(f"\nFEM (CalculiX):")
    print(f"  Maximale Durchbiegung:  {disp_fem:.4f} mm  (Abw. {abw_disp:.1f}%)")
    print(f"  Max. von Mises:         {vm_fem:.2f} MPa  (Abw. {abw_vm:.1f}%)")
    print(f"  Knoten im Netz:         {fem_result.get('knoten', '?')}")
    print(f"\n  Abweichung < 10%: {'JA (gutes Netz)' if abw_disp < 10 else 'NEIN (Netz verfeinern)'}")
else:
    print(f"\nFEM Rohdaten: {fem_result}")

print(f"\n{'=' * 60}")
print(f"MCP Tests: {PASS}/{PASS+FAIL} bestanden")
print(f"{'=' * 60}")
