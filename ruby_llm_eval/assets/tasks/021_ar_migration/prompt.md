# ActiveRecord migration

You are writing a Rails database migration. ActiveRecord is available (no need to
require it). Implement a migration class named `CreateProducts` that inherits
from `ActiveRecord::Migration[7.2]` and, in its `change` method, creates a
`products` table with:

- `name` — a string column that is **not null**
- `price` — a decimal column
- an **index** on `name`

```ruby
class CreateProducts < ActiveRecord::Migration[7.2]
  def change
    # create_table :products ...
  end
end
```

The migration will be run with `CreateProducts.new.migrate(:up)` against a fresh
database.
