require "minitest/autorun"
require "active_record"
require "action_controller"
require "rack/test"
require "json"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :users do |t|
    t.string :name
    t.string :email
    t.boolean :admin, default: false
  end
end

class User < ActiveRecord::Base
end

require_relative "solution"

ROUTES = ActionDispatch::Routing::RouteSet.new
ROUTES.draw do
  post "/users", to: "users#create"
end

class StrongParamsTest < Minitest::Test
  include Rack::Test::Methods

  def app
    ROUTES
  end

  def setup
    User.delete_all
  end

  def test_permitted_attributes_are_saved
    post "/users", user: { name: "Ann", email: "ann@example.com" }
    assert_equal(200, last_response.status)
    user = User.last
    assert_equal("Ann", user.name)
    assert_equal("ann@example.com", user.email)
  end

  def test_unpermitted_admin_is_filtered_out
    post "/users", user: { name: "Mallory", email: "m@example.com", admin: "true" }
    assert_equal(200, last_response.status)
    assert_equal(false, User.last.admin)
  end
end
