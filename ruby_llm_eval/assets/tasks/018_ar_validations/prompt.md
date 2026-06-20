# ActiveRecord validations

You are writing a Rails model. ActiveRecord is available (no need to require it),
and a `users` table already exists with these columns:

| column  | type    |
| ------- | ------- |
| `name`  | string  |
| `email` | string  |
| `age`   | integer |

Implement a `User` model that validates:

- `name` is **present**.
- `email` is **present** and **unique**.
- `age` is an **integer** that is **18 or greater**.

```ruby
class User < ActiveRecord::Base
  # validations here
end
```

A record that violates any rule must be invalid (`user.valid?` returns `false`),
and a duplicate email must put `"has already been taken"` in
`user.errors[:email]`.
