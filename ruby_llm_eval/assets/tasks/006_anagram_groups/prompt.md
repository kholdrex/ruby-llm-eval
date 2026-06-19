# Group anagrams

Implement a method with this exact signature:

```ruby
def anagram_groups(words)
end
```

Group the input `words` so that words which are anagrams of one another end up
in the same group. Return an array of groups.

To keep the output deterministic:

- sort the words **within** each group in ascending (alphabetical) order, and
- sort the **groups** by their first element, ascending.

Example:

```ruby
anagram_groups(%w[eat tea tan ate nat bat])
# => [["ate", "eat", "tea"], ["bat"], ["nat", "tan"]]
```
