# Controller update action

You are writing a Rails controller. ActionController and a `Product`
ActiveRecord model are available (no need to require them). `Product` has a
`name` (string) column.

The route is:

```ruby
patch "/products/:id" => "products#update"
```

Implement `ProductsController < ActionController::Base` with an `update` action
that:

- finds the product by `params[:id]`,
- if none exists, renders `{ "error": "not found" }` with HTTP status `404`,
- otherwise updates its `name` using **strong parameters** (permit only `name`,
  nested under `product`) and renders the product as JSON.

```ruby
class ProductsController < ActionController::Base
  def update
  end
end
```
