"""FreeCAD AI Bridge - GUI initialization.

This file is executed when FreeCAD loads the addon with GUI available.
"""

import os
import sys
import FreeCAD

# Ensure addon directory is in sys.path. __file__ is not defined in FreeCAD addon
# loading; FreeCAD has already put the module directory on sys.path (also for
# --module-path), so locate the package there before falling back to the user Mod folder.
def _locate_addon_dir():
    for entry in sys.path:
        if entry and os.path.isfile(os.path.join(entry, "freecad_ai_bridge", "__init__.py")):
            return entry
    return os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "FreecadAIBridge")


_addon_dir = _locate_addon_dir()
if _addon_dir not in sys.path:
    sys.path.insert(0, _addon_dir)


def setup_rpc_server():
    """Start the RPC server."""
    try:
        param = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/FreecadAIBridge")
        auto_start = param.GetBool("AutoStart", True)

        if auto_start:
            from freecad_ai_bridge.rpc_server import start_server

            host = param.GetString("Host", "127.0.0.1")
            port = param.GetInt("Port", 9875)
            start_server(host, port)
    except Exception as e:
        FreeCAD.Console.PrintError(f"FreecadAIBridge: Failed to start RPC server: {e}\n")
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc() + "\n")


# Start directly - the path is already set up and GUI is available
if FreeCAD.GuiUp:
    setup_rpc_server()
