# Roman numeral to integer

Implement a method with this exact signature:

```ruby
def roman_to_integer(s)
end
```

Convert the Roman numeral string `s` to its integer value. The symbols are:

```
I = 1    V = 5    X = 10    L = 50
C = 100  D = 500  M = 1000
```

Numerals are written largest to smallest, except for the six subtractive
combinations (`IV`, `IX`, `XL`, `XC`, `CD`, `CM`), where a smaller symbol before
a larger one is subtracted. Input is always a valid Roman numeral.

Examples:

```ruby
roman_to_integer("IV")      # => 4
roman_to_integer("LVIII")   # => 58
roman_to_integer("MCMXCIV") # => 1994
```
