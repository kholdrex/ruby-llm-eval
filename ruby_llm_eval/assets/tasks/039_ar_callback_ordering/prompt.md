# Normalize before validating

You are writing a Rails model. ActiveRecord is available (no need to require it).
A `users` table exists with an `email` (string) column.

Implement a `User` model that:

- **normalizes** `email` by stripping surrounding whitespace and downcasing it,
- validates that `email` is **present**,
- validates that `email` is **unique**.

```ruby
class User < ActiveRecord::Base
end
```

The normalization must happen **before validation runs**, so that uniqueness is
enforced on the normalized value. Concretely: if a user with email
`"foo@example.com"` already exists, then building a user with email
`"FOO@EXAMPLE.COM"` (or `"  foo@example.com  "`) must be **invalid** — it is the
same email once normalized.
