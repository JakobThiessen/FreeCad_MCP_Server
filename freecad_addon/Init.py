"""FreeCAD AI Bridge - Base initialization (no GUI)."""

import os
import sys

import FreeCAD

# __file__ is not defined when FreeCAD executes this file. FreeCAD puts the module
# directory (user Mod folder entry or an additional --module-path) on sys.path before
# running it, so locate the package there. Fall back to the default user Mod folder.
# This keeps a copy loaded through --module-path from being shadowed by another
# installed copy in the user's Mod directory.
def _locate_addon_dir():
    for entry in sys.path:
        if entry and os.path.isfile(os.path.join(entry, "freecad_ai_bridge", "__init__.py")):
            return entry
    return os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "FreecadAIBridge")


addon_dir = _locate_addon_dir()
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

FreeCAD.Console.PrintMessage("FreecadAIBridge addon loaded.\n")
