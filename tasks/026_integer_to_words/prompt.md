# Integer to English words

Implement a method with this exact signature:

```ruby
def to_words(number)
end
```

Convert a non-negative integer (`0` to `2_147_483_647`) to its English words,
returning a lowercase `String`.

Rules:

- `0` is `"zero"`.
- Use the scale words `thousand`, `million`, `billion`.
- Join groups and words with single spaces.
- Compound tens use a hyphen: `21` is `"twenty-one"`, `45` is `"forty-five"`.
- Do **not** use the word "and".
- No leading, trailing, or double spaces.

Examples:

```ruby
to_words(0)          # => "zero"
to_words(21)         # => "twenty-one"
to_words(100)        # => "one hundred"
to_words(123)        # => "one hundred twenty-three"
to_words(1_234_567)  # => "one million two hundred thirty-four thousand five hundred sixty-seven"
```
