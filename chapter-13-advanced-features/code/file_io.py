"""Small text and JSON file wrappers for the native I/O library."""
import json
import math
from pathlib import Path


def require_path(path):
    if type(path) is not str:
        raise TypeError("File path must be a string")
    return Path(path)


def read(path):
    return require_path(path).read_bytes().decode("utf-8")


def write(path, text):
    target = require_path(path)
    if type(text) is not str:
        raise TypeError("File contents must be a string")
    target.write_bytes(text.encode("utf-8"))
    return None


def reject_constant(value):
    raise ValueError(f"Invalid JSON number: {value}")


def read_json(path):
    value = json.loads(read(path), parse_constant=reject_constant)
    json_value(value)
    return value


def json_value(value, ancestors=None):
    # Import lazily: evaluator imports the native registry during startup.
    from evaluator import is_function, is_object
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("JSON does not support nonfinite numbers")
        return value
    if is_function(value):
        raise TypeError("JSON does not support functions")
    if type(value) is not list and not is_object(value):
        raise TypeError("JSON requires language data values")
    if ancestors is None:
        ancestors = set()
    if id(value) in ancestors:
        raise ValueError("JSON does not support cyclic data")
    ancestors.add(id(value))
    try:
        if type(value) is list:
            return [json_value(item, ancestors) for item in value]
        if any(type(key) is not str for key in value):
            raise TypeError("JSON object keys must be strings")
        return {key: json_value(item, ancestors) for key, item in value.items()}
    finally:
        ancestors.remove(id(value))


def write_json(path, value):
    target = require_path(path)
    # Complete conversion, serialization, and encoding before opening the file.
    text = json.dumps(json_value(value), ensure_ascii=False, allow_nan=False,
                      indent=2, sort_keys=True) + "\n"
    data = text.encode("utf-8")
    target.write_bytes(data)
    return None
