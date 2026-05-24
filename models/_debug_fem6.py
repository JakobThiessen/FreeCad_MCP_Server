import xmlrpc.client, json
proxy = xmlrpc.client.ServerProxy('http://127.0.0.1:9875/RPC2')

code = """
import FreeCAD
from femtools.ccxtools import FemToolsCcx
doc = FreeCAD.ActiveDocument
analysis = doc.getObject('Analysis')
solver = doc.getObject('CalculiX')

ccx = FemToolsCcx(analysis=analysis, solver=solver)
ccx_attrs = [a for a in dir(ccx) if not a.startswith('_')]
result = ccx_attrs
"""
r = proxy.execute(code)
data = json.loads(r)['result']
# Filter relevant methods
relevant = [a for a in data if any(k in a.lower() for k in ['write', 'run', 'solve', 'load', 'work', 'check', 'setup', 'inp', 'result', 'mesh'])]
print("Relevant FemToolsCcx methods:", relevant)
print("\nAll:", data)
