require "minitest/autorun"
require_relative "solution"

class FlattenDeepTest < Minitest::Test
  def test_deeply_nested
    assert_equal([1, 2, 3, 4], flatten_deep([1, [2, [3, [4]]]]))
  end

  def test_shallow
    assert_equal([1, 2, 3], flatten_deep([[1], [2], [3]]))
  end

  def test_empty
    assert_equal([], flatten_deep([]))
  end

  def test_mixed_depth
    assert_equal([1, 2, 3, 4, 5], flatten_deep([1, [2, 3, [4, [5]]]]))
  end

  def test_single_deep_value
    assert_equal([1], flatten_deep([[[[1]]]]))
  end

  def test_preserves_non_integers
    assert_equal(["a", "b", "c"], flatten_deep([["a"], [["b"], "c"]]))
  end
end
