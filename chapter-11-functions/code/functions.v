// A function literal is a value, like any other. The named form below is
// sugar for assigning one of these to a name.
double = function(x) { return x + x };
print(double(21));

// The named form: identical to the line above, just shorter to write.
function triple(x) { return x + x + x };
print(triple(7));

// An anonymous function expression called the moment it is written, with
// no parentheses needed around it: it is already a factor, and (5) is
// just a call suffix applied to it, the same as any other factor.
function(a) { print(a * 2) }(5);

// Different arities, and a function body with its own local variable.
function average(a, b, c) {
    total = a + b + c;
    return total / 3;
};
print(average(2, 4, 9));

// Falling off the end, and a bare return, both leave the result null.
function sideEffectOnly() { print("ran with no return value") };
print(sideEffectOnly());

// Recursion needs no special support: a call's new environment chains
// back to wherever it was called from, and that chain eventually reaches
// wherever the function's own name was bound, however many calls deep.
function factorial(n) {
    if (n == 0) { return 1 };
    return n * factorial(n - 1);
};
print(factorial(6));

// Calls nest freely inside larger expressions, the same as any other value.
function square(x) { return x * x };
print(1 + square(3) + 1);

// A function that returns a boolean, used directly as a condition.
function isPositive(x) { return x > 0 };
if (isPositive(5)) {
    print("5 is positive");
} else {
    print("5 is not positive");
};

// A call's result can be indexed, accessed by field, or called again
// immediately, the same chain [] and . already allowed.
function pair() { return [10, 20] };
print(pair()[1]);
function record() { return {"value": 99} };
print(record().value);
function makeAdder() { return function(a, b) { return a + b } };
print(makeAdder()(3, 4));

// Dynamic scoping: showGreeting does not declare greeting itself. It
// reads whatever greeting happens to be bound to wherever it is called
// from -- not wherever it was defined, which is a separate function with
// no greeting of its own at all.
function showGreeting() { print(greeting) };
function englishCaller() { greeting = "Hello"; showGreeting() };
function frenchCaller() { greeting = "Bonjour"; showGreeting() };
englishCaller();
frenchCaller();

// Assignment is an expression now, right-associative and chainable: this
// assigns 5 to b first, and that assignment's own value, 5, to a.
a = b = 5;
print(a);
print(b);

// Any expression may stand alone as a statement, including one with no
// effect at all. This line computes 1 + 1 and discards it; legal, just
// useless, the same as in most other languages.
1 + 1;

// null is a value like any other: printable, comparable, storable.
print(null);
print(null == null);
print(type(null));
print(type(double));

// exit still propagates outward through a call, unconsumed, the same as
// it already propagated through every earlier chapter's constructs. A
// function's own exit can now escape from deep inside a larger expression
// too, the same way any other status does -- exit itself still cannot
// nest, but a call can, and a call is all it takes: the promise an
// earlier chapter made before functions existed, now kept.
numbers = [10, 20, 30];
function stopAt(code) { exit(code); };
print(numbers[stopAt(5)]);
print("This statement must not run");
