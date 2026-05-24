"""FreeCAD AI Bridge - Base initialization (no GUI)."""

import os
import sys

import FreeCAD

# Add addon directory to sys.path so freecad_ai_bridge package is importable
# __file__ is not defined in FreeCAD addon loading, so use getUserAppDataDir
addon_dir = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "FreecadAIBridge")
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

FreeCAD.Console.PrintMessage("FreecadAIBridge addon loaded.\n")
