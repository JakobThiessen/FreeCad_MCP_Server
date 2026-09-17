"""Versioned metadata and errors for structured bridge operations."""

CONTRACT_VERSION = "1.0"
BRIDGE_API_VERSION = "0.6.0"


class BridgeError(ValueError):
    """Expected failure with a stable code and explicit affected references."""

    def __init__(self, code, message, references=None):
        super().__init__(message)
        self.code = code
        self.references = references or []


def error_response(error):
    """Keep the legacy error string alongside structured failure metadata."""
    if isinstance(error, BridgeError):
        code = error.code
    elif isinstance(error, TimeoutError):
        code = "execution_timeout"
    elif isinstance(error, (ValueError, TypeError)):
        code = "invalid_arguments"
    else:
        code = "operation_failed"
    return {
        "error": str(error),
        "error_details": {
            "code": code,
            "message": str(error),
            "cause": type(error).__name__,
            "references": getattr(error, "references", []),
            "retryable": False,
            "state": getattr(error, "bridge_state", "unchanged" if isinstance(error, BridgeError) else "unknown"),
            "rollback_error": getattr(error, "rollback_error", None),
        },
    }