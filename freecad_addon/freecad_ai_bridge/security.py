"""Security filter for commands executed via RPC.

Blocks potentially dangerous operations that could harm the system.
"""

BLOCKED_PATTERNS = [
    "os.system",
    "os.popen",
    "os.exec",
    "os.spawn",
    "os.remove",
    "os.unlink",
    "os.rmdir",
    "shutil.rmtree",
    "subprocess",
    "__import__('os')",
    "__import__('subprocess')",
    "importlib.import_module('os')",
    "importlib.import_module('subprocess')",
    "eval(",
    "compile(",
    "open(",  # Block file operations except through FreeCAD API
]

# Modules that are allowed for execute_function calls
ALLOWED_MODULES = [
    "freecad_ai_bridge.operations",
    "freecad_ai_bridge.sketcher_ops",
    "freecad_ai_bridge.partdesign_ops",
    "freecad_ai_bridge.part_ops",
    "freecad_ai_bridge.view_ops",
    "freecad_ai_bridge.export_ops",
]


def check_command(command: str) -> bool:
    """Return True if the command is allowed, False if blocked."""
    command_lower = command.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in command_lower:
            return False
    return True


def check_module(module: str) -> bool:
    """Return True if the module is in the allowed list."""
    return module in ALLOWED_MODULES
