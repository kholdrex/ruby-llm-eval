# Two Sum

Implement a method with this exact signature:

```ruby
def two_sum(nums, target)
end
```

Given an array of integers `nums` and an integer `target`, return the indices
of the two numbers that add up to `target`, as a two-element array
`[i, j]` with `i < j`. You may assume there is **at most one** such pair.

- If a pair exists, return its indices in ascending order.
- If no pair exists, return `nil`.
- You may not use the same element twice.

Examples:

```ruby
two_sum([2, 7, 11, 15], 9) # => [0, 1]
two_sum([3, 2, 4], 6)      # => [1, 2]
two_sum([1, 2, 3], 100)    # => nil
```
