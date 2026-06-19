require "minitest/autorun"
require_relative "solution"

class TransposeTest < Minitest::Test
  def test_rectangular
    assert_equal([[1, 4], [2, 5], [3, 6]], transpose([[1, 2, 3], [4, 5, 6]]))
  end

  def test_single_row
    assert_equal([[1], [2], [3]], transpose([[1, 2, 3]]))
  end

  def test_single_column
    assert_equal([[1, 2, 3]], transpose([[1], [2], [3]]))
  end

  def test_empty
    assert_equal([], transpose([]))
  end

  def test_one_by_one
    assert_equal([[1]], transpose([[1]]))
  end

  def test_does_not_mutate_input
    matrix = [[1, 2], [3, 4]]
    transpose(matrix)
    assert_equal([[1, 2], [3, 4]], matrix)
  end
end
