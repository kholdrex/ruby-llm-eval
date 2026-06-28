require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :orders do |t|
    t.string :customer_name
  end
  create_table :line_items do |t|
    t.integer :order_id
    t.integer :price
  end
end

class Order < ActiveRecord::Base
  has_many :line_items
end

class LineItem < ActiveRecord::Base
  belongs_to :order
  validates :price, numericality: { greater_than: 0 }
end

require_relative "solution"

class OrderPlacementTest < Minitest::Test
  def setup
    LineItem.delete_all
    Order.delete_all
  end

  def test_places_a_valid_order
    order = OrderPlacement.place("Bob", [10, 20])
    assert_equal(1, Order.count)
    assert_equal(2, order.line_items.count)
    assert_equal(30, order.line_items.sum(:price))
  end

  def test_rolls_back_when_a_line_item_is_invalid
    begin
      OrderPlacement.place("Ann", [10, -5, 20])
    rescue ActiveRecord::RecordInvalid
      # Raising on the invalid line item is fine; what matters is atomicity.
    end
    assert_equal(0, Order.count, "a failed placement must not leave an orphaned order")
    assert_equal(0, LineItem.count, "a failed placement must not leave any line items")
  end
end
