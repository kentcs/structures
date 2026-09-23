print("Chapter 4: Booleans and Comparisons");
ready = true;
print(ready);
print(false);

// Supplied input and numeric conversion still work without a keyboard read.
__input = "21";
answer = number(input()) * 2;
print(answer == 42);
print(answer != 42);
print(-1.5 < .5);
print(answer <= 42.0);
print(answer > 40 + 1);
print(answer >= 43);

// String equality and boolean results are ordinary expression values.
print("ha" * 2 == "haha");
print("dog" != "cat");
same = (answer == 42) == ready;
print(same);
saved = __output;
print("Captured: " + saved);
print("Input cleared: [" + __input + "]");
print("Answer: " + string(answer));

// Conversions are explicit; type reports Vertex's three value families.
print(string(true));
print(number(true));
print(boolean(0));
print(boolean(" FALSE "));
print(type(answer));
print(type("42"));
print(type(answer == 42));
print("Accepted: " + string(boolean(-2)));
