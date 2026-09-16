import sys

from tokenizer import tokenize
from parser import parse
from evaluator import evaluate

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python runner.py <program>")
        sys.exit(1)
    program = sys.argv[1]
    if program.endswith((".t", ".v")):
        with open(program, "r") as f:
            program = f.read().strip()
    tokens = tokenize(program)
    ast = parse(tokens)
    evaluate(ast, {})
