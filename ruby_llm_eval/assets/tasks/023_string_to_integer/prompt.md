# String to integer (atoi)

Implement a method with this exact signature:

```ruby
def my_atoi(str)
end
```

Convert `str` to a 32-bit signed integer, following these rules in order:

1. Skip any leading spaces (`" "`).
2. Read an optional single `+` or `-` sign.
3. Read the following digits until a non-digit (or end of string); ignore the
   rest of the string.
4. If no digits were read, the result is `0`.
5. Clamp the result to the signed 32-bit range:
   `[-2_147_483_648, 2_147_483_647]`. Values below clamp to the minimum, values
   above clamp to the maximum.

Examples:

```ruby
my_atoi("42")                 # => 42
my_atoi("   -42")             # => -42
my_atoi("4193 with words")    # => 4193
my_atoi("words and 987")      # => 0
my_atoi("-91283472332")       # => -2147483648  (clamped)
```
