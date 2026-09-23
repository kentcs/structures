import re


# At each source position, the first matching pattern wins.
# Longer operators and reserved words therefore precede their shorter matches.
patterns = [
    (r"\s+", "whitespace"),
    (r"//[^\r\n]*", "comment"),  # Before division; leave the line ending for whitespace.

    # ===== CHAPTER 3: string literals =====
    # Strings use double quotes and stay on one source line.
    (r'"(?:\\[^\r\n]|[^"\\\r\n])*"', "string"),

    (r"\d*\.\d+|\d+\.\d*|\d+", "number"),
    (r"==", "=="),
    # Inequality must win over the single-character spelling of "not".
    (r"!=", "!="),
    # Normalize both spellings here, so the parser only needs word-form tags.
    # Word boundaries keep names such as "android" and "notable" intact.
    (r"and\b|&&", "and"),
    (r"or\b|\|\|", "or"),
    (r"not\b|!", "not"),
    (r"<=", "<="),
    (r">=", ">="),
    (r"<", "<"),
    (r">", ">"),
    (r"\+", "+"),
    (r"\-", "-"),
    (r"\/", "/"),
    (r"\*", "*"),
    (r"\(", "("),
    (r"\)", ")"),
    (r"\=", "="),
    (r"\;", ";"),
    (r"print\b", "print"),
    (r"true\b", "true"),
    (r"false\b", "false"),

    # ===== CHAPTER 3: input expression =====
    # input is a dedicated expression form for now, not a general function.
    (r"input\b", "input"),
    (r"number\b", "number_conversion"),
    (r"string\b", "string_conversion"),
    (r"boolean\b", "boolean_conversion"),
    (r"type\b", "type_query"),

    (r"[a-zA-Z_][\w]*", "identifier"),
    (r".", "error"),
]

patterns = [(re.compile(pattern), tag) for pattern, tag in patterns]


def decode_string(text, line, column):
    # The tokenizer has already matched the surrounding quotes. Decode only
    # Vertex's supported escapes, not the full Python string-literal language.
    escapes = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}
    result = ""
    position = 1
    while position < len(text) - 1:
        character = text[position]
        if character == "\\":
            position += 1
            character = text[position]
            if character not in escapes:
                raise SyntaxError(
                    f"Unknown escape \\{character} at line {line}, "
                    f"column {column + position - 1}"
                )
            character = escapes[character]
        # Append the decoded character once; do not interpret it again.
        result += character
        position += 1
    return result


def tokenize(characters):
    "Tokenize a string using the patterns above"
    tokens = []
    position = 0
    line = 1
    column = 1

    while position < len(characters):
        match = None
        current_tag = None
        for pattern, tag in patterns:
            # Match at this position, never search past an unrecognized character.
            match = pattern.match(characters, position)
            if match:
                current_tag = tag
                break
        assert match is not None
        value = match.group(0)

        if current_tag == "error":
            raise SyntaxError(f"Unexpected character: {value!r}")

        # Comments and whitespace advance through the source but produce no token.
        # A string is matched as a whole, so "//" inside it is not a comment.
        if current_tag not in ("whitespace", "comment"):
            token = {"tag": current_tag, "line": line, "column": column}
            if current_tag == "number":
                token["value"] = float(value) if "." in value else int(value)
            elif current_tag == "string":
                token["value"] = decode_string(value, line, column)
            elif current_tag == "identifier":
                token["value"] = value
            tokens.append(token)

        # Count source characters, not decoded string characters. An escaped
        # newline in a string does not move the following token to another line.
        for character in value:
            if character == "\n":
                line += 1
                column = 1
            else:
                column += 1
        position = match.end()

    # An explicit end marker lets parser helpers inspect the next token safely.
    tokens.append({"tag": None, "line": line, "column": column})
    return tokens


def test_digits():
    print("test tokenize digits")
    tokens = tokenize("123")
    assert tokens[0]["tag"] == "number"
    assert tokens[0]["value"] == 123
    assert tokens[1]["tag"] is None


def test_floats():
    print("test tokenize floats")
    for text, expected in [("1.5", 1.5), (".5", 0.5), ("5.", 5.0)]:
        tokens = tokenize(text)
        assert tokens[0]["tag"] == "number"
        assert tokens[0]["value"] == expected
        assert tokens[1]["tag"] is None


def test_strings():
    # ===== CHAPTER 3 TESTS =====
    print("test tokenize strings")
    tokens = tokenize(r'"hello" "line\nfeed" "say \"hello\""')
    assert [token["tag"] for token in tokens] == [
        "string",
        "string",
        "string",
        None,
    ]
    assert tokens[0]["value"] == "hello"
    assert tokens[1]["value"] == "line\nfeed"
    assert tokens[2]["value"] == 'say "hello"'


def test_string_escapes():
    print("test string escapes")
    for source, expected in [
        ('""', ""),
        (r'"\n\t\r\"\\"', '\n\t\r"\\'),
        (r'"\\n"', "\\n"),
        (r'"ends\\"', "ends\\"),
        ('"plain text"', "plain text"),
    ]:
        assert tokenize(source)[0]["value"] == expected

    for escape in [r"\q", r"\x41", r"\u0041", r"\101", r"\b", r"\'"]:
        try:
            tokenize('\n  "' + escape + '"')
        except SyntaxError as error:
            assert "Unknown escape" in str(error)
            assert "line 2, column 4" in str(error)
        else:
            raise AssertionError(f"Accepted unsupported escape: {escape}")

    for source in ['"a\nb"', '"a\rb"', '"a\r\nb"', '"a\\\nb"', '"a\\\rb"', '"ends\\"']:
        try:
            tokenize(source)
        except SyntaxError:
            pass
        else:
            raise AssertionError(f"Accepted malformed string: {source!r}")

    tokens = tokenize(r'"\n" next')
    assert tokens[1]["line"] == 1
    assert tokens[1]["column"] == 6


def test_operators():
    print("test tokenize operators")
    tokens = tokenize("+ - * / ( ) = ;")
    tags = [token["tag"] for token in tokens]
    assert tags == ["+", "-", "*", "/", "(", ")", "=", ";", None]


def test_keywords():
    print("test tokenize keywords")
    tokens = tokenize("print input printer input_value")
    tags = [token["tag"] for token in tokens]
    assert tags == ["print", "input", "identifier", "identifier", None]
    assert tokens[2]["value"] == "printer"
    assert tokens[3]["value"] == "input_value"


def test_identifiers():
    print("test tokenize identifiers")
    tokens = tokenize("foo bar baz")
    tags = [token["tag"] for token in tokens]
    assert tags == ["identifier", "identifier", "identifier", None]
    assert tokens[0]["value"] == "foo"
    assert tokens[2]["value"] == "baz"


def test_expressions():
    print("test tokenize expressions")
    tokens = tokenize('"dog"*2+"!"')
    assert [token["tag"] for token in tokens] == [
        "string",
        "*",
        "number",
        "+",
        "string",
        None,
    ]


def test_whitespace():
    print("test tokenize whitespace")
    tokens = tokenize("1 +\t2  \n*    3")
    assert [token["tag"] for token in tokens] == [
        "number",
        "+",
        "number",
        "*",
        "number",
        None,
    ]


def test_error():
    print("test tokenize error")
    try:
        tokenize("1@@@")
    except SyntaxError as error:
        assert str(error) == "Unexpected character: '@'"
    else:
        raise Exception("Expected SyntaxError")


def test_unterminated_string():
    # ===== CHAPTER 3 TEST =====
    print("test unterminated string")
    try:
        tokenize('"never closed')
    except SyntaxError as error:
        assert str(error) == "Unexpected character: '\"'"
    else:
        raise Exception("Expected SyntaxError")


if __name__ == "__main__":
    test_digits()
    test_floats()
    test_strings()
    test_string_escapes()
    test_operators()
    test_keywords()
    test_expressions()
    test_identifiers()
    test_whitespace()
    test_error()
    test_unterminated_string()
    print("done.")
