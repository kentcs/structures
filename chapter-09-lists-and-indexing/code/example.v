print("Chapter 9: Lists and Indexing");

// Empty and nonempty lists, including mixed element types.
empty = [];
print(length(empty));
mixed = [1, "two", true];
print(mixed);

// Reading by index. The index is a position; the element is what lives there.
numbers = [10, 20, 30];
print(numbers[1]);

// Traversal with while and length.
values = [3, 1, 4, 1, 5, 9];
total = 0;
i = 0;
while (i < length(values)) {
    total = total + values[i];
    i = i + 1;
};
print(total);

// Indexed assignment modifies an element in place.
scores = [70, 80, 90];
scores[0] = 75;
print(scores);

// Mutation vs rebinding: an alias sees a mutation, but not a rebind.
original = [1, 2, 3];
alias = original;
alias[0] = 99;
print(original);
original = [7, 8, 9];
print(alias);

// Nested lists and chained indexing.
matrix = [[1, 2], [3, 4], [5, 6]];
print(matrix[1][0]);
matrix[1][0] = 30;
print(matrix);

// Whole-number floats are valid indices; fractional ones are not.
print(numbers[1.0]);

// Comparing whole lists: structural equality, not identity, and still
// consistent with Vertex's scalar rule that true is never equal to 1.
print([1, 2] == [1, 2]);
print([true] == [1]);

// Concatenation builds a new list; the originals are untouched.
first = [1, 2];
second = [3, 4];
combined = first + second;
combined[0] = 99;
print(first);
print(combined);

// exit still propagates through every new position: a list element, an
// index base, an index, and an indexed assignment's right-hand value.
// Inject it into the value this time; the list must stay unmutated.
guard = [1, 2, 3];
guard[0] = exit(3);
print("This statement must not run");
