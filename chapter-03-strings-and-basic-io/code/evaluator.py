import builtins
import io
import re
from contextlib import redirect_stdout
from unittest.mock import patch

import parser
import tokenizer


def global_environment(environment):
    while "$PARENT" in environment:
        environment = environment["$PARENT"]
    return environment


def evaluate(ast, environment):
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
            global_environment(environment)["__input"] = ""
            return supplied
        if prompt_ast is None:
            return builtins.input()
        return builtins.input(prompt)

    if ast["tag"] == "string_conversion":
        value = evaluate(ast["expression"], environment)
        if type(value) not in (int, float):
            raise TypeError("string argument must be a number")
        return str(value)

    if ast["tag"] == "number_conversion":
        value = evaluate(ast["expression"], environment)
        if not isinstance(value, str):
            raise TypeError("number argument must be a string")
        text = value.strip()
        if not re.fullmatch(r"[+-]?(?:\d*\.\d+|\d+\.\d*|\d+)", text):
            raise ValueError(f"Invalid number: {value!r}")
        return float(text) if "." in text else int(text)

    if ast["tag"] == "assign":
        value = evaluate(ast["expression"], environment)
        target = ast["target"]
        destination = global_environment(environment) if target in ("__input", "__output") else environment
        destination[target] = value
        return None

    if ast["tag"] == "unary-":
        return -evaluate(ast["operand"], environment)

    # Python's operators deliberately provide the Chapter 3 behavior:
    # string + string concatenates, string * integer repeats, and integer *
    # string repeats in the opposite order. Numeric behavior is unchanged.
    if ast["tag"] == "+":
        return evaluate(ast["left"], environment) + evaluate(ast["right"], environment)
    if ast["tag"] == "-":
        return evaluate(ast["left"], environment) - evaluate(ast["right"], environment)
    if ast["tag"] == "*":
        return evaluate(ast["left"], environment) * evaluate(ast["right"], environment)
    if ast["tag"] == "/":
        return evaluate(ast["left"], environment) / evaluate(ast["right"], environment)

    if ast["tag"] == "print":
        result = evaluate(ast["expression"], environment)
        text = str(result)
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
