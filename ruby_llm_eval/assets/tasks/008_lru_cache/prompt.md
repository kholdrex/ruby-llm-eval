# LRU cache

Implement a class with this exact interface:

```ruby
class LRUCache
  def initialize(capacity)
  end

  def get(key)
  end

  def put(key, value)
  end
end
```

Build a fixed-capacity **Least Recently Used** cache:

- `initialize(capacity)` sets the maximum number of entries (a positive integer).
- `get(key)` returns the value for `key`, or `nil` if it is not present.
- `put(key, value)` inserts or updates the value for `key`.
- Both `get` and `put` count as "using" a key (making it most recently used).
- When inserting a new key would exceed `capacity`, evict the
  **least recently used** key first.

Example:

```ruby
cache = LRUCache.new(2)
cache.put(1, 1)
cache.put(2, 2)
cache.get(1)    # => 1
cache.put(3, 3) # evicts key 2
cache.get(2)    # => nil
```
