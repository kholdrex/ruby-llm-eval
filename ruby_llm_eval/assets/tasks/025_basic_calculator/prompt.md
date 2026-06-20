# Basic calculator

Implement a method with this exact signature:

```ruby
def calculate(expression)
end
```

Evaluate the arithmetic `expression` (a `String`) and return the integer result.
You must **not** use `eval`.

The expression contains only:

- non-negative integer literals,
- the binary operators `+`, `-`, `*`, `/`,
- parentheses `(` and `)`,
- and spaces (ignore them).

Rules:

- Standard precedence: `*` and `/` bind tighter than `+` and `-`; parentheses
  override precedence; operators of equal precedence are left-associative.
- There is no unary minus — negative values arise only from subtraction.
- **Integer division truncates toward zero** (so `(0 - 9) / 4 == -2`, not `-3`).
- The expression is always valid and never divides by zero.

Examples:

```ruby
calculate("3+2*2")                      # => 7
calculate("(1+(4+5+2)-3)+(6+8)")        # => 23
calculate("14/3*2")                     # => 8
calculate("(0-9)/4")                    # => -2
```
