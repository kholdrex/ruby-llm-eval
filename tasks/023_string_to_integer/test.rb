require "minitest/autorun"
require_relative "solution"

class MyAtoiTest < Minitest::Test
  def test_plain
    assert_equal(42, my_atoi("42"))
  end

  def test_leading_spaces_and_sign
    assert_equal(-42, my_atoi("   -42"))
  end

  def test_trailing_junk
    assert_equal(4193, my_atoi("4193 with words"))
  end

  def test_leading_letters
    assert_equal(0, my_atoi("words and 987"))
  end

  def test_empty_and_spaces
    assert_equal(0, my_atoi(""))
    assert_equal(0, my_atoi("   "))
  end

  def test_plus_sign
    assert_equal(1, my_atoi("+1"))
  end

  def test_sign_then_nondigit
    assert_equal(0, my_atoi("+-12"))
  end

  def test_leading_zeros
    assert_equal(12_345_678, my_atoi("  0000000000012345678"))
  end

  def test_stops_at_dot
    assert_equal(3, my_atoi("3.14"))
  end

  def test_clamp_low
    assert_equal(-2_147_483_648, my_atoi("-91283472332"))
    assert_equal(-2_147_483_648, my_atoi("-2147483648"))
  end

  def test_clamp_high
    assert_equal(2_147_483_647, my_atoi("91283472332"))
    assert_equal(2_147_483_647, my_atoi("2147483647"))
  end
end
