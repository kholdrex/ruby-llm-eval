# Run-length encoding

Implement a method with this exact signature:

```ruby
def run_length_encode(str)
end
```

Compress `str` by replacing each run of one or more identical consecutive
characters with that character followed by the length of the run.

- The empty string encodes to the empty string.
- A run of length 1 is still written with its count (`"a"` → `"a1"`).

Examples:

```ruby
run_length_encode("aaabbc") # => "a3b2c1"
run_length_encode("wwww")   # => "w4"
run_length_encode("aba")    # => "a1b1a1"
```
