require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :listings do |t|
    t.string :title
    t.integer :price
  end
end

require_relative "solution"

class ScopeArgumentTest < Minitest::Test
  def setup
    Listing.delete_all
    Listing.create!(title: "Cheap", price: 10)
    Listing.create!(title: "Mid", price: 50)
    Listing.create!(title: "Pricey", price: 100)
    Listing.create!(title: "Lux", price: 500)
  end

  def test_range_is_inclusive
    assert_equal(["Mid", "Pricey"], Listing.priced_between(50, 100).order(:price).pluck(:title))
  end

  def test_single_value_range
    assert_equal(["Cheap"], Listing.priced_between(10, 10).pluck(:title))
  end

  def test_scope_is_chainable
    assert_equal(1, Listing.priced_between(0, 60).where(title: "Mid").count)
  end
end
