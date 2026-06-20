require "minitest/autorun"
require "active_record"
require "action_controller"
require "rack/test"
require "json"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :products do |t|
    t.string :name
  end
end

class Product < ActiveRecord::Base
end

require_relative "solution"

ROUTES = ActionDispatch::Routing::RouteSet.new
ROUTES.draw do
  patch "/products/:id", to: "products#update"
end

class UpdateActionTest < Minitest::Test
  include Rack::Test::Methods

  def app
    ROUTES
  end

  def setup
    Product.delete_all
    @product = Product.create!(name: "Old")
  end

  def test_updates_name
    patch "/products/#{@product.id}", product: { name: "New" }
    assert_equal(200, last_response.status)
    assert_equal("New", @product.reload.name)
  end

  def test_missing_product_returns_404
    patch "/products/999999", product: { name: "X" }
    assert_equal(404, last_response.status)
    assert_equal("not found", JSON.parse(last_response.body)["error"])
  end
end
