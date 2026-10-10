"""Interpret llmcall call exit codes without depending on the gateway implementation."""

_MEANINGS = {
    0: "delivered",
    1: "failed",
    2: "bad_request",
    3: "unsure",
    4: "delivered_unsettled",
}


def meaning(rc):
    """Unknown codes provide no evidence of delivery or definite failure."""
    return _MEANINGS.get(rc, "unknown")


def delivered(rc):
    """Delivery-class exits alone do not prove that the model answered."""
    return meaning(rc) in ("delivered", "delivered_unsettled")


def answered(rc, receipt):
    """Require a receipt: unsettled billing can accompany a failed outcome."""
    return (delivered(rc) and isinstance(receipt, dict)
            and receipt.get("outcome") == "answered"
            and isinstance(receipt.get("text"), str))
