require "minitest/autorun"
require_relative "solution"

class CartSummaryTest < Minitest::Test
  def test_totals
    items = [{ price: 100, quantity: 2 }, { price: 50, quantity: 3 }]
    result = CartSummary.new(items).call
    assert_equal(5, result[:count])
    assert_equal(350, result[:subtotal])
  end

  def test_empty_cart
    result = CartSummary.new([]).call
    assert_equal(0, result[:count])
    assert_equal(0, result[:subtotal])
  end

  def test_single_item
    result = CartSummary.new([{ price: 999, quantity: 1 }]).call
    assert_equal(1, result[:count])
    assert_equal(999, result[:subtotal])
  end
end
