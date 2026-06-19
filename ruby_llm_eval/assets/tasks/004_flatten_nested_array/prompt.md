# Flatten a nested array

Implement a method with this exact signature:

```ruby
def flatten_deep(arr)
end
```

Return a new, fully flattened array containing every non-array element of
`arr`, in order, regardless of how deeply the arrays are nested. The input is
not modified.

Examples:

```ruby
flatten_deep([1, [2, [3, [4]]]]) # => [1, 2, 3, 4]
flatten_deep([[1], [2], [3]])    # => [1, 2, 3]
flatten_deep([])                 # => []
```
