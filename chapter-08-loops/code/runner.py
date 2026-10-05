import sys

from evaluator import evaluate
from parser import parse
from tokenizer import tokenize


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python runner.py <program>")
        sys.exit(1)

    program = sys.argv[1]
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
