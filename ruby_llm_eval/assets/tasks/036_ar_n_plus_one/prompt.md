# Summaries without N+1 queries

You are writing Rails code. ActiveRecord is available (no need to require it).
Two models are already defined for you:

- `Author` — has a `name` (string) and `has_many :books`
- `Book` — has a `title` (string) and `belongs_to :author`

Implement a module method `Library.author_summaries` that returns an array of
strings, one per author **ordered by author name**, of the form:

```
"<author name>: <comma-joined book titles>"
```

where each author's titles are **ordered alphabetically**. An author with no
books renders as `"<name>: "` (nothing after the colon).

```ruby
module Library
  def self.author_summaries
  end
end
```

Efficiency is part of the task: the number of database queries your method
issues **must not grow with the number of authors** (no separate query per
author).

Example:

```ruby
Library.author_summaries
# => ["Isaac: Foundation",
#     "Ursula: A Wizard of Earthsea, The Left Hand of Darkness"]
```
