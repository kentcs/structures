import sys

from evaluator import evaluate_source


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python runner.py <program>")
        sys.exit(1)

    program = sys.argv[1]
    source_path = None
    if program.endswith((".t", ".v")):
        source_path = program
        with open(program, "r", encoding="utf-8") as source_file:
            program = source_file.read().strip()

    (value, status), _ = evaluate_source(program, source_path=source_path)
    if status == "exit":
        # Keep process termination outside the recursive evaluator.
        sys.exit(value)
    if status is not None:
        raise ValueError(f"Unhandled evaluation status: {status}")
