<p class="eyebrow">Structure of Programming Languages / Chapter 00</p>

<div class="rule"></div>

# What Is a<br />Programming Language?

<p class="subtitle">Before building Vertex, decide what kind of thing a language is and what it takes to make one run.</p>

Note:
Open with the difference between knowing how to write programs and knowing what makes a programming language work.

---

<p class="eyebrow">01 / Shared rules</p>

## A token matters because people agree on what it means.

> A light, gesture, word, or keyword becomes part of a language when it stands for something beyond itself.

<div class="callout">The raw token is not the interesting part. The shared rule that connects it to meaning is.</div>

<p class="caption">Traffic lights and referee signals are familiar languages: shared forms, shared meanings, real consequences.</p>

Note:
Use traffic lights or referee signals briefly. The point is the shared rule system, not the analogy itself.

---

<p class="eyebrow">02 / Two questions</p>

## Every language needs syntax and semantics.

<div class="compare">
<div>
<h3>Syntax</h3>
<p>Which programs are <strong>well-formed</strong>?</p>

```vertex
x = 1 + 2;
print x;
```
</div>
<div>
<h3>Semantics</h3>
<p>What do those programs <strong>do</strong>?</p>

```text
1 + 2  ->  3
x      ->  3
print  ->  3
```
</div>
</div>

<div class="callout">A parser can determine whether a program has legal form. It cannot, by itself, give that form behavior.</div>

Note:
Syntax is legal form. Semantics is interpreted behavior. Parsing is not execution.

---

<p class="eyebrow">03 / A program changes form</p>

## Text becomes structure before it becomes behavior.

<div class="pipeline">
<div class="box">Program<br />text</div><span class="arrow">-></span>
<div class="box">Tokens</div><span class="arrow">-></span>
<div class="box">Parse tree<br />or AST</div><span class="arrow">-></span>
<div class="box">Evaluation<br />or execution</div><span class="arrow">-></span>
<div class="box">Values,<br />output, effects</div>
</div>

<p class="caption">Each stage solves a different problem. A flaw in one stage can make the whole language behave strangely in its own special way.</p>

Note:
Walk left to right. This is the recurring architecture of the course.

---

<p class="eyebrow">04 / Structure records precedence</p>

## Parsing makes the meaning in text explicit.

<div class="compare">
<div>

```vertex
x = 1 + 2 * 3;
```
</div>
<div class="tree">assign
|- identifier: x
`- +
   |- number: 1
   `- *
      |- number: 2
      `- number: 3</div>
</div>

<div class="callout">The abstract syntax tree stores the fact that multiplication happens inside addition. Precedence is now data, not a guess from punctuation.</div>

Note:
An AST drops details such as whitespace because the evaluator does not need them. It keeps the structure that determines behavior.

---

<p class="eyebrow">05 / Realizing meaning</p>

## An evaluator runs the tree. A compiler translates it.

<div class="compare">
<div>
<h3>Evaluator / interpreter</h3>
<p>Walk the AST and produce behavior now.</p>
<p class="caption">What happens when this node runs?</p>
</div>
<div>
<h3>Compiler</h3>
<p>Translate the AST into another form for later execution.</p>
<p class="caption">How can this meaning be expressed elsewhere?</p>
</div>
</div>

<p class="caption">JIT compilation and transpilation are variations on the same theme: preserve meaning while changing when or where a program runs.</p>

Note:
Keep this high-level. Vertex uses an evaluator, but this contrast separates language design from implementation strategy.

---

<p class="eyebrow">06 / Programs remember</p>

## Variables require state, and state requires an environment.

<div class="compare">
<div>

```vertex
x = 10;
y = x + 5;
```
</div>
<div class="tree">environment
|- x -> 10
`- y -> 15</div>
</div>

<div class="callout">Later, local scopes, function calls, and closures turn this simple lookup table into a chain of related environments.</div>

Note:
Use x = x + 1 to point out that assignment updates program state. It is not an algebraic equation.

---

<p class="eyebrow">07 / Tests make promises</p>

## A test suite is part of the language specification.

```vertex
assert 2 + 3 * 4 == 14;
```

<div class="compare">
<div><h3>What it checks</h3><p>The implementation produces the expected result.</p></div>
<div><h3>What it defines</h3><p>Multiplication binds more tightly than addition in Vertex.</p></div>
</div>

Note:
Tests are executable statements of intended semantics, not cleanup after the implementation is done.

---

<p class="eyebrow">08 / The course method</p>

## Vertex grows in snapshots, one pressure point at a time.

<div class="timeline">
<div><b>Arithmetic</b>Expression parsing</div>
<div><b>Variables</b>An environment</div>
<div><b>Conditionals</b>Control-flow rules</div>
<div><b>Functions</b>Call frames and returns</div>
<div><b>Closures</b>Captured environments</div>
</div>

<p class="caption">Each new feature changes more than syntax. It creates new structural and semantic work in the implementation.</p>

Note:
Each chapter is a meaningful version of the language, not merely another feature list.

---

<p class="eyebrow">Chapter 00</p>

# Build the rules.<br />Then build the machine.

<div class="rule"></div>

## Next: give `2 + 3 * 4` the right structure and meaning.

Note:
Set up Chapter 01. The recurring course pattern is define syntax, define meaning, implement the machinery, and verify it with tests.
