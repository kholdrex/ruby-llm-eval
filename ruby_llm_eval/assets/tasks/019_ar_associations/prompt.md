# ActiveRecord associations

You are writing Rails models. ActiveRecord is available (no need to require it),
and two tables already exist:

`authors`

| column | type   |
| ------ | ------ |
| `name` | string |

`books`

| column      | type    |
| ----------- | ------- |
| `title`     | string  |
| `author_id` | integer |

Implement two models so that **an author has many books** and **a book belongs
to an author**:

```ruby
class Author < ActiveRecord::Base
  # ...
end

class Book < ActiveRecord::Base
  # ...
end
```

After this, `author.books` returns that author's books, and `book.author`
returns the book's author.
