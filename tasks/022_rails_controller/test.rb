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
  get "/products", to: "products#index"
  get "/products/:id", to: "products#show"
end

class ProductsControllerTest < Minitest::Test
  include Rack::Test::Methods

  def app
    ROUTES
  end

  def setup
    Product.delete_all
    # Inserted out of alphabetical order, so insertion/id order differs from
    # name order. A solution missing `order(:name)` returns insertion order
    # and fails.
    Product.create!(name: "Mango")
    Product.create!(name: "Apple")
    @zebra = Product.create!(name: "Zebra")
  end

  def test_index_orders_by_name
    get "/products"
    assert_equal(200, last_response.status)
    names = JSON.parse(last_response.body).map { |product| product["name"] }
    assert_equal(["Apple", "Mango", "Zebra"], names)
  end

  def test_show_returns_one_product
    get "/products/#{@zebra.id}"
    assert_equal(200, last_response.status)
    assert_equal("Zebra", JSON.parse(last_response.body)["name"])
  end

  def test_show_missing_returns_404
    get "/products/999999"
    assert_equal(404, last_response.status)
    assert_equal("not found", JSON.parse(last_response.body)["error"])
  end
end
