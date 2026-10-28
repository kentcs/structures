# parser.py

from tokenizer import tokenize


# EBNF
#
#   program ::= statement_list
#   statement_list ::= { ";" } statement { ";" { ";" } statement } { ";" }
#   statement ::= print_statement | exit_expression
#               | assert_statement | if_statement | while_statement
#               | break_statement | continue_statement
#               | function_definition | return_statement | expression
#   assert_statement ::= "assert" expression "," <string>
#
#   ===== CHAPTER 11: assignment moves into the expression grammar =====
#   expression_statement ::= expression
#   Any expression is a legal statement; its value is computed and
#   discarded. This covers a bare call made for its effect (log("done")),
#   an assignment (x = 1, folded into expression below), and an expression
#   kept purely for its value with no effect at all (1 + 1), which is
#   legal and simply useless, the same as in most languages. The grammar
#   does not try to rule out useless statements; a clean, predictable rule
#   -- any expression may be a statement -- is worth more than a grammar
#   that also has to say which expressions are "worth" writing alone.
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
#   ===== CHAPTER 11: assignment is the lowest-precedence expression form =====
#   expression ::= logic_or [ "=" expression ]
#   Right-associative: the right-hand side is itself a full expression, so
#   x = y = 1 parses as x = (y = 1), and x = y is legal wherever an
#   expression is, including as a bare statement. The parser does not
#   restrict what can appear to the left of "=" -- 1 = 2 and f() = 5 parse
#   without complaint, the same clean rule applying uniformly. Evaluation
#   decides whether a target can actually be assigned to: only an
#   identifier or an index/field chain not ending in a call.
#
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
#   complex_expression ::= factor { index_suffix | call_suffix }
#   index_suffix ::= "[" expression "]" | "." <identifier>
#   An index_suffix chain produces "complex" nodes, not "index" nodes, on
#   purpose: a later chapter's function calls are the same postfix form
#   with a different suffix, and extend this same chain instead of
#   introducing a parallel one. Indexing applies uniformly after any
#   factor, not just an identifier: a list literal, a parenthesized
#   expression, even another complex expression, which is what makes
#   matrix[row][column] a chain of two nodes rather than a special
#   two-argument form.
#
#   ===== CHAPTER 10: "." is sugar within index_suffix =====
#   "." <identifier> resolves to "[" <string literal> "]" at parse time,
#   producing the same "complex" node either way, so the two forms mix
#   freely in one chain: a[1].bob[3][4].a.b["dog"].
#
#   ===== CHAPTER 11: call_suffix is the promised extension =====
#   call_suffix ::= "(" [ expression { "," expression } ] ")"
#   A call produces a "call" node, not another "complex" one: it takes an
#   argument list, not a single index, so it is a sibling in the same
#   suffix chain rather than a third meaning crammed into "complex". All
#   three suffixes mix freely in any order: funcs[0](x), makeAdder(1)(2),
#   and list[i].method() are each one pass through this one chain.
#
#   ===== CHAPTER 3: strings and input are expression forms =====
#   ===== CHAPTER 11: "null" and function literals are factors too =====
#   factor ::= <number> | <string> | <identifier> | "true" | "false"
#          | "null" | input_expression
#          | number_expression | string_expression | boolean_expression
#          | type_expression | list_expression
#          | length_expression | slice_expression | head_expression
#          | tail_expression | copy_expression | object_expression
#          | function_expression | "(" expression ")"
#   exit_expression ::= "exit" "(" [ expression ] ")"
#   exit_expression is a statement, not a factor: it cannot nest inside a
#   larger expression, only stand alone. Status can still escape from deep
#   inside an expression now that calls exist: a function's own exit
#   propagates outward through the call, the same way any other status
#   does -- see test_exit_from_an_embedded_function_call_propagates.
#   input_expression ::= "input" "(" [ expression ] ")"
#   number_expression ::= "number" "(" expression ")"
#   string_expression ::= "string" "(" expression ")"
#   boolean_expression ::= "boolean" "(" expression ")"
#   type_expression ::= "type" "(" expression ")"
#
#   ===== CHAPTER 9: list literals, length, slice, head, and tail =====
#   list_expression ::= "[" [ expression { "," expression } ] "]"
#   length_expression ::= "length" "(" expression ")"
#   slice_expression ::= "slice" "(" expression "," expression "," expression ")"
#   head_expression ::= "head" "(" expression ")"
#   tail_expression ::= "tail" "(" expression ")"
#   slice, head, and tail are dedicated forms, like length: the syntax looks
#   like a call, but no general function call exists yet.
#
#   ===== CHAPTER 10: copy =====
#   copy_expression ::= "copy" "(" expression ")"
#   Dedicated form for the same reason. x == copy(x) for every x, and for a
#   list the copy is deep: nested lists are new lists too, all the way down.
#
#   ===== CHAPTER 11: functions =====
#   function_expression ::= "function" "(" [ <identifier> { "," <identifier> } ] ")" block
#   function_definition ::= "function" <identifier>
#                            "(" [ <identifier> { "," <identifier> } ] ")" block
#   return_statement ::= "return" [ expression ]
#   A function expression is a factor: a value, like any other, with no
#   name of its own. function_definition is pure syntactic sugar for an
#   assignment of a function expression to a name, resolved at parse
#   time to the identical AST that assignment would have produced; the
#   evaluator never sees a "function_definition" node at all. input,
#   length, slice, head, tail, and copy keep their own dedicated,
#   non-general forms even now that general calls exist: nothing about
#   this chapter changes how those are parsed or evaluated.


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
    # Both keywords become the same kind of literal node, with different values.
    if token["tag"] in ("true", "false"):
        return {"tag": "boolean", "value": token["tag"] == "true"}, tokens[1:]
    # ===== CHAPTER 11: the value a function has if it never returns one =====
    if token["tag"] == "null":
        return {"tag": "null"}, tokens[1:]
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
                  "length": "length", "head": "head", "tail": "tail",
                  "copy": "copy"}
    if token["tag"] in operations:
        name = operations[token["tag"]]
        tokens = require(tokens[1:], "(", f"Expected '(' after '{name}'")
        expression, tokens = parse_expression(tokens)
        tokens = require(tokens, ")", f"Expected ')' after {name} argument")
        return {"tag": token["tag"], "expression": expression}, tokens

    if token["tag"] == "{":
        return parse_object_expression(tokens)

    # ===== CHAPTER 9: list literal =====
    if token["tag"] == "[":
        return parse_list_expression(tokens)

    # ===== CHAPTER 9: slice takes three expressions =====
    if token["tag"] == "slice":
        return parse_slice_expression(tokens)

    # ===== CHAPTER 11: function literal =====
    if token["tag"] == "function":
        return parse_function_expression(tokens)

    if token["tag"] == "(":
        # Parentheses restart at the lowest-precedence rule, allowing a complete
        # logical expression wherever a factor is expected.
        node, tokens = parse_expression(tokens[1:])
        tokens = require(tokens, ")", "Expected ')'")
        return node, tokens

    raise SyntaxError(f"Expected factor, got {token}")


def parse_object_expression(tokens):
    # object_expression ::= "{" [ expression ":" expression
    #                          { "," expression ":" expression } ] "}"
    # Keep ordered pairs in the AST: duplicate evaluated keys are runtime errors.
    tokens = require(tokens, "{", "Expected '{'")
    fields = []
    if tokens and tokens[0]["tag"] == "}":
        return {"tag": "object", "fields": fields}, tokens[1:]
    while True:
        key, tokens = parse_expression(tokens)
        tokens = require(tokens, ":", "Expected ':' after object key")
        value, tokens = parse_expression(tokens)
        fields.append((key, value))
        if not tokens or tokens[0]["tag"] != ",":
            break
        tokens = tokens[1:]
    tokens = require(tokens, "}", "Expected '}' after object fields")
    return {"tag": "object", "fields": fields}, tokens


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


def parse_slice_expression(tokens):
    # ===== CHAPTER 9 =====
    # slice_expression ::= "slice" "(" expression "," expression "," expression ")"
    # The three expressions are the sequence, the start position, and the end
    # position. Checking their types and ranges belongs to the evaluator.
    tokens = require(tokens, "slice", "Expected 'slice'")
    tokens = require(tokens, "(", "Expected '(' after 'slice'")
    sequence, tokens = parse_expression(tokens)
    tokens = require(tokens, ",", "Expected ',' after slice sequence")
    start, tokens = parse_expression(tokens)
    tokens = require(tokens, ",", "Expected ',' after slice start")
    end, tokens = parse_expression(tokens)
    tokens = require(tokens, ")", "Expected ')' after slice end")
    return {"tag": "slice", "expression": sequence, "start": start, "end": end}, tokens


def parse_complex_suffixes(node, tokens):
    # ===== CHAPTER 9 =====
    # { index_suffix }, applied to a node already parsed. Shared by reading
    # (postfix indexing in an expression) and writing (an assignment
    # target): both are the same chain of "complex" nodes, evaluated
    # differently depending on which side of "=" they end up on. The tag is
    # "complex" rather than "index" on purpose: a later chapter's function
    # calls are the same postfix form with a different suffix, and will
    # share this same loop rather than becoming a parallel parsing path --
    # though a call will need its own node tag, not an extension of this
    # one, since a call's payload is an argument list, not an index.
    #
    # ===== CHAPTER 10 =====
    # obj.field is sugar for obj["field"]: it resolves here to the exact
    # same "complex" node, with a string node built from the field name,
    # so nothing downstream of parsing needs to know the sugar was used.
    # The two suffix kinds mix freely, in any order, because this is one
    # loop handling both: a[1].bob[3][4].a.b["dog"] is one chain.
    #
    # ===== CHAPTER 11 =====
    # "(" is the promised third suffix: a call takes an argument list
    # instead of a single index, so it builds a "call" node rather than
    # stretching "complex" to mean two different things depending on
    # which key is present. It shares this same loop, not a parallel one,
    # which is what lets the suffixes chain in any order and any mix:
    # funcs[0](x), makeAdder(1)(2), and list[i].method() are all one
    # pass through this while loop, same as the mixed [] and . chains
    # chapter 10 already allowed.
    while tokens[0]["tag"] in ("[", ".", "("):
        if tokens[0]["tag"] == "[":
            index, tokens = parse_expression(tokens[1:])
            tokens = require(tokens, "]", "Expected ']' after index")
            node = {"tag": "complex", "base": node, "index": index}
        elif tokens[0]["tag"] == ".":
            tokens = tokens[1:]
            if tokens[0]["tag"] != "identifier":
                raise SyntaxError(f"Expected a field name after '.', got {tokens[0]}")
            index = {"tag": "string", "value": tokens[0]["value"]}
            tokens = tokens[1:]
            node = {"tag": "complex", "base": node, "index": index}
        else:
            arguments, tokens = parse_call_arguments(tokens)
            node = {"tag": "call", "callee": node, "arguments": arguments}
    return node, tokens


def parse_call_arguments(tokens):
    # ===== CHAPTER 11 =====
    # call_suffix ::= "(" [ expression { "," expression } ] ")"
    tokens = require(tokens, "(", "Expected '('")
    arguments = []
    if tokens[0]["tag"] != ")":
        argument, tokens = parse_expression(tokens)
        arguments.append(argument)
        while tokens[0]["tag"] == ",":
            argument, tokens = parse_expression(tokens[1:])
            arguments.append(argument)
    tokens = require(tokens, ")", "Expected ')' to close argument list")
    return arguments, tokens


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
    # ===== CHAPTER 11 =====
    # expression ::= logic_or [ "=" expression ]
    # Assignment is the lowest-precedence operator, and right-associative:
    # the right-hand side is parsed by calling parse_expression again, so
    # x = y = 1 parses as x = (y = 1), the same nesting a reader would draw.
    # Operator aliases were normalized by the tokenizer, not by these helpers.
    left, tokens = parse_logic_or(tokens)
    if tokens[0]["tag"] == "=":
        right, tokens = parse_expression(tokens[1:])
        return {"tag": "assign", "target": left, "expression": right}, tokens
    return left, tokens


def parse_print_statement(tokens):
    # ===== CHAPTER 3: parentheses are required =====
    # print_statement ::= "print" "(" expression ")"
    tokens = require(tokens, "print", "Expected 'print'")
    tokens = require(tokens, "(", "Expected '(' after 'print'")
    expression, tokens = parse_expression(tokens)
    tokens = require(tokens, ")", "Expected ')' after print argument")
    return {"tag": "print", "expression": expression}, tokens


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
    # ===== CHAPTER 11 =====
    # "function" alone is ambiguous: an identifier right after it means the
    # named-definition sugar, statement-only syntax with no expression-level
    # form. Anything else -- most commonly "(" -- means an anonymous
    # function expression, an ordinary factor, used here as a statement
    # (an immediately invoked function, for example); that case falls
    # through to the expression path below rather than being special-cased,
    # so it can continue into a call suffix, a comparison, or an assignment
    # exactly as any other expression statement would.
    if tokens[0]["tag"] == "function" and tokens[1]["tag"] == "identifier":
        return parse_function_definition(tokens)
    if tokens[0]["tag"] == "return":
        return parse_return_statement(tokens)
    # ===== CHAPTER 11 =====
    # Anything else is an expression_statement: any expression, including a
    # bare assignment, used as a statement with its value discarded. This
    # covers an assignment (x = 1), a call made only for its effect
    # (log("done")), and an expression kept only for what it evaluates --
    # a useless but harmless statement like 1 + 1, the same way a real
    # language does not forbid writing one. Nothing here checks whether the
    # expression does anything observable; that is not the parser's job.
    return parse_expression(tokens)


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


def parse_function_tail(tokens):
    # ===== CHAPTER 11 =====
    # Shared by the expression and statement forms below, starting right
    # after the "function" keyword has already been consumed:
    #   "(" [ <identifier> { "," <identifier> } ] ")" block
    parameters = []
    tokens = require(tokens, "(", "Expected '(' after 'function'")
    if tokens[0]["tag"] != ")":
        if tokens[0]["tag"] != "identifier":
            raise SyntaxError(f"Expected a parameter name, got {tokens[0]}")
        parameters.append(tokens[0]["value"])
        tokens = tokens[1:]
        while tokens[0]["tag"] == ",":
            if tokens[1]["tag"] != "identifier":
                raise SyntaxError(f"Expected a parameter name, got {tokens[1]}")
            parameters.append(tokens[1]["value"])
            tokens = tokens[2:]
    tokens = require(tokens, ")", "Expected ')' after parameter list")
    body, tokens = parse_block(tokens)
    return {"tag": "function", "parameters": parameters, "body": body}, tokens


def parse_function_expression(tokens):
    # ===== CHAPTER 11 =====
    # function_expression ::= "function" "(" [ <identifier> { "," <identifier> } ] ")" block
    # This is where the actual work happens: a function expression is a
    # factor, a value like any other, with no name of its own. It can be
    # assigned, passed as an argument, returned, or called immediately --
    # function(x) { return x+x }(5) is this factor followed by a call
    # suffix, the same as any other factor followed by "(args)".
    tokens = require(tokens, "function", "Expected 'function'")
    return parse_function_tail(tokens)


def parse_function_definition(tokens):
    # ===== CHAPTER 11 =====
    # function_definition ::= "function" <identifier>
    #                          "(" [ <identifier> { "," <identifier> } ] ")" block
    # Purely syntactic sugar: a named definition is exactly an assignment
    # of a function expression to that name, resolved here so nothing
    # downstream of parsing -- the evaluator least of all -- ever needs to
    # know the named form was used. "function double(x) { return x+x }"
    # produces the identical AST "double = function(x) { return x+x };"
    # would have.
    tokens = require(tokens, "function", "Expected 'function'")
    if tokens[0]["tag"] != "identifier":
        raise SyntaxError(f"Expected a function name, got {tokens[0]}")
    name = tokens[0]["value"]
    function_expression, tokens = parse_function_tail(tokens[1:])
    return {
        "tag": "assign",
        "target": {"tag": "identifier", "value": name},
        "expression": function_expression,
    }, tokens


def parse_return_statement(tokens):
    # ===== CHAPTER 11 =====
    # return_statement ::= "return" [ expression ]
    # A bare return (no expression) still leaves the function's result as
    # null: it did not fall off the end of the body, but it did not
    # supply a value either, so the two cases agree.
    tokens = require(tokens, "return", "Expected 'return'")
    if tokens[0]["tag"] in (";", "}", None):
        return {"tag": "return", "expression": None}, tokens
    expression, tokens = parse_expression(tokens)
    return {"tag": "return", "expression": expression}, tokens


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


def test_parse_slice_head_tail_expressions():
    # ===== CHAPTER 9 TESTS =====
    print("test parse slice, head, and tail expressions")
    ast, rest = parse_factor(tokenize("slice(items, 1, 3)"))
    assert ast == {"tag": "slice",
                   "expression": {"tag": "identifier", "value": "items"},
                   "start": {"tag": "number", "value": 1},
                   "end": {"tag": "number", "value": 3}}
    assert rest[0]["tag"] is None

    ast, rest = parse_factor(tokenize("head(items)"))
    assert ast == {"tag": "head",
                   "expression": {"tag": "identifier", "value": "items"}}
    assert rest[0]["tag"] is None

    ast, rest = parse_factor(tokenize("tail(items)"))
    assert ast == {"tag": "tail",
                   "expression": {"tag": "identifier", "value": "items"}}
    assert rest[0]["tag"] is None

    # Each result is a factor, so it can be indexed or nested immediately.
    ast, rest = parse_complex_expression(tokenize("tail(items)[0]"))
    assert ast == {"tag": "complex",
                   "base": {"tag": "tail",
                            "expression": {"tag": "identifier", "value": "items"}},
                   "index": {"tag": "number", "value": 0}}
    assert rest[0]["tag"] is None

    ast, rest = parse_factor(tokenize("slice(tail(items), 0, length(items))"))
    assert ast["tag"] == "slice"
    assert ast["expression"]["tag"] == "tail"
    assert ast["end"]["tag"] == "length"

    expect_syntax_error("x=slice items, 1, 3)", "Expected '('")
    expect_syntax_error("x=slice(items 1, 3)", "Expected ','")
    expect_syntax_error("x=slice(items, 1 3)", "Expected ','")
    expect_syntax_error("x=slice(items, 1)", "Expected ','")
    expect_syntax_error("x=slice(items, 1, 3", "Expected ')'")
    expect_syntax_error("x=head items)", "Expected '('")
    expect_syntax_error("x=head(items", "Expected ')'")
    expect_syntax_error("x=tail items)", "Expected '('")
    expect_syntax_error("x=tail(items", "Expected ')'")


def test_parse_copy_expression():
    # ===== CHAPTER 10 TEST =====
    print("test parse copy expression")
    ast, rest = parse_factor(tokenize("copy(items)"))
    assert ast == {"tag": "copy",
                   "expression": {"tag": "identifier", "value": "items"}}
    assert rest[0]["tag"] is None

    # A factor, so it can be indexed or nested immediately.
    ast, rest = parse_complex_expression(tokenize("copy(items)[0]"))
    assert ast == {"tag": "complex",
                   "base": {"tag": "copy",
                            "expression": {"tag": "identifier", "value": "items"}},
                   "index": {"tag": "number", "value": 0}}

    expect_syntax_error("x=copy items)", "Expected '('")
    expect_syntax_error("x=copy(items", "Expected ')'")


def test_parse_dot_syntax():
    # ===== CHAPTER 10 TEST =====
    print("test parse dot syntax")
    dot_ast, rest = parse_complex_expression(tokenize("obj.field"))
    assert rest[0]["tag"] is None
    bracket_ast, _ = parse_complex_expression(tokenize('obj["field"]'))
    # Sugar: the exact same AST, not merely an equivalent one.
    assert dot_ast == bracket_ast
    assert dot_ast == {"tag": "complex",
                       "base": {"tag": "identifier", "value": "obj"},
                       "index": {"tag": "string", "value": "field"}}

    # Suffixes mix freely, in any order, read and assignment target alike.
    ast, rest = parse_complex_expression(tokenize('a[1].bob[3][4].a.b["dog"]'))
    assert rest[0]["tag"] is None
    assert ast["tag"] == "complex"
    assert ast["index"] == {"tag": "string", "value": "dog"}
    assert ast["base"]["index"] == {"tag": "string", "value": "b"}

    ast, rest = parse_statement(tokenize('a.b = 5;'))
    assert ast["tag"] == "assign"
    assert ast["target"] == {"tag": "complex",
                             "base": {"tag": "identifier", "value": "a"},
                             "index": {"tag": "string", "value": "b"}}

    expect_syntax_error("x=obj.", "Expected a field name after '.'")
    expect_syntax_error('x=obj."field"', "Expected a field name after '.'")
    # obj.5 never reaches this error: the number pattern's \d*\.\d+
    # matches ".5" as the float 0.5 before a "." token is ever produced,
    # so this fails earlier, as a stray number where a statement ends.
    expect_syntax_error("x=obj.5", "Unexpected token")


def test_parse_null():
    # ===== CHAPTER 11 TEST =====
    print("test parse null")
    ast, rest = parse_factor(tokenize("null"))
    assert ast == {"tag": "null"}
    assert rest[0]["tag"] is None


def test_parse_function_expression():
    # ===== CHAPTER 11 TEST =====
    print("test parse function expression")
    ast, rest = parse_factor(tokenize("function(x) { return x }"))
    assert ast == {
        "tag": "function",
        "parameters": ["x"],
        "body": {"tag": "statement_list",
                 "statements": [{"tag": "return",
                                 "expression": {"tag": "identifier", "value": "x"}}]},
    }
    assert rest[0]["tag"] is None

    # No parameters, and an empty body.
    ast, rest = parse_factor(tokenize("function() { }"))
    assert ast == {"tag": "function", "parameters": [],
                   "body": {"tag": "statement_list", "statements": []}}
    assert rest[0]["tag"] is None

    # Multiple parameters.
    ast, rest = parse_factor(tokenize("function(a, b, c) { return a }"))
    assert ast["parameters"] == ["a", "b", "c"]

    expect_syntax_error("x=function x) { }", "Expected '('")
    expect_syntax_error("x=function(x { }", "Expected ')'")
    expect_syntax_error("x=function(x) y", "Expected '{' to start a block")
    expect_syntax_error("x=function(1) { }", "Expected a parameter name")


def test_parse_function_definition():
    # ===== CHAPTER 11 TEST =====
    print("test parse function definition")
    # Purely syntactic sugar: identical to the equivalent assignment.
    sugar, rest = parse_statement(tokenize("function double(x) { return x+x }"))
    assert rest[0]["tag"] is None
    resolved, rest = parse_statement(tokenize("double = function(x) { return x+x }"))
    assert rest[0]["tag"] is None
    assert sugar == resolved
    assert sugar == {
        "tag": "assign",
        "target": {"tag": "identifier", "value": "double"},
        "expression": {
            "tag": "function",
            "parameters": ["x"],
            "body": {"tag": "statement_list",
                     "statements": [{"tag": "return",
                                     "expression": {"tag": "+",
                                                    "left": {"tag": "identifier", "value": "x"},
                                                    "right": {"tag": "identifier", "value": "x"}}}]},
        },
    }

    # ===== CHAPTER 11: "function(x) { }" is no longer ambiguous =====
    # No identifier follows "function", so parse_statement never routes
    # this to parse_function_definition at all; it is an ordinary anonymous
    # function expression used as a (useless, legal) statement. Calling
    # parse_function_definition directly still rejects a missing name --
    # that check stays, for whatever might call this function on its own.
    ast, rest = parse_statement(tokenize("function(x) { }"))
    assert ast == {"tag": "function", "parameters": ["x"],
                   "body": {"tag": "statement_list", "statements": []}}
    assert rest[0]["tag"] is None
    try:
        parse_function_definition(tokenize("function(x) { }"))
    except SyntaxError as error:
        assert "Expected a function name" in str(error)
    else:
        raise Exception("Expected SyntaxError for parse_function_definition('function(x) { }')")


def test_parse_return_statement():
    # ===== CHAPTER 11 TEST =====
    print("test parse return statement")
    ast, rest = parse_statement(tokenize("return 5"))
    assert ast == {"tag": "return", "expression": {"tag": "number", "value": 5}}
    assert rest[0]["tag"] is None

    # A bare return, with nothing following it, parses with no expression.
    ast, rest = parse_block(tokenize("{ return }"))
    assert ast["statements"][0] == {"tag": "return", "expression": None}

    ast, rest = parse_block(tokenize("{ return; }"))
    assert ast["statements"][0] == {"tag": "return", "expression": None}


def test_parse_call_expression():
    # ===== CHAPTER 11 TEST =====
    print("test parse call expression")
    ast, rest = parse_complex_expression(tokenize("f()"))
    assert ast == {"tag": "call", "callee": {"tag": "identifier", "value": "f"},
                   "arguments": []}
    assert rest[0]["tag"] is None

    ast, rest = parse_complex_expression(tokenize("f(1, 2, 3)"))
    assert ast == {"tag": "call", "callee": {"tag": "identifier", "value": "f"},
                   "arguments": [{"tag": "number", "value": 1},
                                 {"tag": "number", "value": 2},
                                 {"tag": "number", "value": 3}]}
    assert rest[0]["tag"] is None

    # The three suffixes mix freely, in any order, same as [] and . already did.
    ast, rest = parse_complex_expression(tokenize("funcs[0](x)"))
    assert ast == {"tag": "call",
                   "callee": {"tag": "complex",
                             "base": {"tag": "identifier", "value": "funcs"},
                             "index": {"tag": "number", "value": 0}},
                   "arguments": [{"tag": "identifier", "value": "x"}]}
    assert rest[0]["tag"] is None

    # A call's own result can be called again immediately: makeAdder(1)(2).
    ast, rest = parse_complex_expression(tokenize("makeAdder(1)(2)"))
    assert ast["tag"] == "call"
    assert ast["callee"]["tag"] == "call"
    assert ast["callee"]["callee"] == {"tag": "identifier", "value": "makeAdder"}

    # A call's result can also be indexed or accessed by field immediately.
    ast, rest = parse_complex_expression(tokenize("f().result"))
    assert ast == {"tag": "complex",
                   "base": {"tag": "call", "callee": {"tag": "identifier", "value": "f"},
                            "arguments": []},
                   "index": {"tag": "string", "value": "result"}}

    # Assignment statements: a call is a legal bare statement, and a call
    # followed by an index suffix is a legal assignment target (the call
    # only supplies the list or object the index writes into). Whether a
    # bare call itself is a legal assignment target is an evaluation-time
    # question now, not a parse-time one -- see test_evaluate_assign_targets.
    ast, rest = parse_statement(tokenize("f(1, 2)"))
    assert ast == {"tag": "call", "callee": {"tag": "identifier", "value": "f"},
                   "arguments": [{"tag": "number", "value": 1},
                                 {"tag": "number", "value": 2}]}
    assert rest[0]["tag"] is None

    # f() = 5 now parses fine: the parser no longer restricts what can
    # appear to the left of "=". See test_evaluate_assign_targets for the
    # evaluation-time rejection.
    ast, rest = parse_statement(tokenize("f() = 5"))
    assert ast == {"tag": "assign",
                   "target": {"tag": "call", "callee": {"tag": "identifier", "value": "f"},
                              "arguments": []},
                   "expression": {"tag": "number", "value": 5}}

    ast, rest = parse_statement(tokenize("f()[0] = 5"))
    assert ast["tag"] == "assign"
    assert ast["target"]["base"]["tag"] == "call"

    # A bare name is now a legal statement too: it is parsed, just useless.
    ast, rest = parse_statement(tokenize("x"))
    assert ast == {"tag": "identifier", "value": "x"}

    expect_syntax_error("f(1", "Expected ')' to close argument list")
    expect_syntax_error("f(1 2)", "Expected ')' to close argument list")


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


def test_parse_assignment_expression():
    # ===== CHAPTER 11: assignment moved into the expression grammar =====
    print("test parse_assignment_expression()")
    ast, rest = parse_expression(tokenize('greeting="Hello"'))
    assert ast == {
        "tag": "assign",
        "target": {"tag": "identifier", "value": "greeting"},
        "expression": {"tag": "string", "value": "Hello"},
    }
    assert rest[0]["tag"] is None

    # ===== CHAPTER 9 TESTS: indexed assignment targets =====
    ast, rest = parse_expression(tokenize("items[0]=1"))
    assert ast == {
        "tag": "assign",
        "target": {"tag": "complex",
                   "base": {"tag": "identifier", "value": "items"},
                   "index": {"tag": "number", "value": 0}},
        "expression": {"tag": "number", "value": 1},
    }
    assert rest[0]["tag"] is None

    # Chained indexing builds nested "index" targets, base first.
    ast, rest = parse_expression(tokenize("matrix[row][col]=1"))
    assert ast["target"] == {
        "tag": "complex",
        "base": {"tag": "complex",
                 "base": {"tag": "identifier", "value": "matrix"},
                 "index": {"tag": "identifier", "value": "row"}},
        "index": {"tag": "identifier", "value": "col"},
    }
    assert rest[0]["tag"] is None

    # Right-associative and chainable: x = y = 1 parses as x = (y = 1).
    ast, rest = parse_expression(tokenize("x=y=1"))
    assert ast == {
        "tag": "assign",
        "target": {"tag": "identifier", "value": "x"},
        "expression": {
            "tag": "assign",
            "target": {"tag": "identifier", "value": "y"},
            "expression": {"tag": "number", "value": 1},
        },
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
    expect_syntax_error("if (true) { ;", "Expected factor")
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
    expect_syntax_error("if (true) { x=1 }; else { x=2 }", "Expected factor")


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
        expect_syntax_error(source, "Expected factor")


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
    test_parse_slice_head_tail_expressions()
    test_parse_copy_expression()
    test_parse_dot_syntax()
    test_parse_null()
    test_parse_function_expression()
    test_parse_function_definition()
    test_parse_return_statement()
    test_parse_call_expression()
    test_parse_term_and_expression()
    test_parse_print_statement()
    test_parse_assignment_expression()
    test_parse_block()
    test_parse_if_statement()
    test_parse_while_statement()
    test_parse_break_and_continue()
    test_parse_statement_list()
    test_parse_program()
    print("done.")
