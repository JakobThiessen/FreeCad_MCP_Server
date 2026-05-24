"""FreeCAD AI Bridge - GUI initialization.

This file is executed when FreeCAD loads the addon with GUI available.
"""

import os
import sys
import FreeCAD

# Ensure addon directory is in sys.path
# __file__ is not defined in FreeCAD addon loading, so use getUserAppDataDir
_addon_dir = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "FreecadAIBridge")
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
