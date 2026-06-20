# ActiveRecord scopes

You are writing a Rails model. ActiveRecord is available (no need to require it),
and an `articles` table already exists with these columns:

| column      | type    |
| ----------- | ------- |
| `title`     | string  |
| `published` | boolean |
| `views`     | integer |

Implement an `Article` model with this exact shape:

```ruby
class Article < ActiveRecord::Base
  # scope :published, ...
  # scope :popular, ...
end
```

- `Article.published` — only articles where `published` is true.
- `Article.popular` — only articles with `views` of **100 or more**, ordered by
  `views` from highest to lowest.

Both must be real scopes (chainable), so `Article.published.popular` works.

Example:

```ruby
Article.published.popular.pluck(:title)
```
