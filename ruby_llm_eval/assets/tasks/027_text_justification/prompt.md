# Full text justification

Implement a method with this exact signature:

```ruby
def justify(words, max_width)
end
```

Format `words` (an array of non-empty strings) into fully-justified lines and
return an array of strings, each **exactly** `max_width` characters long.

Rules:

- Pack as many words as fit on each line, greedily. Words on a line are
  separated by at least one space; no word exceeds `max_width`.
- Distribute extra spaces between words as evenly as possible. If the spaces
  don't divide evenly, the **left** gaps get one more space than the right ones.
- A line with a single word, and the **last** line, are **left-justified**:
  single spaces between words and the remaining width padded on the right.

Example (`max_width = 16`):

```ruby
justify(["This","is","an","example","of","text","justification."], 16)
# => ["This    is    an",
#     "example  of text",
#     "justification.  "]
```
