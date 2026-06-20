require "minitest/autorun"
require "active_record"
require "json"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :products do |t|
    t.string :name
    t.string :sku
  end
end

require_relative "solution"

class SerializationTest < Minitest::Test
  def setup
    Product.delete_all
  end

  def test_custom_json_shape
    product = Product.create!(name: "Widget", sku: "W-100")
    assert_equal({ "name" => "Widget", "code" => "W-100" }, JSON.parse(product.to_json))
  end

  def test_excludes_other_columns
    product = Product.create!(name: "Gadget", sku: "G-200")
    json = JSON.parse(product.to_json)
    assert_equal(["code", "name"], json.keys.sort)
    refute(json.key?("id"))
  end
end
