from flask import jsonify


def ok(data=None, **kwargs):
    """Return a standardized success response: {"status": "ok", ...}"""
    payload = {"status": "ok"}
    if data is not None:
        payload.update(data if isinstance(data, dict) else {"data": data})
    payload.update(kwargs)
    return jsonify(payload)


def err(message, code=400, **kwargs):
    """Return a standardized error response: {"status": "error", "error": "..."}"""
    payload = {"status": "error", "error": message}
    payload.update(kwargs)
    return jsonify(payload), code
