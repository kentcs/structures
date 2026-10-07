import sys

from evaluator import evaluate
from parser import parse
from tokenizer import tokenize


def run(program):
    if program.endswith((".t", ".v")):
        with open(program, "r") as source_file:
            program = source_file.read().strip()

    tokens = tokenize(program)
    ast = parse(tokens)
    value, status = evaluate(ast, {})
    if status == "exit":
        # Keep process termination outside the recursive evaluator.
        sys.exit(value)
    if status is not None:
        raise ValueError(f"Unhandled evaluation status: {status}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python runner.py <program>", file=sys.stderr)
        sys.exit(1)

    # Report a Vertex program's mistakes as one line, not a Python traceback.
    # Anything else is a bug in the interpreter and keeps its traceback.
    try:
        run(sys.argv[1])
    except SyntaxError as error:
        print(f"Syntax error: {error}", file=sys.stderr)
        sys.exit(1)
    except OSError as error:
        print(f"Cannot read {sys.argv[1]}: {error.strerror}", file=sys.stderr)
        sys.exit(1)
    except (TypeError, ValueError, ZeroDivisionError, EOFError) as error:
        print(f"Runtime error: {error}", file=sys.stderr)
        sys.exit(1)
