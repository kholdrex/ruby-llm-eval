# Spreadsheet column titles

Spreadsheet columns are labelled `A, B, ... Z, AA, AB, ... AZ, BA, ...`. This is
a **bijective base-26** system: `A = 1`, `Z = 26`, `AA = 27`, `AZ = 52`,
`BA = 53`, and so on (there is no "zero" digit).

Implement **both** of these methods with these exact signatures:

```ruby
def column_to_number(title)   # "A" => 1, "ZY" => 701
end

def number_to_column(number)  # 1 => "A", 701 => "ZY"
end
```

- `column_to_number` takes an uppercase column title and returns its 1-based
  number.
- `number_to_column` takes a positive integer and returns its column title.
- They are inverses of each other for all positive integers.
