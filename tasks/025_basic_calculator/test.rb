require "minitest/autorun"
require_relative "solution"

class CalculateTest < Minitest::Test
  def test_precedence
    assert_equal(7, calculate("3+2*2"))
  end

  def test_nested_parentheses
    assert_equal(23, calculate("(1+(4+5+2)-3)+(6+8)"))
  end

  def test_left_associative_div_mul
    assert_equal(8, calculate("14/3*2"))
  end

  def test_truncation_toward_zero
    assert_equal(-2, calculate("(0-9)/4"))
    assert_equal(-1, calculate("1-9/4"))
  end

  def test_spaces_ignored
    assert_equal(21, calculate(" 3 * ( 1 + 6 ) "))
  end

  def test_single_number
    assert_equal(42, calculate("42"))
  end

  def test_subtraction_chain
    assert_equal(-4, calculate("1-2-3"))
  end

  def test_mixed
    assert_equal(2, calculate("2*(5-3)/(4-2)"))
  end
end
