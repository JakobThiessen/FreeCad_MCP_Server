"""Owned document transactions; files and document lifecycle are excluded."""

from contextlib import contextmanager

from freecad_ai_bridge.contracts import BridgeError


@contextmanager
def document_transaction(doc, label, owned=False, recompute=True):
    if owned:
        yield
        return
    import FreeCAD

    if doc.HasPendingTransaction or FreeCAD.getActiveTransaction():
        raise BridgeError("transaction_conflict", "Document has an open transaction owned by another caller",
                          [{"document": doc.Name}])
    visibility = {obj.Name: obj.ViewObject.Visibility for obj in doc.Objects if obj.ViewObject}
    doc.UndoMode = 1
    doc.openTransaction(label)
    application_transaction = FreeCAD.getActiveTransaction()

    def close_application_transaction(abort):
        if application_transaction and FreeCAD.getActiveTransaction() == application_transaction:
            FreeCAD.closeActiveTransaction(abort, application_transaction[1])

    try:
        yield
        if recompute:
            doc.recompute()
        doc.commitTransaction()
        close_application_transaction(False)
    except Exception as error:
        try:
            for name, visible in visibility.items():
                obj = doc.getObject(name)
                if obj and obj.ViewObject and obj.ViewObject.Visibility != visible:
                    obj.ViewObject.Visibility = visible
            doc.abortTransaction()
            close_application_transaction(True)
            doc.recompute()
            if doc.HasPendingTransaction:
                doc.abortTransaction()
            error.bridge_state = "rolled_back"
        except Exception as rollback_error:
            error.bridge_state = "unknown"
            error.rollback_error = str(rollback_error)
        raise
