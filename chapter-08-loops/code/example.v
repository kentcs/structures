print("Chapter 8: Loops");

// A basic counter loop, tested for zero and multiple iterations.
i = 0;
while (i < 3) {
    print(i);
    i = i + 1;
};
print(i);

// A false initial condition: the body never runs at all.
never = 0;
while (false) {
    never = 99;
};
print(never);

// Accumulating a sum, then building a string through concatenation.
n = 5;
sum = 0;
k = 1;
while (k <= n) {
    sum = sum + k;
    k = k + 1;
};
print(sum);

letters = "";
j = 0;
while (j < 3) {
    letters = letters + "x";
    j = j + 1;
};
print(letters);

// break finishes the nearest loop; later work in the same loop is skipped.
found = 0;
search = 0;
while (true) {
    search = search + 1;
    if (search == 4) {
        break;
    };
    found = search;
};
print(found);
print(search);

// continue skips the rest of this iteration and returns to the condition.
// It performs no implicit update: the counter still advances on its own.
total = 0;
m = 0;
while (m < 5) {
    m = m + 1;
    if (m == 3) {
        continue;
    };
    total = total + m;
};
print(total);

// Nested loops: an inner break only ends the inner loop. The outer loop
// still has more work to do afterward.
outer = 0;
combined = 0;
while (outer < 2) {
    outer = outer + 1;
    inner = 0;
    while (true) {
        inner = inner + 1;
        if (inner == 2) {
            break;
        };
        combined = combined + 1;
    };
    combined = combined + 10;
};
print(combined);

// exit propagates outward through a loop instead of being consumed like
// break: the loop does not own it, and the print below never runs.
attempt = 0;
while (attempt < 10) {
    attempt = attempt + 1;
    assert attempt < 3, "attempt should stay below 3";
};
print("This statement must not run");
