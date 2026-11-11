"""Owned document transactions; files and document lifecycle are excluded."""

from contextlib import contextmanager

from freecad_ai_bridge.contracts import BridgeError

_DRAFT_WIRE_TOLERANCE = 1e-7


def draft_wire_snapshot(doc):
    """Placement/Start/End of native Draft wires/lines before undo, redo or abort restores their properties."""
    import FreeCAD

    return {obj.Name: (FreeCAD.Placement(obj.Placement), FreeCAD.Vector(obj.Start), FreeCAD.Vector(obj.End))
            for obj in doc.Objects
            if type(getattr(obj, "Proxy", None)).__module__ == "draftobjects.wire"
            and {"Points", "Start", "End"} <= set(obj.PropertiesList)}


def repair_draft_wire_endpoints(doc, placements):
    """Undo native Draft endpoint drift caused by unordered property restoration.

    Draft Wire.onChanged rewrites Points[0]/Points[-1] from the global Start/End using the Placement
    current at that moment. Undo/redo/abort restore properties in unspecified order, so an endpoint can
    be computed with the pre-restore Placement. Only that exact signature is repaired: Placement and the
    endpoint changed during the restore and the point equals the pre-restore Placement inverse. Returns Names.
    """
    import FreeCAD

    repaired = []
    for name, (before, start_before, end_before) in placements.items():
        obj = doc.getObject(name)
        if obj is None or not {"Points", "Start", "End"} <= set(obj.PropertiesList) or len(obj.Points) < 2:
            continue
        after = FreeCAD.Placement(obj.Placement)
        if after.isSame(before, _DRAFT_WIRE_TOLERANCE):
            continue
        points = list(obj.Points)
        changed = False
        for index, endpoint, previous in ((0, obj.Start, start_before), (-1, obj.End, end_before)):
            if endpoint.isEqual(previous, _DRAFT_WIRE_TOLERANCE):
                continue
            expected = after.inverse().multVec(endpoint)
            if (points[index].isEqual(before.inverse().multVec(endpoint), _DRAFT_WIRE_TOLERANCE)
                    and not points[index].isEqual(expected, _DRAFT_WIRE_TOLERANCE)):
                points[index] = expected
                changed = True
        if changed:
            obj.Points = points
            repaired.append(name)
    return repaired


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
            placements = draft_wire_snapshot(doc)
            doc.abortTransaction()
            close_application_transaction(True)
            repair_draft_wire_endpoints(doc, placements)
            doc.recompute()
            if doc.HasPendingTransaction:
                doc.abortTransaction()
            error.bridge_state = "rolled_back"
        except Exception as rollback_error:
            error.bridge_state = "unknown"
            error.rollback_error = str(rollback_error)
        raise
