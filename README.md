# FreeCAD MCP Server

Ein MCP Server der Claude (und andere AI-Assistenten) direkt mit einer laufenden FreeCAD-Instanz verbindet — mit vollem Sketcher-, Part- und PartDesign-Funktionsumfang und Echtzeit-GUI-Updates.

## Architektur

```
Claude (VS Code / Desktop)
    │ stdio (JSON-RPC / MCP Protocol)
    ▼
MCP Server (Python, FastMCP)         ← src/freecad_mcp/
    │ XML-RPC (localhost:9875)
    ▼
FreeCAD Addon (Workbench)            ← freecad_addon/
    │ Queue → GUI Thread (QTimer)
    ▼
FreeCAD GUI (Live Updates!)
```

## Installation

### 1. FreeCAD Addon installieren

Kopiere den `freecad_addon` Ordner nach FreeCAD's Mod-Verzeichnis:

```bat
:: Windows (CMD)
xcopy /E /I freecad_addon "%APPDATA%\FreeCAD\Mod\FreecadAIBridge"
```

```bash
# Linux
cp -r freecad_addon ~/.FreeCAD/Mod/FreecadAIBridge

# macOS
cp -r freecad_addon ~/Library/Preferences/FreeCAD/Mod/FreecadAIBridge
```

### 2. MCP Server installieren

Im geklonten Root-Verzeichnis des Repos:

```bash
# Virtuelle Umgebung erstellen und aktivieren
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# Abhängigkeiten installieren
pip install -e .
```

### 3. Claude Desktop konfigurieren

Füge in `claude_desktop_config.json` hinzu (siehe `claude_desktop_config.example.json`):

Die Datei befindet sich unter:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "freecad": {
      "command": "python",
      "args": ["-m", "freecad_mcp.server"],
      "env": {
        "PYTHONPATH": "C:\\Users\\<DeinName>\\FreeCad_MCP_Server\\src"
      }
    }
  }
}
```

> **Hinweis:** Passe den `PYTHONPATH` auf den absoluten Pfad zum `src`-Verzeichnis deines geklonten Repos an. Wenn du eine virtuelle Umgebung nutzt, trage statt `python` den vollen Pfad zur Python-Binary ein (z.B. `C:\\Users\\<DeinName>\\FreeCad_MCP_Server\\.venv\\Scripts\\python.exe`).

### 4. VS Code konfigurieren

Die `.vscode/mcp.json` ist bereits im Projekt enthalten — beim Öffnen des Repo-Ordners in VS Code wird der MCP-Server automatisch erkannt. Der `PYTHONPATH` zeigt relativ auf `src/` im Repo.

## Verwendung

1. **FreeCAD starten** — Das Addon startet automatisch den RPC-Server auf Port 9875
2. **Claude verwenden** — Die MCP Tools sind automatisch verfügbar
3. **Erstes Tool aufrufen**: `connect` um die Verbindung herzustellen

### Beispiel-Workflow

```
User: "Erstelle einen Würfel 20x20x20mm mit 2mm Fillet auf allen Kanten"

Claude ruft auf:
1. connect()
2. create_document("MyPart")
3. partdesign_body("Body")
4. create_sketch("Sketch", plane="XY", body_name="Body")
5. sketch_add_rectangle("Sketch", 0, 0, 20, 20)
6. partdesign_pad("Sketch", length=20)
7. partdesign_fillet("Pad", edges=["Edge1","Edge2",...,"Edge12"], radius=2)
8. screenshot(view="isometric")
```

## Verfügbare Tools (84)

### Verbindung & Dokumente (8)
- `connect`, `get_status`
- `create_document`, `open_document`, `save_document`, `close_document`
- `list_objects`, `inspect_object`, `delete_object`

### Sketcher Geometrie (11)
- `create_sketch`
- `sketch_add_line`, `sketch_add_rectangle`, `sketch_add_circle`
- `sketch_add_arc`, `sketch_add_ellipse`, `sketch_add_bspline`
- `sketch_add_point`, `sketch_add_polygon`, `sketch_add_slot`
- `sketch_info`

### Sketcher Constraints (15) ⭐
- `sketch_constrain_coincident`, `sketch_constrain_tangent`
- `sketch_constrain_perpendicular`, `sketch_constrain_parallel`
- `sketch_constrain_equal`, `sketch_constrain_symmetric`
- `sketch_constrain_horizontal`, `sketch_constrain_vertical`
- `sketch_constrain_lock`, `sketch_constrain_block`
- `sketch_constrain_distance`, `sketch_constrain_distance_x`, `sketch_constrain_distance_y`
- `sketch_constrain_angle`, `sketch_constrain_radius`

### PartDesign Features (14)
- `partdesign_body`, `partdesign_pad`, `partdesign_pocket`
- `partdesign_revolution`, `partdesign_groove`
- `partdesign_loft`, `partdesign_sweep`
- `partdesign_hole`
- `partdesign_fillet`, `partdesign_chamfer`
- `partdesign_thickness`, `partdesign_draft`
- `partdesign_linear_pattern`, `partdesign_polar_pattern`, `partdesign_mirrored`

### Part Primitives & Boolean (8)
- `part_box`, `part_cylinder`, `part_sphere`, `part_cone`, `part_torus`
- `boolean_fuse`, `boolean_cut`, `boolean_common`

### Transform (5)
- `set_placement`, `move_object`, `rotate_object`, `scale_object`, `mirror_object`

### View & Visualisierung (6)
- `screenshot`, `set_view`, `fit_view`
- `set_visibility`, `set_color`, `set_transparency`

### Export/Import (4)
- `export_step`, `export_stl`, `import_step`, `import_stl`

### Utilities (4)
- `measure`, `undo`, `redo`, `execute_python`

## Konfiguration

Das Addon kann über FreeCAD-Preferences konfiguriert werden:

- **Port**: Standard 9875 (änderbar in `User parameter:BaseApp/Preferences/Mod/FreecadAIBridge`)
- **Host**: Standard 127.0.0.1 (nur lokal)
- **AutoStart**: Standard True

## Sicherheit

- Der RPC-Server lauscht nur auf localhost (127.0.0.1)
- Gefährliche Befehle (`os.system`, `subprocess`, etc.) werden geblockt
- `execute_python` ist der einzige Weg für beliebigen Code

## Bekannte Einschränkungen

- FreeCAD muss laufen (kein headless Mode für GUI-Updates)
- Topology Naming Problem: Edge/Face-Namen können sich nach Recompute ändern
- Thread-Safety wird durch Queue-Pattern sichergestellt (kein direkter Zugriff)
- Kein FEM-Support in v1 (erweiterbar)
- Kein Assembly-Workbench Support (zu experimentell)

## GitHub Copilot verwenden

Das Projekt lässt sich auch direkt mit **GitHub Copilot** (VS Code) nutzen. Die `.vscode/mcp.json` ist bereits im Repo enthalten und registriert den FreeCAD-MCP-Server automatisch.

### Voraussetzungen

- VS Code mit der Erweiterung **GitHub Copilot** (≥ v1.99) oder **GitHub Copilot Chat**
- MCP-Unterstützung ist in VS Code ab Version 1.99 integriert (Agent Mode)

### Einrichtung

1. Repo in VS Code öffnen
2. Virtualenv aktivieren und `pip install -e .` ausführen (siehe [Installation](#installation))
3. FreeCAD starten (Addon muss geladen sein, RPC-Server auf Port 9875)
4. In VS Code den **Copilot Chat** öffnen und in den **Agent Mode** wechseln (Dropdown oben im Chat-Fenster → „Agent")
5. Die FreeCAD-Tools erscheinen automatisch — einfach loslegen:

```
@workspace Erstelle in FreeCAD einen Zylinder mit Durchmesser 30mm und Höhe 50mm
```

> **Hinweis:** `mcp.json` setzt `PYTHONPATH` automatisch auf `${workspaceFolder}/src`, es ist kein manueller Eintrag nötig.

## Lizenz

MIT License — Copyright (c) 2026 JakobThiessen

Siehe [LICENSE](LICENSE) für den vollständigen Lizenztext.
