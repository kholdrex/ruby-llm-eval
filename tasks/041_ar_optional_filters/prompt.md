# Optional search filters

You are writing a Rails model. ActiveRecord is available (no need to require it).
A `products` table exists with `name` (string) and `price` (integer) columns.

Implement `ProductSearch.call(name: nil, max_price: nil)` that returns an array
of `{ name:, price: }` hashes for the matching products, ordered by `price`
ascending. Both arguments are **optional**:

- `name` — when given and non-empty, keep only products whose `name` contains it
  as a substring (a safe `LIKE` match). When `nil` or empty, do not filter by
  name.
- `max_price` — when given, keep only products with `price <= max_price`. When
  `nil`, do not filter by price.
- When **both** are omitted, return **all** products (ordered by price).
- When both are given, apply both (AND).

```ruby
module ProductSearch
  def self.call(name: nil, max_price: nil)
  end
end
```
