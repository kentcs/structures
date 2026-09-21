# parser.py

from tokenizer import tokenize


# EBNF
#
#   program = statement_list
#   statement_list = { ";" } statement { ";" { ";" } statement } { ";" }
#   statement = assignment_statement | print_statement
#   assignment_statement = <identifier> "=" expression
#
#   ===== CHAPTER 3: print now requires parentheses =====
#   print_statement = "print" "(" expression ")"
#
#   expression = term { ("+" | "-") term }
#   term = unary { ("*" | "/") unary }
#   unary = "-" unary | factor
#
#   ===== CHAPTER 3: strings and input are expression forms =====
#   factor = <number> | <string> | <identifier> | input_expression
#          | number_expression | string_expression | "(" expression ")"
#   input_expression = "input" "(" [ expression ] ")"
#   number_expression = "number" "(" expression ")"
#   string_expression = "string" "(" expression ")"
#
# input has function-shaped syntax, but this chapter does not implement
# general function calls, parameters, or function values.


def require(tokens, tag, message):
    if tokens[0]["tag"] != tag:
        raise SyntaxError(f"{message}, got {tokens[0]}")
    return tokens[1:]


def parse_input_expression(tokens):
    # ===== CHAPTER 3 =====
    # input_expression = "input" "(" [ expression ] ")"
    tokens = require(tokens, "input", "Expected 'input'")
    tokens = require(tokens, "(", "Expected '(' after 'input'")

    if tokens[0]["tag"] == ")":
        return {"tag": "input", "prompt": None}, tokens[1:]

    prompt, tokens = parse_expression(tokens)
    tokens = require(tokens, ")", "Expected ')' after input prompt")
    return {"tag": "input", "prompt": prompt}, tokens


def parse_factor(tokens):
    token = tokens[0]
    if token["tag"] == "number":
        return {"tag": "number", "value": token["value"]}, tokens[1:]

    # ===== CHAPTER 3: string expression =====
    if token["tag"] == "string":
        return {"tag": "string", "value": token["value"]}, tokens[1:]

    if token["tag"] == "identifier":
        return {"tag": "identifier", "value": token["value"]}, tokens[1:]

    # ===== CHAPTER 3: dedicated input expression =====
    if token["tag"] == "input":
        return parse_input_expression(tokens)

    if token["tag"] in ("number_conversion", "string_conversion"):
        name = "number" if token["tag"] == "number_conversion" else "string"
        tokens = require(tokens[1:], "(", f"Expected '(' after '{name}'")
        expression, tokens = parse_expression(tokens)
        tokens = require(tokens, ")", f"Expected ')' after {name} argument")
        return {"tag": token["tag"], "expression": expression}, tokens

    if token["tag"] == "(":
        node, tokens = parse_expression(tokens[1:])
        tokens = require(tokens, ")", "Expected ')'")
        return node, tokens

    raise SyntaxError(f"Expected factor, got {token}")


def parse_unary(tokens):
    """unary = "-" unary | factor"""
    if tokens[0]["tag"] == "-":
        operand, tokens = parse_unary(tokens[1:])
        return {"tag": "unary-", "operand": operand}, tokens
    return parse_factor(tokens)


def parse_term(tokens):
    """term = unary { ("*" | "/") unary }"""
    left, tokens = parse_unary(tokens)
    while tokens[0]["tag"] in ["*", "/"]:
        operator = tokens[0]["tag"]
        right, tokens = parse_unary(tokens[1:])
        left = {"tag": operator, "left": left, "right": right}
    return left, tokens


def parse_expression(tokens):
    """expression = term { ("+" | "-") term }"""
    left, tokens = parse_term(tokens)
    while tokens[0]["tag"] in ["+", "-"]:
        operator = tokens[0]["tag"]
        right, tokens = parse_term(tokens[1:])
        left = {"tag": operator, "left": left, "right": right}
    return left, tokens


def parse_print_statement(tokens):
    # ===== CHAPTER 3: parentheses are required =====
    # print_statement = "print" "(" expression ")"
    tokens = require(tokens, "print", "Expected 'print'")
    tokens = require(tokens, "(", "Expected '(' after 'print'")
    expression, tokens = parse_expression(tokens)
    tokens = require(tokens, ")", "Expected ')' after print argument")
    return {"tag": "print", "expression": expression}, tokens


def parse_assignment_statement(tokens):
    # assignment_statement = <identifier> "=" expression
    if tokens[0]["tag"] != "identifier":
        raise SyntaxError(f"Expected identifier, got {tokens[0]}")
    identifier = tokens[0]["value"]
    tokens = require(tokens[1:], "=", "Expected '=' for assignment")
    expression, tokens = parse_expression(tokens)
    return {
        "tag": "assign",
        "target": identifier,
        "expression": expression,
    }, tokens


def parse_statement(tokens):
    if tokens[0]["tag"] == "print":
        return parse_print_statement(tokens)
    if tokens[0]["tag"] == "identifier":
        return parse_assignment_statement(tokens)
    raise SyntaxError(f"Expected statement, got {tokens[0]}")


def parse_statement_list(tokens):
    # statement_list = { ";" } statement { ";" { ";" } statement } { ";" }
    statements = []

    while tokens[0]["tag"] == ";":
        tokens = tokens[1:]

    statement, tokens = parse_statement(tokens)
    statements.append(statement)

    while tokens[0]["tag"] == ";":
        while tokens[0]["tag"] == ";":
            tokens = tokens[1:]
        if tokens[0]["tag"] is None:
            break
        statement, tokens = parse_statement(tokens)
        statements.append(statement)

    return {"tag": "statement_list", "statements": statements}, tokens


def parse_program(tokens):
    statements, tokens = parse_statement_list(tokens)
    return {"tag": "program", "statements": statements}, tokens


def parse(tokens):
    ast, tokens = parse_program(tokens)
    if tokens[0]["tag"] is not None:
        raise SyntaxError(f"Unexpected token: {tokens[0]}")
    return ast


def expect_syntax_error(source, text):
    try:
        parse(tokenize(source))
    except SyntaxError as error:
        assert text in str(error), str(error)
    else:
        raise Exception(f"Expected SyntaxError for {source!r}")


def test_parse_factor():
    print("test parse_factor()")
    ast, rest = parse_factor(tokenize("3"))
    assert ast == {"tag": "number", "value": 3}
    assert rest[0]["tag"] is None

    ast, rest = parse_factor(tokenize("(3+4)"))
    assert ast == {
        "tag": "+",
        "left": {"tag": "number", "value": 3},
        "right": {"tag": "number", "value": 4},
    }
    assert rest[0]["tag"] is None


def test_parse_strings():
    # ===== CHAPTER 3 TESTS =====
    print("test parse strings")
    ast, rest = parse_expression(tokenize('"dog" * 2 + "!"'))
    assert ast == {
        "tag": "+",
        "left": {
            "tag": "*",
            "left": {"tag": "string", "value": "dog"},
            "right": {"tag": "number", "value": 2},
        },
        "right": {"tag": "string", "value": "!"},
    }
    assert rest[0]["tag"] is None


def test_parse_input_expression():
    # ===== CHAPTER 3 TESTS =====
    print("test parse_input_expression()")
    ast, rest = parse_input_expression(tokenize("input()"))
    assert ast == {"tag": "input", "prompt": None}
    assert rest[0]["tag"] is None

    ast, rest = parse_input_expression(tokenize('input("Name? ")'))
    assert ast == {
        "tag": "input",
        "prompt": {"tag": "string", "value": "Name? "},
    }
    assert rest[0]["tag"] is None

    ast, rest = parse_expression(tokenize('input("Name? ") + "!"'))
    assert ast["tag"] == "+"
    assert ast["left"]["tag"] == "input"
    assert rest[0]["tag"] is None

    expect_syntax_error("x=input", "Expected '('")
    expect_syntax_error('x=input("Name? "', "Expected ')'")


def test_parse_unary():
    print("test parse_unary()")
    ast, rest = parse_unary(tokenize("--3"))
    assert ast == {
        "tag": "unary-",
        "operand": {"tag": "unary-", "operand": {"tag": "number", "value": 3}},
    }
    assert rest[0]["tag"] is None


def test_parse_term_and_expression():
    print("test parse term and expression")
    ast, rest = parse_expression(tokenize("3*4+5-6"))
    assert ast == {
        "tag": "-",
        "left": {
            "tag": "+",
            "left": {
                "tag": "*",
                "left": {"tag": "number", "value": 3},
                "right": {"tag": "number", "value": 4},
            },
            "right": {"tag": "number", "value": 5},
        },
        "right": {"tag": "number", "value": 6},
    }
    assert rest[0]["tag"] is None


def test_parse_print_statement():
    # ===== CHAPTER 3 TESTS: only the parenthesized form is valid =====
    print("test parse_print_statement()")
    ast, rest = parse_print_statement(tokenize('print("hello")'))
    assert ast == {
        "tag": "print",
        "expression": {"tag": "string", "value": "hello"},
    }
    assert rest[0]["tag"] is None

    ast, rest = parse_print_statement(tokenize("print(1+1*3)"))
    assert ast["tag"] == "print"
    assert rest[0]["tag"] is None

    expect_syntax_error("print 1", "Expected '('")
    expect_syntax_error("print(1", "Expected ')'")


def test_parse_assignment_statement():
    print("test parse_assignment_statement()")
    ast, rest = parse_assignment_statement(tokenize('greeting="Hello"'))
    assert ast == {
        "tag": "assign",
        "target": "greeting",
        "expression": {"tag": "string", "value": "Hello"},
    }
    assert rest[0]["tag"] is None


def test_parse_statement_list():
    print("test parse_statement_list()")
    source = ';;;name=input("Name? ");greeting="Hello, "+name;print(greeting);;;'
    ast, rest = parse_statement_list(tokenize(source))
    assert [statement["tag"] for statement in ast["statements"]] == [
        "assign",
        "assign",
        "print",
    ]
    assert rest[0]["tag"] is None

    for source in ["", ";;;"]:
        expect_syntax_error(source, "Expected statement")


def test_parse_program():
    print("test parse program")
    ast = parse(tokenize('x="ha"*3;print(x)'))
    assert ast["tag"] == "program"
    assert len(ast["statements"]["statements"]) == 2

    # Adjacent statements still require a semicolon.
    expect_syntax_error('x="hello" print(x)', "Unexpected token")


if __name__ == "__main__":
    test_parse_factor()
    test_parse_strings()
    test_parse_input_expression()
    test_parse_unary()
    test_parse_term_and_expression()
    test_parse_print_statement()
    test_parse_assignment_statement()
    test_parse_statement_list()
    test_parse_program()
    print("done.")
