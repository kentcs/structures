// Chapter 1: Numbers and Arithmetic - Test Suite

print("Chapter 1: Numbers and Arithmetic");

print "Testing basic numbers...";
x = 1;
assert x == 1;

x = -123.456;
assert x == -123.456;

print "Testing arithmetic operations...";

// addition
assert 1+2 == 3;

// subtraction  
assert 4-1 == 3;

// multiplication
assert 4 * 5 == 20;
assert 0.4 * 5 == 2.0;

// division
assert 6/2 == 3;
assert 5.5 / 0.5 == 11.0;

// operator precedence
assert 2+3*4 == 14;
assert (2+3)*4 == 20;

// negation
assert -5 == 0-5;

print "Chapter 1 tests completed.";
