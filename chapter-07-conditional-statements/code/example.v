print("Chapter 7: Conditional Statements");

// A single branch: only runs when the condition is true. An if statement
// still needs the usual ";" separator before the next statement, the same
// as any other statement.
if (true) {
    print("single branch runs");
};
if (false) {
    print("single branch is skipped");
};

// Two branches: exactly one of them runs.
grade = 72;
if (grade >= 90) {
    letter = "A";
} else {
    letter = "B or lower";
};
print(letter);

// This grammar has no "else if" shortcut. A chain is written as an else
// block containing its own nested if, with its own braces.
if (grade >= 90) {
    letter = "A";
} else {
    if (grade >= 80) {
        letter = "B";
    } else {
        if (grade >= 70) {
            letter = "C";
        } else {
            letter = "D or lower";
        };
    };
};
print(letter);

// A block can hold several statements.
if (true) {
    a = 1;
    b = 2;
    print(a + b);
};

// The branch not taken is never evaluated: no input read, no exit, no
// assertion failure, even though the code is right there in the source.
if (false) {
    stuck = exit(9) + number(input());
} else {
    print("unselected branch never touched exit or input");
};

// A status still escapes outward through nested conditionals, and it still
// stops whatever would have run after it, the same way it did in Chapter 6.
if (true) {
    if (true) {
        assert grade > 100, "grade should exceed 100";
    };
};
print("This statement must not run");
