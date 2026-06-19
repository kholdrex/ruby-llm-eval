# Balanced brackets

Implement a method with this exact signature:

```ruby
def balanced?(str)
end
```

Return `true` if every bracket in `str` is correctly matched and nested, and
`false` otherwise. The three bracket pairs are `()`, `[]`, and `{}`.

- Any non-bracket characters are ignored.
- The empty string is balanced.
- Brackets must close in the right order: `"([)]"` is **not** balanced.

Examples:

```ruby
balanced?("()[]{}")  # => true
balanced?("{[]}")    # => true
balanced?("([)]")    # => false
balanced?("a(b)c")   # => true
```
