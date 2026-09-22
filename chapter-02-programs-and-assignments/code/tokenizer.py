import re
from pprint import pprint

# p = re.compile("ab*")

# if p.match("abbbbbbb") :
#     print("match")
# else:
#     print("not match")

patterns = [
    (r"\s+", "whitespace"),
    (r"//[^\r\n]*", "comment"),
    (r"\d*\.\d+|\d+\.\d*|\d+", "number"),
    (r"\+", "+"),
    (r"\-", "-"),
    (r"\/", "/"),
    (r"\*", "*"),
    (r"\(", "("),
    (r"\)", ")"),
    (r"\=", "="),
    (r"\;", ";"),
    (r"print\b", "print"),
    (r"[a-zA-Z_][\w]*", "identifier"),
    (r".", "error"),
]

patterns = [(re.compile(p), tag) for p, tag in patterns]


def tokenize(characters):
    "Tokenize a string using the patterns above"
    tokens = []
    position = 0
    line = 1
    column = 1
    current_tag = None

    while position < len(characters):
        for pattern, tag in patterns:
            match = pattern.match(characters, position)
            if match:
                current_tag = tag
                break
        assert match is not None
        value = match.group(0)

        if current_tag == "error":
            raise Exception(f"Unexpected character: {value!r}")

        if current_tag not in ("whitespace", "comment"):
            token = {"tag": current_tag, "line": line, "column": column}
            if current_tag == "number":
                if "." in value:
                    token["value"] = float(value)
                else:
                    token["value"] = int(value)
            if current_tag == "identifier":
                token["value"] = value
            tokens.append(token)

        # advance position and update line/column
        for ch in value:
            if ch == "\n":
                line += 1
                column = 1
            else:
                column += 1
        position = match.end()

    tokens.append({"tag": None, "line": line, "column": column})
    return tokens


def test_digits():
    print("test tokenize digits")
    t = tokenize("123")
    assert t[0]["tag"] == "number"
    assert t[0]["value"] == 123
    assert t[1]["tag"] is None
    t = tokenize("1")
    assert t[0]["tag"] == "number"
    assert t[0]["value"] == 1
    assert t[1]["tag"] is None


def test_floats():
    print("test tokenize floats")
    for text, expected in [("1.5", 1.5), (".5", 0.5), ("5.", 5.0)]:
        t = tokenize(text)
        assert t[0]["tag"] == "number"
        assert t[0]["value"] == expected
        assert t[1]["tag"] is None


def test_operators():
    print("test tokenize operators")
    t = tokenize("+ - * / ( ) = ;")
    tags = [tok["tag"] for tok in t]
    assert tags == ["+", "-", "*", "/", "(", ")", "=", ";", None]


def test_keywords():
    print("test tokenize keywords")
    t = tokenize("print")
    tags = [tok["tag"] for tok in t]
    assert tags == ["print", None]


def test_identifiers():
    print("test tokenize identifiers")
    t = tokenize("foo bar baz")
    tags = [tok["tag"] for tok in t]
    assert tags == ["identifier", "identifier", "identifier", None]
    assert t[0]["value"] == "foo"
    assert t[2]["value"] == "baz"


def test_expressions():
    print("test tokenize expressions")
    t = tokenize("1+222*3")
    assert t[0]["tag"] == "number" and t[0]["value"] == 1
    assert t[1]["tag"] == "+"
    assert t[2]["tag"] == "number" and t[2]["value"] == 222
    assert t[3]["tag"] == "*"
    assert t[4]["tag"] == "number" and t[4]["value"] == 3
    assert t[5]["tag"] is None


def test_whitespace():
    print("test tokenize whitespace")
    t = tokenize("1 +\t2  \n*    3")
    assert t[0]["tag"] == "number" and t[0]["value"] == 1
    assert t[1]["tag"] == "+"
    assert t[2]["tag"] == "number" and t[2]["value"] == 2
    assert t[3]["tag"] == "*"
    assert t[4]["tag"] == "number" and t[4]["value"] == 3
    assert t[5]["tag"] is None


def test_comments():
    print("test tokenize comments")
    for ending in ("\n", "\r\n", "\r"):
        tokens = tokenize("8// ignored @ ; /" + ending + "/2")
        assert [token["tag"] for token in tokens] == ["number", "/", "number", None]
        assert tokens[0]["value"] == 8
        assert tokens[2]["value"] == 2
    for source in ("//", "// comment at end", "8 // trailing comment"):
        tokens = tokenize(source)
        assert [token["tag"] for token in tokens] == (
            ["number", None] if source.startswith("8") else [None]
        )
        assert tokens[-1]["column"] == len(source) + 1
    tokens = tokenize("// first\n  8// second\r\n /2")
    assert (tokens[0]["line"], tokens[0]["column"]) == (2, 3)
    assert (tokens[1]["line"], tokens[1]["column"]) == (3, 2)
    assert [token["tag"] for token in tokenize("8/2")] == ["number", "/", "number", None]
    assert [token["tag"] for token in tokenize("/ /")] == ["/", "/", None]


def test_error():
    print("test tokenize error")
    try:
        t = tokenize("1@@@ +\t2  \n*    3")
    except Exception as e:
        assert str(e) == "Unexpected character: '@'"
        return
    assert Exception("Error did not happen.")


if __name__ == "__main__":
    test_digits()
    test_floats()
    test_operators()
    test_keywords()
    test_expressions()
    test_identifiers()
    test_whitespace()
    test_comments()
    test_error()
    print("done.")
