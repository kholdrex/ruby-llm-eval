require "minitest/autorun"
require_relative "solution"

class RomanToIntegerTest < Minitest::Test
  def test_simple_additive
    assert_equal(3, roman_to_integer("III"))
  end

  def test_subtractive_four
    assert_equal(4, roman_to_integer("IV"))
  end

  def test_subtractive_nine
    assert_equal(9, roman_to_integer("IX"))
  end

  def test_mixed
    assert_equal(58, roman_to_integer("LVIII"))
  end

  def test_large_with_subtractions
    assert_equal(1994, roman_to_integer("MCMXCIV"))
  end

  def test_year
    assert_equal(2024, roman_to_integer("MMXXIV"))
  end
end
