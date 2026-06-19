require "minitest/autorun"
require_relative "solution"

class TwoSumTest < Minitest::Test
  def test_basic
    assert_equal([0, 1], two_sum([2, 7, 11, 15], 9))
  end

  def test_middle_pair
    assert_equal([1, 2], two_sum([3, 2, 4], 6))
  end

  def test_duplicate_values
    assert_equal([0, 1], two_sum([3, 3], 6))
  end

  def test_negative_numbers
    assert_equal([1, 4], two_sum([5, -1, 8, 11, 1], 0))
  end

  def test_no_solution
    assert_nil(two_sum([1, 2, 3], 100))
  end
end
