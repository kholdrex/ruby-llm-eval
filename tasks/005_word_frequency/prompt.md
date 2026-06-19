# Word frequency

Implement a method with this exact signature:

```ruby
def word_frequency(text)
end
```

Return a `Hash` mapping each word in `text` to the number of times it appears.

- A "word" is a maximal run of alphanumeric characters (`a-z`, `0-9`).
- Matching is **case-insensitive**: count words in lowercase.
- Everything else (spaces, punctuation, newlines) separates words.
- For empty input, return an empty hash.

Example:

```ruby
word_frequency("The cat sat on the mat. The cat!")
# => { "the" => 3, "cat" => 2, "sat" => 1, "on" => 1, "mat" => 1 }
```
