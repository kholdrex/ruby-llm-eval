# Caesar cipher

Implement a method with this exact signature:

```ruby
def caesar_cipher(str, shift)
end
```

Return `str` with every alphabetic character shifted forward by `shift`
positions in the alphabet, wrapping around (`z` + 1 → `a`).

- Preserve case: letters stay the same case after shifting.
- Leave non-letters (spaces, punctuation, digits) unchanged.
- `shift` may be `0`, larger than 26, or negative.

Examples:

```ruby
caesar_cipher("abc", 1)            # => "bcd"
caesar_cipher("Hello, World!", 3)  # => "Khoor, Zruog!"
caesar_cipher("abc", -2)           # => "yza"
```
