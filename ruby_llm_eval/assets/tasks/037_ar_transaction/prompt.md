# Atomic order placement

You are writing Rails code. ActiveRecord is available (no need to require it).
Two models are already defined for you:

- `Order` — has a `customer_name` (string) and `has_many :line_items`
- `LineItem` — has a `price` (integer), `belongs_to :order`, and **validates that
  `price` is greater than 0**

Implement a service that places an order with its line items **atomically**:

```ruby
class OrderPlacement
  def self.place(customer_name, item_prices)
  end
end
```

- Create one `Order` for `customer_name`, then a `LineItem` for each price in
  `item_prices`.
- If **any** line item is invalid (e.g. a non-positive price), the whole
  placement must roll back: **no `Order` and no `LineItem` may be left in the
  database.**
- On success, return the created order.

So `OrderPlacement.place("Ann", [10, -5, 20])` must leave the database exactly
as it was before the call.
