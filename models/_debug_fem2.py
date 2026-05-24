import xmlrpc.client
proxy = xmlrpc.client.ServerProxy('http://127.0.0.1:9875/RPC2')

code = """
import FreeCAD, ObjectsFem

doc = FreeCAD.ActiveDocument

# Check Netgen Shape vs Part
ng = doc.getObject('TestNetgen')
ng_shape_props = [p for p in ng.PropertiesList if 'shape' in p.lower() or 'part' in p.lower() or 'solid' in p.lower() or 'mesh' in p.lower()]

# Check NetgenLegacy
ngl = doc.getObject('TestNetgenLegacy')
ngl_shape_props = [p for p in ngl.PropertiesList if 'shape' in p.lower() or 'part' in p.lower() or 'solid' in p.lower() or 'mesh' in p.lower()]

# Check Gmsh all props
gm = doc.getObject('TestGmsh')
gm_all_props = gm.PropertiesList

result = {
    'netgen_shape_related': ng_shape_props,
    'netgen_full_props': ng.PropertiesList,
    'netgenlegacy_shape_related': ngl_shape_props,
    'gmsh_all': gm_all_props,
}
"""
import json
r = proxy.execute(code)
data = json.loads(r)
print("=== Netgen shape-related:", data['result']['netgen_shape_related'])
print("=== NetgenLegacy shape-related:", data['result']['netgenlegacy_shape_related'])
print("=== Gmsh ALL props:", data['result']['gmsh_all'])
print("\n=== Netgen FULL props:", data['result']['netgen_full_props'])
