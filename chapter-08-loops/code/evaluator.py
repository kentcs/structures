import builtins
import io
import re
import sys
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
    """Return (value, status); None means evaluation completed normally.

    A special status is propagated before any remaining computation or effect.
    Only the structure responsible for that status may consume it. For now,
    exit travels through the program to the runner, as in the old interpreter.

    The status check after each child evaluation is repeated on purpose: evaluate
    a child, and if its status is not None, return that pair before doing more.
    """
    if ast["tag"] == "assert":
        # An exit during the condition takes precedence over assertion handling.
        value, status = evaluate(ast["expression"], environment)
        if status is not None:
            return value, status
        if type(value) is not bool:
            raise TypeError("assert requires a boolean expression")
        if value:
            return None, None
        message = "Assertion failed: " + ast["explanation"]
        # Report here, then request ordinary program exit. No exception payload
        # needs to travel through the tree because Vertex has no catch mechanism.
        print(message, file=sys.stderr)
        return 1, "exit"

    if ast["tag"] == "exit":
        value = 0
        if ast["expression"] is not None:
            value, status = evaluate(ast["expression"], environment)
            if status is not None:
                return value, status
        if type(value) is not int:
            raise TypeError("exit code must be an integer")
        return value, "exit"

    if ast["tag"] == "boolean":
        return ast["value"], None

    if ast["tag"] == "not":
        # Do not let Python coerce numbers or strings to truth values for Vertex.
        value, status = evaluate(ast["operand"], environment)
        if status is not None:
            return value, status
        if type(value) is not bool:
            raise TypeError("not requires a boolean operand")
        return not value, None

    if ast["tag"] in ("and", "or"):
        # Evaluate and validate the left operand before considering the right.
        # An eager evaluation of both children would consume input even when
        # that input cannot affect the result.
        left, status = evaluate(ast["left"], environment)
        if status is not None:
            return left, status
        if type(left) is not bool:
            raise TypeError(f"{ast['tag']} requires boolean operands")
        # Do not evaluate the right side when the left already decides the result.
        if ast["tag"] == "and" and not left:
            return False, None
        if ast["tag"] == "or" and left:
            return True, None
        right, status = evaluate(ast["right"], environment)
        if status is not None:
            return right, status
        if type(right) is not bool:
            raise TypeError(f"{ast['tag']} requires boolean operands")
        # Only true-and-right and false-or-right reach here. In both cases the
        # validated right boolean is also the result of the whole expression.
        return right, None

    if ast["tag"] == "number":
        return ast["value"], None

    # ===== CHAPTER 3: strings are values =====
    if ast["tag"] == "string":
        return ast["value"], None

    if ast["tag"] == "identifier":
        identifier = ast["value"]
        env = environment
        while True:
            if identifier in env:
                return env[identifier], None
            if "$PARENT" in env:
                env = env["$PARENT"]
                continue
            raise ValueError(f"Unknown identifier: {identifier}")

    # ===== CHAPTER 3: dedicated input expression =====
    if ast["tag"] == "input":
        prompt_ast = ast["prompt"]
        prompt = None
        if prompt_ast is not None:
            prompt, status = evaluate(prompt_ast, environment)
            if status is not None:
                return prompt, status
        if prompt_ast is not None and not isinstance(prompt, str):
            raise TypeError("input prompt must be a string")
        supplied = global_environment(environment).get("__input", "")
        if not isinstance(supplied, str):
            raise TypeError("__input must be a string")
        if supplied != "":
            # Clear before returning so a later input expression cannot reuse it.
            global_environment(environment)["__input"] = ""
            return supplied, None
        if prompt_ast is None:
            return builtins.input(), None
        return builtins.input(prompt), None

    if ast["tag"] == "type_query":
        # Evaluate exactly once: type(input()) still consumes input. Report
        # Vertex types, not Python's distinction between int and float.
        value, status = evaluate(ast["expression"], environment)
        if status is not None:
            return value, status
        if type(value) is bool:
            return "boolean", None
        if type(value) in (int, float):
            return "number", None
        if type(value) is str:
            return "string", None
        raise TypeError("type argument must be a Vertex value")

    if ast["tag"] == "string_conversion":
        value, status = evaluate(ast["expression"], environment)
        if status is not None:
            return value, status
        if type(value) is bool:
            if value:
                return "true", None
            return "false", None
        if type(value) in (int, float, str):
            return str(value), None
        raise TypeError("string argument must be a number, string, or boolean")

    if ast["tag"] == "number_conversion":
        value, status = evaluate(ast["expression"], environment)
        if status is not None:
            return value, status
        # Explicit conversion permits booleans as 1/0 without making them
        # implicit arithmetic operands. Existing numbers retain their type.
        if type(value) is bool:
            if value:
                return 1, None
            return 0, None
        if type(value) in (int, float):
            return value, None
        if type(value) is not str:
            raise TypeError("number argument must be a number, string, or boolean")
        text = value.strip()
        if not re.fullmatch(r"[+-]?(?:\d*\.\d+|\d+\.\d*|\d+)", text):
            raise ValueError(f"Invalid number: {value!r}")
        if "." in text:
            return float(text), None
        return int(text), None

    if ast["tag"] == "boolean_conversion":
        value, status = evaluate(ast["expression"], environment)
        if status is not None:
            return value, status
        if type(value) is bool:
            return value, None
        if type(value) in (int, float):
            return value != 0, None
        if type(value) is str:
            # Do not use Python's bool(text): even "false" would become true.
            text = value.strip().lower()
            if text in ("true", "false"):
                return text == "true", None
            raise ValueError(f"Invalid boolean: {value!r}")
        raise TypeError("boolean argument must be a number, string, or boolean")

    if ast["tag"] == "assign":
        value, status = evaluate(ast["expression"], environment)
        if status is not None:
            return value, status
        target = ast["target"]
        if target["tag"] != "identifier":
            raise ValueError("Assignment requires an identifier destination")
        name = target["value"]
        destination = environment
        if name in ("__input", "__output"):
            destination = global_environment(environment)
        destination[name] = value
        return None, None

    if ast["tag"] == "unary-":
        value, status = evaluate(ast["operand"], environment)
        if status is not None:
            return value, status
        if type(value) is bool:
            raise TypeError("Unary minus requires a number")
        return -value, None

    if ast["tag"] in ("==", "!=", "<", "<=", ">", ">="):
        # Comparisons evaluate both operands, left to right. Unlike logical
        # operators they have no short-circuit case.
        left, status = evaluate(ast["left"], environment)
        if status is not None:
            return left, status
        right, status = evaluate(ast["right"], environment)
        if status is not None:
            return right, status
        numeric = type(left) in (int, float) and type(right) in (int, float)
        if ast["tag"] in ("==", "!="):
            # Integers and floats share numeric equality. Other types must match:
            # true is not 1, and the string "1" is not the number 1.
            equal = (numeric or type(left) is type(right)) and left == right
            if ast["tag"] == "==":
                return equal, None
            return not equal, None
        strings = type(left) is str and type(right) is str
        if not (numeric or strings):
            raise TypeError("Ordering comparisons require two numbers or two strings")
        # Python string ordering is lexicographic by Unicode code point:
        # the first unequal character decides; a matching shorter prefix wins.
        if ast["tag"] == "<":
            return left < right, None
        if ast["tag"] == "<=":
            return left <= right, None
        if ast["tag"] == ">":
            return left > right, None
        return left >= right, None

    # Python's operators deliberately provide the Chapter 3 behavior:
    # string + string concatenates, string * integer repeats, and integer *
    # string repeats in the opposite order. Numeric behavior is unchanged.
    if ast["tag"] in ("+", "-", "*", "/"):
        left, status = evaluate(ast["left"], environment)
        if status is not None:
            return left, status
        right, status = evaluate(ast["right"], environment)
        if status is not None:
            return right, status
        # Python treats bool as an integer; Vertex keeps truth values distinct.
        if type(left) is bool or type(right) is bool:
            raise TypeError("Arithmetic does not accept boolean operands")
        if ast["tag"] == "+":
            return left + right, None
        if ast["tag"] == "-":
            return left - right, None
        if ast["tag"] == "*":
            return left * right, None
        return left / right, None

    if ast["tag"] == "print":
        result, status = evaluate(ast["expression"], environment)
        if status is not None:
            return result, status
        # Use Vertex's lowercase boolean spellings instead of Python's True/False.
        # The terminal and __output must receive the same text.
        if type(result) is bool:
            if result:
                text = "true"
            else:
                text = "false"
        else:
            text = str(result)
        print(text)
        global_environment(environment)["__output"] = text
        return None, None

    if ast["tag"] == "statement_list":
        for statement in ast["statements"]:
            value, status = evaluate(statement, environment)
            if status is not None:
                return value, status
        return None, None

    # ===== CHAPTER 7: conditionals =====
    if ast["tag"] == "if":
        condition, status = evaluate(ast["condition"], environment)
        if status is not None:
            return condition, status
        if type(condition) is not bool:
            raise TypeError("if condition must be a boolean expression")
        # The branch not taken is never evaluated: it cannot read input,
        # exit, or fail an assertion. Both branches share this environment;
        # a block introduces no scope of its own.
        if condition:
            return evaluate(ast["then"], environment)
        if ast["else"] is not None:
            return evaluate(ast["else"], environment)
        return None, None

    # ===== CHAPTER 8: loops =====
    if ast["tag"] == "break":
        return None, "break"

    if ast["tag"] == "continue":
        return None, "continue"

    if ast["tag"] == "while":
        while True:
            condition, status = evaluate(ast["condition"], environment)
            if status is not None:
                return condition, status
            if type(condition) is not bool:
                raise TypeError("while condition must be a boolean expression")
            if not condition:
                return None, None
            value, status = evaluate(ast["body"], environment)
            if status == "break":
                return None, None
            if status is not None and status != "continue":
                # exit, a failed assertion, or anything else this loop does
                # not own: pass it outward without finishing the loop.
                return value, status
            # Normal completion and "continue" both return to the condition.

    if ast["tag"] == "program":
        globals_ = global_environment(environment)
        globals_.setdefault("__input", "")
        globals_.setdefault("__output", "")
        value, status = evaluate(ast["statements"], environment)
        if status is not None:
            return value, status
        return None, None

    raise ValueError(f"Unknown AST node: {ast}")


def evaluate_source(source, environment=None):
    """Return ((value, status), environment), retaining both result components."""
    if environment is None:
        environment = {}
    ast = parser.parse(tokenizer.tokenize(source))
    result = evaluate(ast, environment)
    return result, environment


def test_evaluate_numbers():
    print("test evaluate numbers")
    ast, rest = parser.parse_expression(tokenizer.tokenize("3*(4+5)"))
    assert rest[0]["tag"] is None
    assert evaluate(ast, {}) == (27, None)

    ast, rest = parser.parse_expression(tokenizer.tokenize("-1.5+2"))
    assert rest[0]["tag"] is None
    assert evaluate(ast, {}) == (0.5, None)


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
        assert evaluate(ast, {}) == (expected, None)


def test_evaluate_environments():
    print("test evaluate environments")
    result, environment = evaluate_source('name="Ada";greeting="Hello, "+name')
    assert result == (None, None)
    assert environment == {"name": "Ada", "greeting": "Hello, Ada", "__input": "", "__output": ""}


def test_evaluate_input():
    # ===== CHAPTER 3 TESTS =====
    print("test evaluate input")

    ast, rest = parser.parse_expression(tokenizer.tokenize("input()"))
    assert rest[0]["tag"] is None
    with patch("builtins.input", return_value="one line") as fake_input:
        assert evaluate(ast, {}) == ("one line", None)
        fake_input.assert_called_once_with()

    ast, rest = parser.parse_expression(
        tokenizer.tokenize('input("Your " + "name? ")')
    )
    assert rest[0]["tag"] is None
    with patch("builtins.input", return_value="Ada") as fake_input:
        assert evaluate(ast, {}) == ("Ada", None)
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
    assert result == (None, None)
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

    assert result == (None, None)
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


def test_evaluate_if():
    # ===== CHAPTER 7 TEST =====
    print("test evaluate if")
    result, environment = evaluate_source('if (true) { x=1 }')
    assert result == (None, None)
    assert environment["x"] == 1

    result, environment = evaluate_source('if (false) { x=1 }')
    assert result == (None, None)
    assert "x" not in environment

    result, environment = evaluate_source('if (false) { x=1 } else { x=2 }')
    assert environment["x"] == 2

    result, environment = evaluate_source('x=1; if (true) { }; x=2')
    assert result == (None, None)
    assert environment["x"] == 2


def test_evaluate_while():
    # ===== CHAPTER 8 TEST =====
    print("test evaluate while")
    result, environment = evaluate_source('i=0; while (i < 3) { i=i+1 }')
    assert result == (None, None)
    assert environment["i"] == 3

    # A false initial condition means the body never runs.
    result, environment = evaluate_source('i=0; while (false) { i=99 }')
    assert environment["i"] == 0

    # break stops the loop and completes normally.
    result, environment = evaluate_source(
        'i=0; while (true) { i=i+1; if (i == 3) { break } }')
    assert result == (None, None)
    assert environment["i"] == 3

    # continue skips the rest of the body and reevaluates the condition.
    result, environment = evaluate_source(
        'i=0; total=0; while (i < 5) { i=i+1; if (i == 3) { continue }; total=total+i }')
    assert environment["total"] == 12  # 1+2+4+5, 3 skipped

    # exit propagates outward instead of being consumed like break.
    result, environment = evaluate_source('while (true) { exit(7) }')
    assert result == (7, "exit")


if __name__ == "__main__":
    test_evaluate_numbers()
    test_evaluate_strings()
    test_evaluate_environments()
    test_evaluate_input()
    test_evaluate_print()
    test_evaluate_chapter_3_program()
    test_evaluate_if()
    test_evaluate_while()
    print("done.")
