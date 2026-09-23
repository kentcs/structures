import builtins
import io
import re
from contextlib import redirect_stdout
from unittest.mock import patch

import parser
import tokenizer


def global_environment(environment):
    # The runner uses one dictionary. Tests can supply nested environments;
    # the two input/output variables still belong to the root dictionary.
    while "$PARENT" in environment:
        environment = environment["$PARENT"]
    return environment


def evaluate(ast, environment):
    if ast["tag"] == "boolean":
        return ast["value"]

    if ast["tag"] == "number":
        return ast["value"]

    # ===== CHAPTER 3: strings are values =====
    if ast["tag"] == "string":
        return ast["value"]

    if ast["tag"] == "identifier":
        identifier = ast["value"]
        env = environment
        while True:
            if identifier in env:
                return env[identifier]
            if "$PARENT" in env:
                env = env["$PARENT"]
                continue
            raise ValueError(f"Unknown identifier: {identifier}")

    # ===== CHAPTER 3: dedicated input expression =====
    if ast["tag"] == "input":
        prompt_ast = ast["prompt"]
        prompt = evaluate(prompt_ast, environment) if prompt_ast is not None else None
        if prompt_ast is not None and not isinstance(prompt, str):
            raise TypeError("input prompt must be a string")
        supplied = global_environment(environment).get("__input", "")
        if not isinstance(supplied, str):
            raise TypeError("__input must be a string")
        if supplied != "":
            # Clear before returning so a later input expression cannot reuse it.
            global_environment(environment)["__input"] = ""
            return supplied
        if prompt_ast is None:
            return builtins.input()
        return builtins.input(prompt)

    if ast["tag"] == "type_query":
        # Evaluate exactly once: type(input()) still consumes input. Report
        # Vertex types, not Python's distinction between int and float.
        value = evaluate(ast["expression"], environment)
        if type(value) is bool:
            return "boolean"
        if type(value) in (int, float):
            return "number"
        if type(value) is str:
            return "string"
        raise TypeError("type argument must be a Vertex value")

    if ast["tag"] == "string_conversion":
        value = evaluate(ast["expression"], environment)
        if type(value) is bool:
            return "true" if value else "false"
        if type(value) in (int, float, str):
            return str(value)
        raise TypeError("string argument must be a number, string, or boolean")

    if ast["tag"] == "number_conversion":
        value = evaluate(ast["expression"], environment)
        # Explicit conversion permits booleans as 1/0 without making them
        # implicit arithmetic operands. Existing numbers retain their type.
        if type(value) is bool:
            return 1 if value else 0
        if type(value) in (int, float):
            return value
        if type(value) is not str:
            raise TypeError("number argument must be a number, string, or boolean")
        text = value.strip()
        if not re.fullmatch(r"[+-]?(?:\d*\.\d+|\d+\.\d*|\d+)", text):
            raise ValueError(f"Invalid number: {value!r}")
        return float(text) if "." in text else int(text)

    if ast["tag"] == "boolean_conversion":
        value = evaluate(ast["expression"], environment)
        if type(value) is bool:
            return value
        if type(value) in (int, float):
            return value != 0
        if type(value) is str:
            # Do not use Python's bool(text): even "false" would become true.
            text = value.strip().lower()
            if text in ("true", "false"):
                return text == "true"
            raise ValueError(f"Invalid boolean: {value!r}")
        raise TypeError("boolean argument must be a number, string, or boolean")

    if ast["tag"] == "assign":
        value = evaluate(ast["expression"], environment)
        target = ast["target"]
        if target["tag"] != "identifier":
            raise ValueError("Assignment requires an identifier destination")
        name = target["value"]
        destination = global_environment(environment) if name in ("__input", "__output") else environment
        destination[name] = value
        return None

    if ast["tag"] == "unary-":
        value = evaluate(ast["operand"], environment)
        if type(value) is bool:
            raise TypeError("Unary minus requires a number")
        return -value

    if ast["tag"] in ("==", "!=", "<", "<=", ">", ">="):
        # Comparisons evaluate both operands, left to right, before comparing.
        left = evaluate(ast["left"], environment)
        right = evaluate(ast["right"], environment)
        numeric = type(left) in (int, float) and type(right) in (int, float)
        if ast["tag"] in ("==", "!="):
            # Integers and floats share numeric equality. Other types must match:
            # true is not 1, and the string "1" is not the number 1.
            equal = (numeric or type(left) is type(right)) and left == right
            return equal if ast["tag"] == "==" else not equal
        if not numeric:
            # This chapter defines ordering for numbers only, not for strings
            # or booleans. Equality is available for all three value families.
            raise TypeError("Ordering comparisons require numbers")
        if ast["tag"] == "<":
            return left < right
        if ast["tag"] == "<=":
            return left <= right
        if ast["tag"] == ">":
            return left > right
        return left >= right

    # Python's operators deliberately provide the Chapter 3 behavior:
    # string + string concatenates, string * integer repeats, and integer *
    # string repeats in the opposite order. Numeric behavior is unchanged.
    if ast["tag"] in ("+", "-", "*", "/"):
        left = evaluate(ast["left"], environment)
        right = evaluate(ast["right"], environment)
        # Python treats bool as an integer; Vertex keeps truth values distinct.
        if type(left) is bool or type(right) is bool:
            raise TypeError("Arithmetic does not accept boolean operands")
        if ast["tag"] == "+":
            return left + right
        if ast["tag"] == "-":
            return left - right
        if ast["tag"] == "*":
            return left * right
        return left / right

    if ast["tag"] == "print":
        result = evaluate(ast["expression"], environment)
        # Use Vertex's lowercase boolean spellings instead of Python's True/False.
        # The terminal and __output must receive the same text.
        text = ("true" if result else "false") if type(result) is bool else str(result)
        print(text)
        global_environment(environment)["__output"] = text
        return None

    if ast["tag"] == "statement_list":
        for statement in ast["statements"]:
            evaluate(statement, environment)
        return None

    if ast["tag"] == "program":
        globals_ = global_environment(environment)
        globals_.setdefault("__input", "")
        globals_.setdefault("__output", "")
        evaluate(ast["statements"], environment)
        return None

    raise ValueError(f"Unknown AST node: {ast}")


def evaluate_source(source, environment=None):
    """Small test helper; the runner performs these same three stages."""
    if environment is None:
        environment = {}
    ast = parser.parse(tokenizer.tokenize(source))
    result = evaluate(ast, environment)
    return result, environment


def test_evaluate_numbers():
    print("test evaluate numbers")
    ast, rest = parser.parse_expression(tokenizer.tokenize("3*(4+5)"))
    assert rest[0]["tag"] is None
    assert evaluate(ast, {}) == 27

    ast, rest = parser.parse_expression(tokenizer.tokenize("-1.5+2"))
    assert rest[0]["tag"] is None
    assert evaluate(ast, {}) == 0.5


def test_evaluate_strings():
    # ===== CHAPTER 3 TESTS =====
    print("test evaluate strings")
    cases = [
        ('"dog" + "cat"', "dogcat"),
        ('"dog" * 2', "dogdog"),
        ('2 * "dog"', "dogdog"),
        ('("ha" * 3) + "!"', "hahaha!"),
    ]
    for source, expected in cases:
        ast, rest = parser.parse_expression(tokenizer.tokenize(source))
        assert rest[0]["tag"] is None
        assert evaluate(ast, {}) == expected


def test_evaluate_environments():
    print("test evaluate environments")
    result, environment = evaluate_source('name="Ada";greeting="Hello, "+name')
    assert result is None
    assert environment == {"name": "Ada", "greeting": "Hello, Ada", "__input": "", "__output": ""}


def test_evaluate_input():
    # ===== CHAPTER 3 TESTS =====
    print("test evaluate input")

    ast, rest = parser.parse_expression(tokenizer.tokenize("input()"))
    assert rest[0]["tag"] is None
    with patch("builtins.input", return_value="one line") as fake_input:
        assert evaluate(ast, {}) == "one line"
        fake_input.assert_called_once_with()

    ast, rest = parser.parse_expression(
        tokenizer.tokenize('input("Your " + "name? ")')
    )
    assert rest[0]["tag"] is None
    with patch("builtins.input", return_value="Ada") as fake_input:
        assert evaluate(ast, {}) == "Ada"
        fake_input.assert_called_once_with("Your name? ")

    ast, rest = parser.parse_expression(tokenizer.tokenize("input(42)"))
    assert rest[0]["tag"] is None
    with patch("builtins.input") as fake_input:
        try:
            evaluate(ast, {})
        except TypeError as error:
            assert str(error) == "input prompt must be a string"
        else:
            raise Exception("Expected TypeError for non-string input prompt")
        fake_input.assert_not_called()


def test_evaluate_print():
    # ===== CHAPTER 3 TEST: parser accepts only print(expression) =====
    print("test evaluate print")
    output = io.StringIO()
    with redirect_stdout(output):
        result, environment = evaluate_source('x="ha"*3;print(x)')
    assert result is None
    assert environment == {"x": "hahaha", "__input": "", "__output": "hahaha"}
    assert output.getvalue() == "hahaha\n"


def test_evaluate_chapter_3_program():
    # ===== CHAPTER 3 INTEGRATION TEST =====
    print("test evaluate Chapter 3 program")
    source = """
        name = input("What is your name? ");
        greeting = "Hello, " + name + "!";
        print(greeting);
        line = input();
        print("You entered: " + line)
    """

    output = io.StringIO()
    with patch("builtins.input", side_effect=["Ada", "testing"] ) as fake_input:
        with redirect_stdout(output):
            result, environment = evaluate_source(source)

    assert result is None
    assert environment == {
        "name": "Ada",
        "greeting": "Hello, Ada!",
        "line": "testing",
        "__input": "",
        "__output": "You entered: testing",
    }
    assert output.getvalue() == "Hello, Ada!\nYou entered: testing\n"
    assert fake_input.call_count == 2
    assert fake_input.call_args_list[0].args == ("What is your name? ",)
    assert fake_input.call_args_list[1].args == ()


if __name__ == "__main__":
    test_evaluate_numbers()
    test_evaluate_strings()
    test_evaluate_environments()
    test_evaluate_input()
    test_evaluate_print()
    test_evaluate_chapter_3_program()
    print("done.")
