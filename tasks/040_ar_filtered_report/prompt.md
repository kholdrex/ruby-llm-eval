# Published article report

You are writing Rails code. ActiveRecord is available (no need to require it).
Three models are already defined for you:

- `Author` — `name` (string), `has_many :articles`
- `Article` — `title` (string), `published` (boolean), `belongs_to :author`,
  `has_many :comments`
- `Comment` — `belongs_to :article`

Implement `ArticleReport.published`, which returns an array of hashes, one per
**published** article, each shaped like:

```ruby
{ title: "...", author: "<author name>", comments: <number of comments> }
```

All of the following must hold:

- Only **published** articles are included.
- Results are ordered by `title` (ascending).
- `comments` is the count of that article's comments, including **0** for
  articles that have none.
- It must run in a **constant** number of queries — the count must not grow
  with the number of articles.

```ruby
module ArticleReport
  def self.published
  end
end
```
