require "minitest/autorun"
require_relative "solution"

class BinarySearchTest < Minitest::Test
  def test_first_element
    assert_equal(0, binary_search([1, 2, 3], 1))
  end

  def test_last_element
    assert_equal(2, binary_search([1, 2, 3], 3))
  end

  def test_middle_element
    assert_equal(3, binary_search([1, 3, 5, 7, 9], 7))
  end

  def test_absent
    assert_nil(binary_search([1, 3, 5, 7, 9], 4))
  end

  def test_empty
    assert_nil(binary_search([], 1))
  end

  def test_single_element
    assert_equal(0, binary_search([42], 42))
    assert_nil(binary_search([42], 7))
  end
end
