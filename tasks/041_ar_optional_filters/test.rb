require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :products do |t|
    t.string :name
    t.integer :price
  end
end

class Product < ActiveRecord::Base
end

require_relative "solution"

class ProductSearchTest < Minitest::Test
  def setup
    Product.delete_all
    Product.create!(name: "Cable", price: 5)
    Product.create!(name: "Cap", price: 15)
    Product.create!(name: "Charger", price: 20)
    Product.create!(name: "Mouse", price: 25)
  end

  def names(result)
    result.map { |row| row[:name] }
  end

  def test_no_filters_returns_all_ordered_by_price
    assert_equal(["Cable", "Cap", "Charger", "Mouse"], names(ProductSearch.call))
  end

  def test_blank_name_is_ignored
    assert_equal(["Cable", "Cap", "Charger", "Mouse"], names(ProductSearch.call(name: "")))
  end

  def test_name_filter_only
    assert_equal(["Cable", "Cap"], names(ProductSearch.call(name: "Ca")))
  end

  def test_max_price_only
    assert_equal(["Cable", "Cap"], names(ProductSearch.call(max_price: 15)))
  end

  def test_both_filters_combine
    assert_equal(["Cable"], names(ProductSearch.call(name: "Ca", max_price: 10)))
  end

  def test_row_shape
    row = ProductSearch.call(max_price: 5).first
    assert_equal({ name: "Cable", price: 5 }, row)
  end
end
