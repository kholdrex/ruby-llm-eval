require "minitest/autorun"
require_relative "solution"

class MergeIntervalsTest < Minitest::Test
  def test_basic
    assert_equal([[1, 6], [8, 10], [15, 18]],
                 merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]]))
  end

  def test_touching_merges
    assert_equal([[1, 5]], merge_intervals([[1, 4], [4, 5]]))
  end

  def test_empty
    assert_equal([], merge_intervals([]))
  end

  def test_single
    assert_equal([[1, 4]], merge_intervals([[1, 4]]))
  end

  def test_unsorted_input_with_full_overlap
    assert_equal([[1, 10]], merge_intervals([[2, 3], [1, 10], [5, 6]]))
  end

  def test_no_overlap_sorted
    assert_equal([[1, 2], [3, 4]], merge_intervals([[3, 4], [1, 2]]))
  end
end
