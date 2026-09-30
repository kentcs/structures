# parser.py

from tokenizer import tokenize


# EBNF
#
#   program ::= statement_list
#   statement_list ::= { ";" } statement { ";" { ";" } statement } { ";" }
#   statement ::= assignment_statement | print_statement | exit_expression
#               | assert_statement | if_statement
#   assert_statement ::= "assert" expression "," <string>
#   assignment_statement ::= <identifier> "=" expression
#
#   ===== CHAPTER 3: print now requires parentheses =====
#   print_statement ::= "print" "(" expression ")"
#
#   ===== CHAPTER 7: conditionals and statement blocks =====
#   if_statement ::= "if" "(" expression ")" block [ "else" block ]
#   block ::= "{" [ statement_list ] { ";" } "}"
#   A bare statement is never a valid if/else body. An else that itself
#   branches must write its own braces around a nested if_statement: this
#   grammar has no "else if" shortcut.
#
#   expression ::= logic_or
#   logic_or ::= logic_and { "or" logic_and }
#   logic_and ::= logic_not { "and" logic_not }
#   logic_not ::= "not" logic_not | comparison
#   comparison ::= arithmetic_expression [ compare_op arithmetic_expression ]
#   compare_op ::= "==" | "!=" | "<" | "<=" | ">" | ">="
#   arithmetic_expression ::= term { ("+" | "-") term }
#   term ::= unary { ("*" | "/") unary }
#   unary ::= "-" unary | factor
#
#   ===== CHAPTER 3: strings and input are expression forms =====
#   factor ::= <number> | <string> | <identifier> | "true" | "false" | input_expression
#          | number_expression | string_expression | boolean_expression
#          | type_expression | exit_expression | "(" expression ")"
#   exit_expression ::= "exit" "(" [ expression ] ")"
#   input_expression ::= "input" "(" [ expression ] ")"
#   number_expression ::= "number" "(" expression ")"
#   string_expression ::= "string" "(" expression ")"
#   boolean_expression ::= "boolean" "(" expression ")"
#   type_expression ::= "type" "(" expression ")"
#
# input has function-shaped syntax, but this chapter does not implement
# general function calls, parameters, or function values.


def describe(token):
    # Report a token the way it appears in Vertex source, not as a dictionary.
    # Conversion keywords are tagged by operation, so restore their spelling.
    position = f"at line {token['line']}, column {token['column']}"
    if token["tag"] is None:
        return f"end of input {position}"
    spellings = {"number_conversion": "number", "string_conversion": "string",
                 "boolean_conversion": "boolean", "type_query": "type"}
    if token["tag"] == "string":
        text = '"' + token["value"] + '"'
    elif token["tag"] in ("number", "identifier"):
        text = str(token["value"])
    else:
        text = spellings.get(token["tag"], token["tag"])
    return f"'{text}' {position}"


def require(tokens, tag, message):
    if tokens[0]["tag"] != tag:
        raise SyntaxError(f"{message}, got {describe(tokens[0])}")
    return tokens[1:]


def parse_input_expression(tokens):
    # ===== CHAPTER 3 =====
    # input_expression ::= "input" "(" [ expression ] ")"
    tokens = require(tokens, "input", "Expected 'input'")
    tokens = require(tokens, "(", "Expected '(' after 'input'")

    if tokens[0]["tag"] == ")":
        return {"tag": "input", "prompt": None}, tokens[1:]

    prompt, tokens = parse_expression(tokens)
    tokens = require(tokens, ")", "Expected ')' after input prompt")
    return {"tag": "input", "prompt": prompt}, tokens


def parse_factor(tokens):
    token = tokens[0]
    if token["tag"] == "exit":
        return parse_exit_expression(tokens)
    # Both keywords become the same kind of literal node, with different values.
    if token["tag"] in ("true", "false"):
        return {"tag": "boolean", "value": token["tag"] == "true"}, tokens[1:]
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

    # All four forms take one expression. The AST retains the operation tag;
    # checking the argument's runtime type belongs to the evaluator.
    operations = {"number_conversion": "number", "string_conversion": "string",
                  "boolean_conversion": "boolean", "type_query": "type"}
    if token["tag"] in operations:
        name = operations[token["tag"]]
        tokens = require(tokens[1:], "(", f"Expected '(' after '{name}'")
        expression, tokens = parse_expression(tokens)
        tokens = require(tokens, ")", f"Expected ')' after {name} argument")
        return {"tag": token["tag"], "expression": expression}, tokens

    if token["tag"] == "(":
        # Parentheses restart at the lowest-precedence rule, allowing a complete
        # logical expression wherever a factor is expected.
        node, tokens = parse_expression(tokens[1:])
        tokens = require(tokens, ")", "Expected ')'")
        return node, tokens

    raise SyntaxError(f"Expected factor, got {describe(token)}")


def parse_unary(tokens):
    """unary ::= "-" unary | factor"""
    if tokens[0]["tag"] == "-":
        operand, tokens = parse_unary(tokens[1:])
        return {"tag": "unary-", "operand": operand}, tokens
    return parse_factor(tokens)


def parse_term(tokens):
    """term ::= unary { ("*" | "/") unary }"""
    left, tokens = parse_unary(tokens)
    while tokens[0]["tag"] in ["*", "/"]:
        operator = tokens[0]["tag"]
        right, tokens = parse_unary(tokens[1:])
        left = {"tag": operator, "left": left, "right": right}
    return left, tokens


def parse_arithmetic_expression(tokens):
    """arithmetic_expression ::= term { ("+" | "-") term }"""
    left, tokens = parse_term(tokens)
    while tokens[0]["tag"] in ["+", "-"]:
        operator = tokens[0]["tag"]
        right, tokens = parse_term(tokens[1:])
        left = {"tag": operator, "left": left, "right": right}
    return left, tokens


def parse_comparison(tokens):
    """comparison ::= arithmetic_expression [ compare_op arithmetic_expression ]"""
    # Arithmetic binds more tightly than comparisons: 1 + 2 < 4 compares 3 to 4.
    left, tokens = parse_arithmetic_expression(tokens)
    # One optional operator, not a loop: unparenthesized comparison chains are
    # deliberately outside this grammar. The unused token will cause an error.
    if tokens[0]["tag"] in ("==", "!=", "<", "<=", ">", ">="):
        operator = tokens[0]["tag"]
        right, tokens = parse_arithmetic_expression(tokens[1:])
        return {"tag": operator, "left": left, "right": right}, tokens
    return left, tokens


def parse_logic_not(tokens):
    # Recursive negation accepts "not not x" and "!!x". Falling through to
    # comparison makes "not x == y" mean "not (x == y)".
    if tokens[0]["tag"] == "not":
        operand, tokens = parse_logic_not(tokens[1:])
        return {"tag": "not", "operand": operand}, tokens
    return parse_comparison(tokens)


def parse_logic_and(tokens):
    # Each operand comes from the next tighter precedence level. The loop
    # constructs a left-associated tree without evaluating either operand.
    left, tokens = parse_logic_not(tokens)
    while tokens[0]["tag"] == "and":
        right, tokens = parse_logic_not(tokens[1:])
        left = {"tag": "and", "left": left, "right": right}
    return left, tokens


def parse_logic_or(tokens):
    # Parsing an entire conjunction first makes "and" bind more tightly than "or".
    left, tokens = parse_logic_and(tokens)
    while tokens[0]["tag"] == "or":
        right, tokens = parse_logic_and(tokens[1:])
        left = {"tag": "or", "left": left, "right": right}
    return left, tokens


def parse_expression(tokens):
    # Every expression context enters through the lowest-precedence rule.
    # Operator aliases were normalized by the tokenizer, not by these helpers.
    return parse_logic_or(tokens)


def parse_print_statement(tokens):
    # ===== CHAPTER 3: parentheses are required =====
    # print_statement ::= "print" "(" expression ")"
    tokens = require(tokens, "print", "Expected 'print'")
    tokens = require(tokens, "(", "Expected '(' after 'print'")
    expression, tokens = parse_expression(tokens)
    tokens = require(tokens, ")", "Expected ')' after print argument")
    return {"tag": "print", "expression": expression}, tokens


def parse_assignment_statement(tokens):
    # assignment_statement ::= <identifier> "=" expression
    if tokens[0]["tag"] != "identifier":
        raise SyntaxError(f"Expected identifier, got {describe(tokens[0])}")
    # The target names a destination. It must not read an existing binding;
    # assigning a name for the first time is valid.
    identifier = {"tag": "identifier", "value": tokens[0]["value"]}
    tokens = require(tokens[1:], "=", "Expected '=' for assignment")
    expression, tokens = parse_expression(tokens)
    return {
        "tag": "assign",
        "target": identifier,
        "expression": expression,
    }, tokens


def parse_statement(tokens):
    if tokens[0]["tag"] == "assert":
        return parse_assert_statement(tokens)
    if tokens[0]["tag"] == "exit":
        return parse_exit_expression(tokens)
    if tokens[0]["tag"] == "print":
        return parse_print_statement(tokens)
    # ===== CHAPTER 7 =====
    if tokens[0]["tag"] == "if":
        return parse_if_statement(tokens)
    if tokens[0]["tag"] == "identifier":
        return parse_assignment_statement(tokens)
    raise SyntaxError(f"Expected statement, got {describe(tokens[0])}")


def parse_block(tokens):
    # ===== CHAPTER 7 =====
    # block ::= "{" [ statement_list ] { ";" } "}"
    # A block wraps a statement_list in braces, so running it does not differ
    # from running the top-level program's statement_list, including
    # accepting a trailing semicolon before the closing brace. Unlike the
    # top-level program, the statement_list itself is optional: "{}" is an
    # empty block, not an error. Extra semicolons are harmless even when
    # there are no statements. The top-level program is unchanged.
    tokens = require(tokens, "{", "Expected '{' to start a block")
    while tokens[0]["tag"] == ";":
        tokens = tokens[1:]
    if tokens[0]["tag"] == "}":
        return {"tag": "statement_list", "statements": []}, tokens[1:]
    statements, tokens = parse_statement_list(tokens)
    tokens = require(tokens, "}", "Expected '}' to close a block")
    return statements, tokens


def parse_if_statement(tokens):
    # ===== CHAPTER 7 =====
    # if_statement ::= "if" "(" expression ")" block [ "else" block ]
    # Both branches require braces, so there is no dangling-else ambiguity to
    # resolve: this function checks for "else" immediately after parsing its
    # own then-block, before returning. An "else" always belongs to whichever
    # "if" statement's then-block just closed.
    tokens = require(tokens, "if", "Expected 'if'")
    tokens = require(tokens, "(", "Expected '(' after 'if'")
    condition, tokens = parse_expression(tokens)
    tokens = require(tokens, ")", "Expected ')' after if condition")
    then_block, tokens = parse_block(tokens)
    else_block = None
    if tokens[0]["tag"] == "else":
        else_block, tokens = parse_block(tokens[1:])
    return {"tag": "if", "condition": condition, "then": then_block,
            "else": else_block}, tokens


def parse_assert_statement(tokens):
    # The required explanation is a string literal, not another computation.
    tokens = require(tokens, "assert", "Expected 'assert'")
    expression, tokens = parse_expression(tokens)
    tokens = require(tokens, ",", "Expected ',' and explanation string after assertion")
    if tokens[0]["tag"] != "string":
        raise SyntaxError(
            f"Expected explanation string after ',', got {describe(tokens[0])}")
    explanation = tokens[0]["value"]
    tokens = tokens[1:]
    return {"tag": "assert", "expression": expression,
            "explanation": explanation}, tokens


def parse_exit_expression(tokens):
    # A dedicated expression, also allowed as a standalone statement.
    # Nesting it in an operand makes status propagation observable.
    tokens = require(tokens, "exit", "Expected 'exit'")
    tokens = require(tokens, "(", "Expected '(' after 'exit'")
    if tokens[0]["tag"] == ")":
        return {"tag": "exit", "expression": None}, tokens[1:]
    expression, tokens = parse_expression(tokens)
    tokens = require(tokens, ")", "Expected ')' after exit argument")
    return {"tag": "exit", "expression": expression}, tokens


def parse_statement_list(tokens):
    # statement_list ::= { ";" } statement { ";" { ";" } statement } { ";" }
    statements = []

    while tokens[0]["tag"] == ";":
        tokens = tokens[1:]

    statement, tokens = parse_statement(tokens)
    statements.append(statement)

    while tokens[0]["tag"] == ";":
        while tokens[0]["tag"] == ";":
            tokens = tokens[1:]
        # ===== CHAPTER 7 =====
        # A trailing semicolon is allowed at the end of any statement_list,
        # not only at the true end of input: "}" ends a block the same way
        # None ends the program.
        if tokens[0]["tag"] in (None, "}"):
            break
        statement, tokens = parse_statement(tokens)
        statements.append(statement)

    return {"tag": "statement_list", "statements": statements}, tokens


def parse_program(tokens):
    statements, tokens = parse_statement_list(tokens)
    return {"tag": "program", "statements": statements}, tokens


def parse(tokens):
    ast, tokens = parse_program(tokens)
    # A valid prefix is not enough: reject missing separators and extra operators.
    if tokens[0]["tag"] is not None:
        raise SyntaxError(f"Unexpected token: {describe(tokens[0])}")
    return ast


def expect_syntax_error(source, text):
    try:
        parse(tokenize(source))
    except SyntaxError as error:
        assert text in str(error), str(error)
    else:
        raise Exception(f"Expected SyntaxError for {source!r}")


def test_error_messages_describe_tokens():
    print("test error messages describe tokens")
    expect_syntax_error("print(1", "got end of input at line 1, column 8")
    expect_syntax_error("x = 1; x", "got end of input at line 1, column 9")
    expect_syntax_error('x = number "1"', "got '\"1\"' at line 1, column 12")
    expect_syntax_error("x = )", "got ')' at line 1, column 5")
    expect_syntax_error("x = 1 y", "Unexpected token: 'y' at line 1, column 7")


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
        "target": {"tag": "identifier", "value": "greeting"},
        "expression": {"tag": "string", "value": "Hello"},
    }
    assert rest[0]["tag"] is None


def test_parse_block():
    # ===== CHAPTER 7 TESTS =====
    print("test parse_block()")
    ast, rest = parse_block(tokenize("{ x=1 }"))
    assert ast == {"tag": "statement_list",
                    "statements": [{"tag": "assign",
                                    "target": {"tag": "identifier", "value": "x"},
                                    "expression": {"tag": "number", "value": 1}}]}
    assert rest[0]["tag"] is None

    ast, rest = parse_block(tokenize("{ x=1; y=2 }"))
    assert [statement["tag"] for statement in ast["statements"]] == ["assign", "assign"]
    assert rest[0]["tag"] is None

    # A trailing semicolon before the closing brace is allowed, the same as
    # one before the end of the whole program.
    ast, rest = parse_block(tokenize("{ x=1; y=2; }"))
    assert [statement["tag"] for statement in ast["statements"]] == ["assign", "assign"]
    assert rest[0]["tag"] is None

    # Nesting: a block may contain another brace-delimited block via "if".
    ast, rest = parse_block(tokenize("{ if (true) { x=1 } }"))
    assert ast["statements"][0]["tag"] == "if"
    assert rest[0]["tag"] is None

    try:
        parse_block(tokenize("x=1"))
    except SyntaxError as error:
        assert "Expected '{'" in str(error)
    else:
        raise Exception("Expected SyntaxError for a block missing '{'")

    # A block's statement_list is optional: "{}" is empty, not an error.
    ast, rest = parse_block(tokenize("{ }"))
    assert ast == {"tag": "statement_list", "statements": []}
    assert rest[0]["tag"] is None

    for source in ("{ ; }", "{ ;;; }", "{ ; // comment\n ; }"):
        ast, rest = parse_block(tokenize(source))
        assert ast == {"tag": "statement_list", "statements": []}
        assert rest[0]["tag"] is None
    expect_syntax_error("if (true) { ;", "Expected statement")
    expect_syntax_error("if (true) { x=1", "Expected '}'")


def test_parse_if_statement():
    # ===== CHAPTER 7 TESTS =====
    print("test parse_if_statement()")
    ast, rest = parse_if_statement(tokenize("if (x) { y=1 }"))
    assert ast == {
        "tag": "if",
        "condition": {"tag": "identifier", "value": "x"},
        "then": {"tag": "statement_list",
                 "statements": [{"tag": "assign",
                                 "target": {"tag": "identifier", "value": "y"},
                                 "expression": {"tag": "number", "value": 1}}]},
        "else": None,
    }
    assert rest[0]["tag"] is None

    ast, rest = parse_if_statement(tokenize("if (x) { y=1 } else { y=2 }"))
    assert ast["then"]["statements"][0]["expression"]["value"] == 1
    assert ast["else"]["statements"][0]["expression"]["value"] == 2
    assert rest[0]["tag"] is None

    # An "else if" chain is written as an else-block containing a nested if.
    ast, rest = parse_if_statement(tokenize("if (x) { y=1 } else { if (z) { y=2 } }"))
    assert ast["else"]["statements"][0]["tag"] == "if"
    assert rest[0]["tag"] is None

    # A branch's statement_list is optional: an empty then or else is legal.
    ast, rest = parse_if_statement(tokenize("if (x) { }"))
    assert ast["then"] == {"tag": "statement_list", "statements": []}
    assert ast["else"] is None
    assert rest[0]["tag"] is None

    ast, rest = parse_if_statement(tokenize("if (x) { } else { }"))
    assert ast["then"] == {"tag": "statement_list", "statements": []}
    assert ast["else"] == {"tag": "statement_list", "statements": []}
    assert rest[0]["tag"] is None

    # Bodies must be braced; a bare statement is never a valid branch.
    expect_syntax_error("if (x) y=1", "Expected '{'")
    expect_syntax_error("if (x) { y=1 } else y=2", "Expected '{'")
    expect_syntax_error("if x { y=1 }", "Expected '('")
    expect_syntax_error("if (x { y=1 }", "Expected ')'")

    # An if statement needs the usual ";" before the next statement, the
    # same as any other statement; "else" must directly follow the
    # preceding "}" with no semicolon in between.
    ast = parse(tokenize("if (true) { x=1 }; y=2"))
    assert [statement["tag"] for statement in ast["statements"]["statements"]] == ["if", "assign"]
    expect_syntax_error("if (true) { x=1 } y=2", "Unexpected token")
    expect_syntax_error("if (true) { x=1 }; else { x=2 }", "Expected statement")


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
    test_parse_block()
    test_parse_if_statement()
    test_parse_statement_list()
    test_parse_program()
    test_error_messages_describe_tokens()
    print("done.")
