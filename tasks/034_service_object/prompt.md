# Service object

A common Rails pattern is the **service object**: a plain Ruby class that
wraps one unit of business logic behind a `call` method.

Implement a `CartSummary` service object:

```ruby
class CartSummary
  def initialize(items)
  end

  def call
  end
end
```

- `items` is an array of hashes, each with `:price` (integer, in cents) and
  `:quantity` (integer).
- `call` returns a hash with two keys:
  - `:count` — the total quantity across all items,
  - `:subtotal` — the sum of `price * quantity` over all items.
- An empty cart returns `{ count: 0, subtotal: 0 }`.

Example:

```ruby
CartSummary.new([{ price: 100, quantity: 2 }, { price: 50, quantity: 3 }]).call
# => { count: 5, subtotal: 350 }
```
