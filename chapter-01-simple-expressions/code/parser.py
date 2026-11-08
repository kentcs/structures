# parser.py

from tokenizer import tokenize
from pprint import pprint

# EBNF

#   expression ::= term { ("+" | "-") term }
#   term ::= unary { ("*" | "/") unary }
#   unary ::= "-" unary | factor
#   factor ::= <number> | "(" expression ")"


def parse_factor(tokens):
    """factor ::= <number>"""
    token = tokens[0]
    if token["tag"] == "number":
        node = {"tag": "number", "value": token["value"]}
        return node, tokens[1:]
    if token["tag"] == "(":
        node, tokens = parse_expression(tokens[1:])
        if tokens[0]["tag"] != ")":
            raise SyntaxError(f"Expected ')', got {tokens[0]}")
        return node, tokens[1:]
    raise SyntaxError(f"Expected expression, got {tokens[0]}")


def test_parse_factor():
    """factor ::= <number>"""
    print("test parse_factor()")
    tokens = tokenize("3")
    ast, tokens = parse_factor(tokens)
    assert ast == {"tag": "number", "value": 3}
    assert tokens == [{"tag": None, "line": 1, "column": 2}]
    tokens = tokenize("(3+4)")
    ast, tokens = parse_factor(tokens)
    assert ast == {'tag': '+', 'left': {'tag': 'number', 'value': 3}, 'right': {'tag': 'number', 'value': 4}} 
    assert tokens == [{'tag': None, 'line': 1, 'column': 6}]



def parse_unary(tokens):
    """unary ::= "-" unary | factor"""
    if tokens[0]["tag"] == "-":
        operand, tokens = parse_unary(tokens[1:])
        return {"tag": "unary-", "operand": operand}, tokens
    return parse_factor(tokens)


def test_parse_unary():
    """unary ::= "-" unary | factor"""
    print("test parse_unary()")
    tokens = tokenize("-3")
    ast, tokens = parse_unary(tokens)
    assert ast == {"tag": "unary-", "operand": {"tag": "number", "value": 3}}
    assert tokens == [{"tag": None, "line": 1, "column": 3}]
    tokens = tokenize("--3")
    ast, tokens = parse_unary(tokens)
    assert ast == {
        "tag": "unary-",
        "operand": {"tag": "unary-", "operand": {"tag": "number", "value": 3}},
    }
    assert tokens == [{"tag": None, "line": 1, "column": 4}]
    tokens = tokenize("-(3+4)")
    ast, tokens = parse_unary(tokens)
    assert ast == {
        "tag": "unary-",
        "operand": {
            "tag": "+",
            "left": {"tag": "number", "value": 3},
            "right": {"tag": "number", "value": 4},
        },
    }
    assert tokens == [{"tag": None, "line": 1, "column": 7}]


def parse_term(tokens):
    """term ::= unary { ("*" | "/") unary }"""
    left, tokens = parse_unary(tokens)
    while tokens[0]["tag"] in ["*", "/"]:
        op = tokens[0]["tag"]
        right, tokens = parse_unary(tokens[1:])
        left = {"tag": op, "left": left, "right": right}
    return left, tokens


def test_parse_term():
    """term ::= unary { ("*" | "/") unary }"""
    print("test parse_term()")
    tokens = tokenize("3")
    ast, tokens = parse_term(tokens)
    assert ast == {"tag": "number", "value": 3}
    assert tokens == [{"tag": None, "line": 1, "column": 2}]
    tokens = tokenize("3*4")
    ast, tokens = parse_term(tokens)
    assert ast == {
        "left": {"tag": "number", "value": 3},
        "right": {"tag": "number", "value": 4},
        "tag": "*",
    }
    assert tokens == [{"column": 4, "line": 1, "tag": None}]
    tokens = tokenize("3/4")
    ast, tokens = parse_term(tokens)
    assert ast == {
        "left": {"tag": "number", "value": 3},
        "right": {"tag": "number", "value": 4},
        "tag": "/",
    }
    assert tokens == [{"column": 4, "line": 1, "tag": None}]
    tokens = tokenize("3/4*5")
    ast, tokens = parse_term(tokens)
    assert ast == {
        "left": {
            "left": {"tag": "number", "value": 3},
            "right": {"tag": "number", "value": 4},
            "tag": "/",
        },
        "right": {"tag": "number", "value": 5},
        "tag": "*",
    }
    assert tokens == [{"column": 6, "line": 1, "tag": None}]
    tokens = tokenize("3*-2")
    ast, tokens = parse_term(tokens)
    assert ast == {
        "left": {"tag": "number", "value": 3},
        "right": {"tag": "unary-", "operand": {"tag": "number", "value": 2}},
        "tag": "*",
    }
    assert tokens == [{"column": 5, "line": 1, "tag": None}]


def parse_expression(tokens):
    """expression ::= term { ("+" | "-") term }"""
    left, tokens = parse_term(tokens)
    while tokens[0]["tag"] in ["+", "-"]:
        op = tokens[0]["tag"]
        right, tokens = parse_term(tokens[1:])
        left = {"tag": op, "left": left, "right": right}
    return left, tokens


def test_parse_expression():
    """expression ::= term { ("+" | "-") term }"""
    print("test parse_expression()")
    tokens = tokenize("3")
    ast, tokens = parse_expression(tokens)
    assert ast == {"tag": "number", "value": 3}
    assert tokens == [{"tag": None, "line": 1, "column": 2}]
    tokens = tokenize("3*4+5-6")
    ast, tokens = parse_expression(tokens)
    assert ast == {
        "left": {
            "left": {
                "left": {"tag": "number", "value": 3},
                "right": {"tag": "number", "value": 4},
                "tag": "*",
            },
            "right": {"tag": "number", "value": 5},
            "tag": "+",
        },
        "right": {"tag": "number", "value": 6},
        "tag": "-",
    }
    assert tokens == [{"column": 8, "line": 1, "tag": None}]
    tokens = tokenize("-1.5+2")
    ast, tokens = parse_expression(tokens)
    assert ast == {
        "left": {"tag": "unary-", "operand": {"tag": "number", "value": 1.5}},
        "right": {"tag": "number", "value": 2},
        "tag": "+",
    }
    assert tokens == [{"column": 7, "line": 1, "tag": None}]

def parse(tokens):
    ast, tokens = parse_expression(tokens)
    if tokens[0]["tag"] is not None:
        raise SyntaxError(f"Unexpected token: {tokens[0]}")
    return ast

if __name__ == "__main__":
    test_parse_factor()
    test_parse_unary()
    test_parse_term()
    test_parse_expression()
    print("done.")
