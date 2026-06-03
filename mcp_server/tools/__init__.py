import os

def db_path():
    """Resolve path to houdiny.db regardless of where this file is called from."""
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "instance", "houdiny.db")
