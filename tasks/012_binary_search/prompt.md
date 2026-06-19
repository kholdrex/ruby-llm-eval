# Binary search

Implement a method with this exact signature:

```ruby
def binary_search(sorted, target)
end
```

`sorted` is an array of integers in ascending order. Return the index of
`target` in `sorted`, or `nil` if it is not present. Run in O(log n) time
(use binary search, not a linear scan).

Examples:

```ruby
binary_search([1, 3, 5, 7, 9], 7) # => 3
binary_search([1, 3, 5, 7, 9], 4) # => nil
binary_search([], 1)              # => nil
```
