# Custom JSON serialization

You are writing a Rails model. ActiveRecord is available (no need to require it).
A `products` table exists with columns `name` (string) and `sku` (string).

By default a model serializes every column (including `id`). Override the
model's JSON representation so that `product.to_json` produces **exactly** these
two keys and nothing else:

- `"name"` — the product's name
- `"code"` — the product's `sku`

```ruby
class Product < ActiveRecord::Base
  # override as_json
end
```

Example:

```ruby
Product.new(name: "Widget", sku: "W-100").to_json
# => '{"name":"Widget","code":"W-100"}'
```
