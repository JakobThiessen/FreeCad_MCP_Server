import xmlrpc.client
proxy = xmlrpc.client.ServerProxy('http://127.0.0.1:9875/RPC2')

code = """
import FreeCAD, ObjectsFem

for n in list(FreeCAD.listDocuments().keys()): FreeCAD.closeDocument(n)
doc = FreeCAD.newDocument('FEM_Debug')

# Test Netgen
try:
    ng = ObjectsFem.makeMeshNetgen(doc, 'TestNetgen')
    ng_props = [p for p in ng.PropertiesList if not p.startswith('_')]
    has_part_ng = hasattr(ng, 'Part')
    has_shape_ng = hasattr(ng, 'Shape')
except Exception as e:
    ng_props = str(e)
    has_part_ng = False
    has_shape_ng = False

# Test NetgenLegacy
try:
    ngl = ObjectsFem.makeMeshNetgenLegacy(doc, 'TestNetgenLegacy')
    ngl_props = [p for p in ngl.PropertiesList if not p.startswith('_')]
    has_part_ngl = hasattr(ngl, 'Part')
except Exception as e:
    ngl_props = str(e)
    has_part_ngl = False

# Test Gmsh
try:
    gm = ObjectsFem.makeMeshGmsh(doc, 'TestGmsh')
    gm_props = [p for p in gm.PropertiesList if not p.startswith('_')]
    has_part_gm = hasattr(gm, 'Part')
except Exception as e:
    gm_props = str(e)
    has_part_gm = False

result = {
    'netgen_has_Part': has_part_ng,
    'netgen_has_Shape': has_shape_ng,
    'netgen_props': ng_props[:10] if isinstance(ng_props, list) else ng_props,
    'netgenlegacy_has_Part': has_part_ngl,
    'netgenlegacy_props': ngl_props[:10] if isinstance(ngl_props, list) else ngl_props,
    'gmsh_has_Part': has_part_gm,
    'gmsh_props': gm_props[:10] if isinstance(gm_props, list) else gm_props,
}
"""
import json
r = proxy.execute(code)
data = json.loads(r)
for k, v in data['result'].items():
    print(f"{k}: {v}")
