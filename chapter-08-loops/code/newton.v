// Newton's method for square roots, using only what exists through
// Chapter 8: numbers, arithmetic, comparisons, assignment, print, while,
// break, and assert. There are no functions yet (a later chapter), so the
// same computation is written out twice below, once per input value,
// instead of being wrapped in something reusable.
//
// The idea: to approximate sqrt(S), start from any positive guess and
// repeatedly replace it with the average of the guess and S / guess.
//     next_guess = (guess + S / guess) / 2
// Each pass gets roughly twice as many correct digits as the one before,
// so a handful of iterations is enough for ordinary precision.

print("Newton's method for square roots");

// ===== First example: S = 2 (an irrational root) =====

S = 2;
guess = S;              // any positive starting guess works; S itself is easy
epsilon = 0.0000001;    // stop once consecutive guesses are this close
iteration = 0;
maxIterations = 100;    // a safety cap so a mistake here cannot loop forever

while (true) {
    previous = guess;
    guess = (guess + S / guess) / 2;
    iteration = iteration + 1;

    // Vertex has no abs() yet, so the difference is unsigned by hand.
    difference = guess - previous;
    if (difference < 0) {
        difference = -difference;
    };

    print("  guess after iteration " + string(iteration) + ": " + string(guess));

    if (difference < epsilon) {
        break;
    };
    if (iteration >= maxIterations) {
        break;
    };
};

print("Square root of " + string(S) + " is approximately " + string(guess));

// Check the answer the same way it was derived: squaring it should land
// back close to S. "Close" still means within epsilon, not exact equality,
// since Newton's method (like almost all floating-point computation) only
// ever produces an approximation.
check = guess * guess;
error = check - S;
if (error < 0) {
    error = -error;
};
assert error < epsilon, "squaring the result should return close to S";
print("Check: " + string(guess) + " * " + string(guess) + " = " + string(check));

// ===== Second example: S = 16 (a perfect square) =====
// Same computation, same variable names, reused now that the first
// example is finished with them. There is no scoping yet either, so this
// really is the same environment, not a fresh copy of it.

S = 16;
guess = S;
iteration = 0;

while (true) {
    previous = guess;
    guess = (guess + S / guess) / 2;
    iteration = iteration + 1;

    difference = guess - previous;
    if (difference < 0) {
        difference = -difference;
    };

    print("  guess after iteration " + string(iteration) + ": " + string(guess));

    if (difference < epsilon) {
        break;
    };
    if (iteration >= maxIterations) {
        break;
    };
};

print("Square root of " + string(S) + " is approximately " + string(guess));

check = guess * guess;
error = check - S;
if (error < 0) {
    error = -error;
};
assert error < epsilon, "squaring the result should return close to S";
print("Check: " + string(guess) + " * " + string(guess) + " = " + string(check));
