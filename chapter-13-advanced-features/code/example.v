print("Chapter 13: Native Functions and Modules");
// Constructing a native function does not call its host implementation.
sqrt = native("math.sqrt", ["x"]);
distance = native("math.hypot", ["a", "b"]);
print(sqrt(9));
print(distance(3, 4));

// Native and Vertex functions use the same call syntax.
function apply(f, x) { return f(x) };
operations = {"sqrt": sqrt};
print(apply(operations.sqrt, 49));
print(type(sqrt));
print(copy(sqrt) == sqrt);

geometry = import("modules/geometry.v");
print(geometry.square(5));
print(geometry.sqrt(9));
print(geometry.scale(5));
geometry.factor = 3;
print(geometry.scale(5));
first = import("modules/counter.v");
second = import("modules/counter.v");
print(first.next());
print(first.next());
print(second.count);
