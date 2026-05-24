import xmlrpc.client, json
proxy = xmlrpc.client.ServerProxy('http://127.0.0.1:9875/RPC2')

code = """
# Find the correct FemMesh module name in FreeCAD 1.1
avail = []
for mod_name in ['FemMesh', 'Fem', 'femobjects', 'FreeCAD.Fem']:
    try:
        m = __import__(mod_name)
        avail.append(f'{mod_name}: OK -> {[a for a in dir(m) if "mesh" in a.lower() or "Mesh" in a][:5]}')
    except Exception as e:
        avail.append(f'{mod_name}: {e}')

# Try via FreeCAD module
try:
    import FreeCAD
    fc_mesh = FreeCAD.Units  # dummy
    avail.append(f'FreeCAD module ok')
    # Try creating a FemMesh via FreeCAD
    m = FreeCAD.newDocument('tmp_fem_test')
    o = m.addObject('Fem::FemMeshObject', 'TestMesh')
    mesh_cls = type(o.FemMesh).__name__
    avail.append(f'FemMeshObject type: {mesh_cls}')
    import FreeCAD
    FreeCAD.closeDocument('tmp_fem_test')
except Exception as e:
    avail.append(f'FemMeshObject error: {e}')

result = avail
"""
r = proxy.execute(code)
print(json.loads(r)['result'])
