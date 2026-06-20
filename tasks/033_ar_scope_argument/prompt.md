# Scope with arguments

You are writing a Rails model. ActiveRecord is available (no need to require it).
A `listings` table exists with columns `title` (string) and `price` (integer).

Implement a `Listing` model with a scope `priced_between` that takes a low and a
high bound (both **inclusive**) and returns the listings whose `price` falls in
that range:

```ruby
class Listing < ActiveRecord::Base
  # scope :priced_between, ->(low, high) { ... }
end
```

It must be a real, chainable scope, so `Listing.priced_between(50, 100).order(:price)`
works.
