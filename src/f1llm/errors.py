class SessionDataUnavailable(Exception):
    """Raised by a load_* boundary function when no data exists for the request."""
