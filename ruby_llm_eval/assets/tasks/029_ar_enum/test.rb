require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :orders do |t|
    t.integer :status
  end
end

require_relative "solution"

class OrderEnumTest < Minitest::Test
  def setup
    Order.delete_all
  end

  def test_predicates_and_string_value
    order = Order.create!(status: :pending)
    assert(order.pending?)
    refute(order.shipped?)
    assert_equal("pending", order.status)
  end

  def test_bang_method_persists
    order = Order.create!(status: :pending)
    order.shipped!
    assert(order.shipped?)
    assert_equal("shipped", order.reload.status)
  end

  def test_scopes
    Order.create!(status: :pending)
    Order.create!(status: :shipped)
    Order.create!(status: :shipped)
    assert_equal(2, Order.shipped.count)
    assert_equal(1, Order.pending.count)
    assert_equal(0, Order.delivered.count)
  end
end
