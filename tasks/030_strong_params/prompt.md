# Strong parameters

You are writing a Rails controller. ActionController and a `User` ActiveRecord
model are available (no need to require them). `User` has columns `name`
(string), `email` (string), and `admin` (boolean, default `false`).

The route is:

```ruby
post "/users" => "users#create"
```

Implement `UsersController < ActionController::Base` with a `create` action that:

- builds a `User` from the request parameters using **strong parameters**,
  permitting only `name` and `email` (so a request can never set `admin`),
- saves it, and renders the user as JSON.

```ruby
class UsersController < ActionController::Base
  def create
  end
end
```

Parameters arrive nested under `user`, e.g. `params[:user][:name]`.
