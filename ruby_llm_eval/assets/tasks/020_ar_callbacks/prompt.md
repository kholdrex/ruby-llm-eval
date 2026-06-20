# ActiveRecord callbacks

You are writing a Rails model. ActiveRecord is available (no need to require it),
and an `accounts` table already exists with these columns:

| column  | type   |
| ------- | ------ |
| `name`  | string |
| `email` | string |

Implement an `Account` model with a callback that **normalizes the email before
the record is saved**: strip leading/trailing whitespace and downcase it.

```ruby
class Account < ActiveRecord::Base
  # before_save callback that normalizes email
end
```

So saving an account with email `"  Foo@Example.COM "` stores
`"foo@example.com"`.
