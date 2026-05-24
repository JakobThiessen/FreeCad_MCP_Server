import xmlrpc.client
proxy = xmlrpc.client.ServerProxy('http://127.0.0.1:9875/RPC2')
code = """
try:
    from femmesh import gmshtools
    has_gmshtools = True
except Exception as e:
    has_gmshtools = str(e)
try:
    from femsolver import run as femrun
    has_femsolver = True
except Exception as e:
    has_femsolver = str(e)
try:
    import ObjectsFem
    has_objectsfem = True
except Exception as e:
    has_objectsfem = str(e)
result = {"gmshtools": has_gmshtools, "femsolver": has_femsolver, "objectsfem": has_objectsfem}
"""
print(proxy.execute(code))
