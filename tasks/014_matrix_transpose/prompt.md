# Transpose a matrix

Implement a method with this exact signature:

```ruby
def transpose(matrix)
end
```

`matrix` is an array of rows, where every row is an array of equal length.
Return its transpose: a new matrix whose rows are the columns of the input.
Return `[]` for an empty matrix. Do not modify the input.

Examples:

```ruby
transpose([[1, 2, 3], [4, 5, 6]]) # => [[1, 4], [2, 5], [3, 6]]
transpose([[1], [2], [3]])        # => [[1, 2, 3]]
transpose([])                     # => []
```
