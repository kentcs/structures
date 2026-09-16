import parser, tokenizer


def evaluate(ast, environment):
    if ast["tag"] == "number":
        return ast["value"]
    elif ast["tag"] == "identifier":
        identifier = ast["value"]
        env = environment
        while True:
            if identifier in env:
                return env[identifier]
            if "$PARENT" in env:
                env = env["$PARENT"]
                continue
            raise ValueError(f"Unknown identifier: {identifier}")
    elif ast["tag"] == "assign":
        value = evaluate(ast["expression"], environment)
        environment[ast["target"]] = value
        return None
    elif ast["tag"] == "unary-":
        return -evaluate(ast["operand"], environment)
    elif ast["tag"] == "+":
        return evaluate(ast["left"], environment) + evaluate(ast["right"], environment)
    elif ast["tag"] == "-":
        return evaluate(ast["left"], environment) - evaluate(ast["right"], environment)
    elif ast["tag"] == "*":
        return evaluate(ast["left"], environment) * evaluate(ast["right"], environment)
    elif ast["tag"] == "/":
        return evaluate(ast["left"], environment) / evaluate(ast["right"], environment)
    elif ast["tag"] == "print":
        result = evaluate(ast["expression"], environment)
        print(result)
        return None
    elif ast["tag"] == "statement_list":
        for statement in ast["statements"]:
            evaluate(statement, environment)
        return None
    elif ast["tag"] == "program":
        evaluate(ast["statements"], environment)
        return None
    else:
        raise ValueError(f"Unknown AST node: {ast}")


def test_evaluate():
    print("test evaluate()")
    ast = {"tag": "number", "value": 3}
    assert evaluate(ast, {}) == 3
    ast = {
        "tag": "+",
        "left": {"tag": "number", "value": 3},
        "right": {"tag": "number", "value": 4},
    }
    assert evaluate(ast, {}) == 7
    ast = {
        "tag": "*",
        "left": {
            "tag": "+",
            "left": {"tag": "number", "value": 3},
            "right": {"tag": "number", "value": 4},
        },
        "right": {"tag": "number", "value": 5},
    }
    assert evaluate(ast, {}) == 35
    tokens = tokenizer.tokenize("3*(4+5)")
    ast, tokens = parser.parse_expression(tokens)
    assert evaluate(ast, {}) == 27
    tokens = tokenizer.tokenize("-1.5+2")
    ast, tokens = parser.parse_expression(tokens)
    assert evaluate(ast, {}) == 0.5


def test_evaluate_environments():
    print("test evaluate() with environments")
    ast = {"tag": "identifier", "value": "x"}
    assert evaluate(ast, {"x": 3}) == 3
    tokens = tokenizer.tokenize("3*(x+5)")
    ast, tokens = parser.parse_expression(tokens)
    environment = {"x": 4}
    assert evaluate(ast, environment) == 27
    try:
        evaluate(ast, {})
    except ValueError as error:
        assert str(error) == "Unknown identifier: x"
    else:
        raise Exception("Expected ValueError for undefined identifier")
    tokens = tokenizer.tokenize("x*(z+y)")
    ast, tokens = parser.parse_expression(tokens)
    environment = {"$PARENT": {"z": 5}, "x": 4, "y": 3}
    assert evaluate(ast, environment) == 32
    tokens = tokenizer.tokenize("x*(z+y)")
    ast, tokens = parser.parse_expression(tokens)
    environment = {
        "$PARENT": {
            "$PARENT": {"z": 5},
        },
        "x": 4,
        "y": 3,
    }
    assert evaluate(ast, environment) == 32


def test_evaluate_assignments():
    tokens = tokenizer.tokenize("z=3*(x+5)")
    ast, tokens = parser.parse_statement(tokens)
    environment = {"x": 4}
    assert evaluate(ast, environment) == None
    print(environment)
    assert environment == {"x": 4, "z": 27}
    tokens = tokenizer.tokenize("z=-1.5")
    ast, tokens = parser.parse_statement(tokens)
    environment = {}
    assert evaluate(ast, environment) == None
    assert environment == {"z": -1.5}


def test_evaluate_program():
    print("test evaluate() program")
    tokens = tokenizer.tokenize("x=-2.5;print x")
    ast = parser.parse(tokens)
    environment = {}
    assert evaluate(ast, environment) == None
    assert environment == {"x": -2.5}


if __name__ == "__main__":
    test_evaluate()
    test_evaluate_environments()
    test_evaluate_assignments()
    test_evaluate_program()
    print("done.")
