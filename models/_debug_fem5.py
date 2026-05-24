import xmlrpc.client, json
proxy = xmlrpc.client.ServerProxy('http://127.0.0.1:9875/RPC2')

# Try makeSolverCalculiX (not CcxTools) - uses getMachine interface
code = """
import FreeCAD, ObjectsFem
from femsolver.run import getMachine
doc = FreeCAD.ActiveDocument

# Try the newer CalculiX solver (not CcxTools)
try:
    solver2 = ObjectsFem.makeSolverCalculiX(doc, 'CalcNew')
    machine = getMachine(solver2)
    machine_type = type(machine).__name__
    machine_attrs = [a for a in dir(machine) if not a.startswith('_')]
    result = {'solver_type': type(solver2).__name__, 'machine_type': machine_type, 'machine_attrs': machine_attrs}
except Exception as e:
    result = {'error': str(e)[:300]}
"""
r = proxy.execute(code)
print(json.loads(r))

# Also check the ccxtools path
code2 = """
avail = []
try:
    from femtools.ccxtools import FemToolsCcx
    avail.append('femtools.ccxtools.FemToolsCcx')
except Exception as e:
    avail.append(f'femtools.ccxtools: {e}')
try:
    import femsolver.calculix.tasks as cctasks
    avail.append('femsolver.calculix.tasks: ' + str(dir(cctasks))[:100])
except Exception as e:
    avail.append(f'femsolver.calculix.tasks: {e}')
try:
    import femsolver.calculix
    avail.append('femsolver.calculix: ' + str(dir(femsolver.calculix))[:100])
except Exception as e:
    avail.append(f'femsolver.calculix: {e}')
result = avail
"""
r2 = proxy.execute(code2)
print(json.loads(r2))
