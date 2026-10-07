# parser.py

from tokenizer import tokenize


# EBNF
#
#   program ::= statement_list
#   statement_list ::= { ";" } statement { ";" { ";" } statement } { ";" }
#   statement ::= assignment_statement | print_statement | exit_expression
#               | assert_statement | if_statement | while_statement
#               | break_statement | continue_statement
#   assert_statement ::= "assert" expression "," <string>
#
#   ===== CHAPTER 9: indexed assignment targets =====
#   assignment_statement ::= <identifier> { index_suffix } "=" expression
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
#   ===== CHAPTER 8: loops =====
#   while_statement ::= "while" "(" expression ")" block
#   break_statement ::= "break"
#   continue_statement ::= "continue"
#   A loop body is a block, the same requirement as an if branch. break and
#   continue take no argument and are only meaningful inside a loop; nothing
#   in the grammar enforces that placement, so using either outside a loop
#   is caught later, at evaluation.
#
#   expression ::= logic_or
#   logic_or ::= logic_and { "or" logic_and }
#   logic_and ::= logic_not { "and" logic_not }
#   logic_not ::= "not" logic_not | comparison
#   comparison ::= arithmetic_expression [ compare_op arithmetic_expression ]
#   compare_op ::= "==" | "!=" | "<" | "<=" | ">" | ">="
#   arithmetic_expression ::= term { ("+" | "-") term }
#   term ::= unary { ("*" | "/") unary }
#
#   ===== CHAPTER 9: postfix indexing applies to any factor =====
#   unary ::= "-" unary | complex_expression
#   complex_expression ::= factor { index_suffix }
#   index_suffix ::= "[" expression "]"
#   An index_suffix chain produces "complex" nodes, not "index" nodes: a
#   later chapter's function calls are the same postfix shape with a
#   different suffix, and will extend this node instead of introducing a
#   parallel one. Indexing applies uniformly after any factor, not just an
#   identifier: a list literal, a parenthesized expression, even another
#   complex expression, which is what makes matrix[row][column] a chain of
#   two nodes rather than a special two-argument form.
#
#   ===== CHAPTER 3: strings and input are expression forms =====
#   factor ::= <number> | <string> | <identifier> | "true" | "false" | input_expression
#          | number_expression | string_expression | boolean_expression
#          | type_expression | exit_expression | list_expression
#          | length_expression | "(" expression ")"
#   exit_expression ::= "exit" "(" [ expression ] ")"
#   input_expression ::= "input" "(" [ expression ] ")"
#   number_expression ::= "number" "(" expression ")"
#   string_expression ::= "string" "(" expression ")"
#   boolean_expression ::= "boolean" "(" expression ")"
#   type_expression ::= "type" "(" expression ")"
#
#   ===== CHAPTER 9: list literals and length =====
#   list_expression ::= "[" [ expression { "," expression } ] "]"
#   length_expression ::= "length" "(" expression ")"
#
# input has function-shaped syntax, but this chapter does not implement
# general function calls, parameters, or function values.


def require(tokens, tag, message):
    if tokens[0]["tag"] != tag:
        raise SyntaxError(f"{message}, got {tokens[0]}")
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

    # All five forms take one expression. The AST retains the operation tag;
    # checking the argument's runtime type belongs to the evaluator.
    operations = {"number_conversion": "number", "string_conversion": "string",
                  "boolean_conversion": "boolean", "type_query": "type",
                  "length": "length"}
    if token["tag"] in operations:
        name = operations[token["tag"]]
        tokens = require(tokens[1:], "(", f"Expected '(' after '{name}'")
        expression, tokens = parse_expression(tokens)
        tokens = require(tokens, ")", f"Expected ')' after {name} argument")
        return {"tag": token["tag"], "expression": expression}, tokens

    # ===== CHAPTER 9: list literal =====
    if token["tag"] == "[":
        return parse_list_expression(tokens)

    if token["tag"] == "(":
        # Parentheses restart at the lowest-precedence rule, allowing a complete
        # logical expression wherever a factor is expected.
        node, tokens = parse_expression(tokens[1:])
        tokens = require(tokens, ")", "Expected ')'")
        return node, tokens

    raise SyntaxError(f"Expected factor, got {token}")


def parse_list_expression(tokens):
    # ===== CHAPTER 9 =====
    # list_expression ::= "[" [ expression { "," expression } ] "]"
    tokens = require(tokens, "[", "Expected '['")
    items = []
    if tokens[0]["tag"] != "]":
        item, tokens = parse_expression(tokens)
        items.append(item)
        while tokens[0]["tag"] == ",":
            item, tokens = parse_expression(tokens[1:])
            items.append(item)
    tokens = require(tokens, "]", "Expected ']' to close list literal")
    return {"tag": "list", "items": items}, tokens


def parse_complex_suffixes(node, tokens):
    # ===== CHAPTER 9 =====
    # { index_suffix }, applied to a node already parsed. Shared by reading
    # (postfix indexing in an expression) and writing (an assignment
    # target): both are the same chain of "complex" nodes, evaluated
    # differently depending on which side of "=" they end up on. The tag is
    # "complex" rather than "index" on purpose: a later chapter's function
    # calls are the same postfix shape with a different suffix, and will
    # extend this same node instead of introducing a parallel one.
    while tokens[0]["tag"] == "[":
        index, tokens = parse_expression(tokens[1:])
        tokens = require(tokens, "]", "Expected ']' after index")
        node = {"tag": "complex", "base": node, "index": index}
    return node, tokens


def parse_complex_expression(tokens):
    """complex_expression ::= factor { index_suffix }"""
    node, tokens = parse_factor(tokens)
    return parse_complex_suffixes(node, tokens)


def parse_unary(tokens):
    """unary ::= "-" unary | complex_expression"""
    if tokens[0]["tag"] == "-":
        operand, tokens = parse_unary(tokens[1:])
        return {"tag": "unary-", "operand": operand}, tokens
    return parse_complex_expression(tokens)


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
    # assignment_statement ::= <identifier> { index_suffix } "=" expression
    if tokens[0]["tag"] != "identifier":
        raise SyntaxError(f"Expected identifier, got {tokens[0]}")
    # The target names a destination. It must not read an existing binding;
    # assigning a name for the first time is valid, unless it is indexed,
    # which requires the list it indexes into to already exist.
    target = {"tag": "identifier", "value": tokens[0]["value"]}
    target, tokens = parse_complex_suffixes(target, tokens[1:])
    tokens = require(tokens, "=", "Expected '=' for assignment")
    expression, tokens = parse_expression(tokens)
    return {
        "tag": "assign",
        "target": target,
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
    # ===== CHAPTER 8 =====
    if tokens[0]["tag"] == "while":
        return parse_while_statement(tokens)
    if tokens[0]["tag"] == "break":
        return {"tag": "break"}, tokens[1:]
    if tokens[0]["tag"] == "continue":
        return {"tag": "continue"}, tokens[1:]
    if tokens[0]["tag"] == "identifier":
        return parse_assignment_statement(tokens)
    raise SyntaxError(f"Expected statement, got {tokens[0]}")


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


def parse_while_statement(tokens):
    # ===== CHAPTER 8 =====
    # while_statement ::= "while" "(" expression ")" block
    # A loop body is a block, the same requirement as an if branch: no bare
    # statement, and empty or semicolon-only is a legal body that does
    # nothing each time the condition holds.
    tokens = require(tokens, "while", "Expected 'while'")
    tokens = require(tokens, "(", "Expected '(' after 'while'")
    condition, tokens = parse_expression(tokens)
    tokens = require(tokens, ")", "Expected ')' after while condition")
    body, tokens = parse_block(tokens)
    return {"tag": "while", "condition": condition, "body": body}, tokens


def parse_assert_statement(tokens):
    # The required explanation is a string literal, not another computation.
    tokens = require(tokens, "assert", "Expected 'assert'")
    expression, tokens = parse_expression(tokens)
    tokens = require(tokens, ",", "Expected ',' and explanation string after assertion")
    if tokens[0]["tag"] != "string":
        raise SyntaxError("Expected explanation string after ','")
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


def test_parse_list_expression():
    # ===== CHAPTER 9 TESTS =====
    print("test parse_list_expression()")
    ast, rest = parse_list_expression(tokenize("[]"))
    assert ast == {"tag": "list", "items": []}
    assert rest[0]["tag"] is None

    ast, rest = parse_list_expression(tokenize('[1, "two", true]'))
    assert ast == {"tag": "list", "items": [
        {"tag": "number", "value": 1},
        {"tag": "string", "value": "two"},
        {"tag": "boolean", "value": True},
    ]}
    assert rest[0]["tag"] is None

    # A list literal is itself a factor, so it can be indexed immediately.
    ast, rest = parse_complex_expression(tokenize("[1, 2][0]"))
    assert ast == {
        "tag": "complex",
        "base": {"tag": "list", "items": [
            {"tag": "number", "value": 1}, {"tag": "number", "value": 2},
        ]},
        "index": {"tag": "number", "value": 0},
    }
    assert rest[0]["tag"] is None

    # A list literal is only valid in an expression context, not as a bare
    # statement, so these go through an assignment's right-hand side.
    expect_syntax_error("x=[1, 2", "Expected ']'")
    expect_syntax_error("x=[1 2]", "Expected ']'")


def test_parse_complex_expression_indexing():
    # ===== CHAPTER 9 TESTS =====
    print("test parse_complex_expression() indexing")
    ast, rest = parse_complex_expression(tokenize("items[0]"))
    assert ast == {
        "tag": "complex",
        "base": {"tag": "identifier", "value": "items"},
        "index": {"tag": "number", "value": 0},
    }
    assert rest[0]["tag"] is None

    # Chained indexing nests, base first: matrix[row] is the base of the
    # outer index, not the other way around.
    ast, rest = parse_complex_expression(tokenize("matrix[row][column]"))
    assert ast == {
        "tag": "complex",
        "base": {
            "tag": "complex",
            "base": {"tag": "identifier", "value": "matrix"},
            "index": {"tag": "identifier", "value": "row"},
        },
        "index": {"tag": "identifier", "value": "column"},
    }
    assert rest[0]["tag"] is None

    expect_syntax_error("items[0", "Expected ']'")


def test_parse_length_expression():
    # ===== CHAPTER 9 TESTS =====
    print("test parse length expression")
    ast, rest = parse_factor(tokenize("length(items)"))
    assert ast == {"tag": "length",
                    "expression": {"tag": "identifier", "value": "items"}}
    assert rest[0]["tag"] is None

    # length() is only valid in an expression context, not as a bare
    # statement, so these go through an assignment's right-hand side.
    expect_syntax_error("x=length items)", "Expected '('")
    expect_syntax_error("x=length(items", "Expected ')'")


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

    # ===== CHAPTER 9 TESTS: indexed assignment targets =====
    ast, rest = parse_assignment_statement(tokenize("items[0]=1"))
    assert ast == {
        "tag": "assign",
        "target": {"tag": "complex",
                   "base": {"tag": "identifier", "value": "items"},
                   "index": {"tag": "number", "value": 0}},
        "expression": {"tag": "number", "value": 1},
    }
    assert rest[0]["tag"] is None

    # Chained indexing builds nested "index" targets, base first.
    ast, rest = parse_assignment_statement(tokenize("matrix[row][col]=1"))
    assert ast["target"] == {
        "tag": "complex",
        "base": {"tag": "complex",
                 "base": {"tag": "identifier", "value": "matrix"},
                 "index": {"tag": "identifier", "value": "row"}},
        "index": {"tag": "identifier", "value": "col"},
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


def test_parse_while_statement():
    # ===== CHAPTER 8 TESTS =====
    print("test parse_while_statement()")
    ast, rest = parse_while_statement(tokenize("while (x) { y=1 }"))
    assert ast == {
        "tag": "while",
        "condition": {"tag": "identifier", "value": "x"},
        "body": {"tag": "statement_list",
                 "statements": [{"tag": "assign",
                                 "target": {"tag": "identifier", "value": "y"},
                                 "expression": {"tag": "number", "value": 1}}]},
    }
    assert rest[0]["tag"] is None

    # A loop body is a block: empty is legal, a bare statement is not.
    ast, rest = parse_while_statement(tokenize("while (x) { }"))
    assert ast["body"] == {"tag": "statement_list", "statements": []}
    assert rest[0]["tag"] is None

    expect_syntax_error("while (x) y=1", "Expected '{'")
    expect_syntax_error("while x { y=1 }", "Expected '('")
    expect_syntax_error("while (x { y=1 }", "Expected ')'")


def test_parse_break_and_continue():
    # ===== CHAPTER 8 TESTS =====
    print("test parse break and continue")
    ast, rest = parse_statement(tokenize("break"))
    assert ast == {"tag": "break"}
    assert rest[0]["tag"] is None

    ast, rest = parse_statement(tokenize("continue"))
    assert ast == {"tag": "continue"}
    assert rest[0]["tag"] is None

    # Both are bare keywords: no argument, no parentheses.
    ast = parse(tokenize("while (true) { break; continue }"))
    body = ast["statements"]["statements"][0]["body"]["statements"]
    assert [statement["tag"] for statement in body] == ["break", "continue"]


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
    test_parse_list_expression()
    test_parse_complex_expression_indexing()
    test_parse_length_expression()
    test_parse_term_and_expression()
    test_parse_print_statement()
    test_parse_assignment_statement()
    test_parse_block()
    test_parse_if_statement()
    test_parse_while_statement()
    test_parse_break_and_continue()
    test_parse_statement_list()
    test_parse_program()
    print("done.")
