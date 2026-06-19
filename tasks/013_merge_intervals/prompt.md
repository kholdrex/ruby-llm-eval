# Merge intervals

Implement a method with this exact signature:

```ruby
def merge_intervals(intervals)
end
```

`intervals` is an array of `[start, finish]` integer pairs. Merge all
overlapping intervals and return the result as an array of `[start, finish]`
pairs sorted by `start`. Intervals that merely touch (e.g. `[1, 4]` and
`[4, 5]`) count as overlapping and should merge.

Examples:

```ruby
merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]])
# => [[1, 6], [8, 10], [15, 18]]

merge_intervals([[1, 4], [4, 5]]) # => [[1, 5]]
merge_intervals([])               # => []
```
