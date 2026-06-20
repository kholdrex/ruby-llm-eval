# Conditional validation

You are writing a Rails model. ActiveRecord is available (no need to require it).
A `subscriptions` table exists with columns `plan` (string) and `card_number`
(string).

Implement a `Subscription` model that requires `card_number` to be present
**only when** `plan` is `"paid"`. A subscription on any other plan (e.g.
`"free"`) is valid without a card number.

```ruby
class Subscription < ActiveRecord::Base
  # conditional presence validation
end
```

So a paid subscription without a card number is invalid, but a free one without
a card number is valid.
