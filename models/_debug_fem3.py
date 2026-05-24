import xmlrpc.client, json
proxy = xmlrpc.client.ServerProxy('http://127.0.0.1:9875/RPC2')

# Check correct API
code = """
from femsolver import run as femrun
from femmesh import netgentools

# Check run module attrs
run_attrs = [a for a in dir(femrun) if not a.startswith('_')]

# Check NetgenTools attrs
import FreeCAD
doc = FreeCAD.ActiveDocument
mesh_obj = doc.getObject('FEMMesh')
if mesh_obj:
    ng = netgentools.NetgenTools(mesh_obj)
    ng_attrs = [a for a in dir(ng) if not a.startswith('_')]
else:
    ng_attrs = 'no mesh object'

result = {'run_attrs': run_attrs, 'netgen_attrs': ng_attrs}
"""
r = proxy.execute(code)
data = json.loads(r)['result']
print("femsolver.run functions:", [a for a in data['run_attrs'] if not a[0].isupper()])
print("\nNetgenTools methods:", [a for a in data['netgen_attrs'] if callable])
