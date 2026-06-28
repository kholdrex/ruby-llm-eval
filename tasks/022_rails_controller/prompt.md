# Rails controller (JSON)

You are writing a Rails controller. ActionController and a `Product`
ActiveRecord model are available (no need to require them). The `Product` model
maps to a `products` table with a `name` (string) column.

The routes are:

```ruby
get "/products"     => "products#index"
get "/products/:id" => "products#show"
```

Implement `ProductsController < ActionController::Base` with:

- `index` — render **all products** as JSON, ordered alphabetically **by name**.
- `show` — find the product by `params[:id]` and render it as JSON. If no such
  product exists, render `{ "error": "not found" }` with HTTP status `404`.

```ruby
class ProductsController < ActionController::Base
  def index
  end

  def show
  end
end
```
