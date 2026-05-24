import xmlrpc.client, json
proxy = xmlrpc.client.ServerProxy('http://127.0.0.1:9875/RPC2')

# Check getMachine return type and attributes
code = """
import FreeCAD
from femsolver.run import getMachine, run_fem_solver
doc = FreeCAD.ActiveDocument
solver = doc.getObject('CalculiX')

# What does getMachine return?
try:
    machine = getMachine(solver)
    machine_type = type(machine).__name__
    machine_attrs = [a for a in dir(machine) if not a.startswith('_')]
except Exception as e:
    machine_type = str(e)
    machine_attrs = []

# Check NetgenTools more carefully
from femmesh import netgentools
mesh_obj = doc.getObject('FEMMesh')
ng = netgentools.NetgenTools(mesh_obj)
ng_attrs = [a for a in dir(ng) if not a.startswith('_')]

result = {
    'machine_type': machine_type,
    'machine_attrs': machine_attrs,
    'ng_attrs': ng_attrs,
}
"""
r = proxy.execute(code)
data = json.loads(r)['result']
print("Machine type:", data['machine_type'])
print("Machine attrs:", data['machine_attrs'])
print("\nNetgenTools attrs:", data['ng_attrs'])
