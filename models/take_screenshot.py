import sys, base64, json
sys.path.insert(0, r"D:\Proj\FreeCad\AI_Server\src")
from freecad_mcp.connection import FreeCADConnection

conn = FreeCADConnection()
conn.connect()

# Nutze die view_ops.get_screenshot Funktion des MCP Servers
result = conn.call_function("freecad_ai_bridge.view_ops", "get_screenshot",
                            width=800, height=600, view="isometric")

data = json.loads(result) if isinstance(result, str) else result
img_b64 = data.get('image_base64', '')

img_data = base64.b64decode(img_b64)
with open(r'D:\Proj\FreeCad\AI_Server\testbilder\model_screenshot.png', 'wb') as f:
    f.write(img_data)
print(f'Screenshot gespeichert ({len(img_data)} bytes)')
