# Safe search

You are writing a Rails model. ActiveRecord is available (no need to require it).
A `users` table exists with a `name` (string) column.

Implement a `User.search(query)` class method that returns the users whose
`name` **contains** `query` as a substring (a `LIKE '%query%'` match).

```ruby
class User < ActiveRecord::Base
  def self.search(query)
  end
end
```

`query` comes from untrusted user input, so it must be handled **safely**: a
malicious `query` must not be able to change the SQL. Treat the whole `query`
as a literal value to match against, never as SQL.

For example, searching for `"' OR '1'='1"` must return only users whose name
literally contains that text (normally none) — not every user.
