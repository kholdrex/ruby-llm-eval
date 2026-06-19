require "minitest/autorun"
require_relative "solution"

class FizzBuzzTest < Minitest::Test
  def test_one
    assert_equal(["1"], fizzbuzz(1))
  end

  def test_first_three
    assert_equal(["1", "2", "Fizz"], fizzbuzz(3))
  end

  def test_through_fifteen
    expected = ["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz",
                "Buzz", "11", "Fizz", "13", "14", "FizzBuzz"]
    assert_equal(expected, fizzbuzz(15))
  end

  def test_returns_strings
    assert(fizzbuzz(5).all? { |item| item.is_a?(String) })
  end
end
