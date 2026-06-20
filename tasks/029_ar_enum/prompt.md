# ActiveRecord enum

You are writing a Rails model. ActiveRecord is available (no need to require it).
An `orders` table exists with a `status` column (integer).

Implement an `Order` model with a `status` enum that maps:

- `pending` → `0`
- `shipped` → `1`
- `delivered` → `2`

```ruby
class Order < ActiveRecord::Base
  # status enum
end
```

This must give you the usual enum helpers:

- predicate methods: `order.pending?`, `order.shipped?`, …
- bang methods that persist: `order.shipped!`
- class scopes: `Order.shipped`, `Order.pending`
- `order.status` returns the string name (e.g. `"pending"`).
