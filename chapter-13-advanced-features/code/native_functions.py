"""Host implementations available through Vertex's native() constructor.

Registry names are the interface. Another host, such as Go, can supply the
same operations without changing Vertex source. Wrappers adapt host types
and results where necessary; no Python expressions are evaluated here.
"""
import math
from file_io import read, write, read_json, write_json


def require_number(value):
    if type(value) not in (int, float):
        raise TypeError("Expected a Vertex number")
    return value


def sqrt(value):
    return math.sqrt(require_number(value))


def hypot(a, b):
    return math.hypot(require_number(a), require_number(b))


NATIVE_FUNCTIONS = {
    "math.sqrt": sqrt,
    "math.hypot": hypot,
    "io.read": read,
    "io.write": write,
    "io.readJSON": read_json,
    "io.writeJSON": write_json,
}


def register_native(name, implementation):
    """Connect a registry name to a Python callable before loading Vertex code."""
    if type(name) is not str or not name:
        raise TypeError("Native name must be a nonempty string")
    if not callable(implementation):
        raise TypeError("Native implementation must be callable")
    NATIVE_FUNCTIONS[name] = implementation

