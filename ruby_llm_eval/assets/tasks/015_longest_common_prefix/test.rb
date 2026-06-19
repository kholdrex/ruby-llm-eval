require "minitest/autorun"
require_relative "solution"

class LongestCommonPrefixTest < Minitest::Test
  def test_common_prefix
    assert_equal("fl", longest_common_prefix(["flower", "flow", "flight"]))
  end

  def test_no_common_prefix
    assert_equal("", longest_common_prefix(["dog", "cat"]))
  end

  def test_empty_array
    assert_equal("", longest_common_prefix([]))
  end

  def test_single_string
    assert_equal("a", longest_common_prefix(["a"]))
  end

  def test_long_shared_prefix
    assert_equal("inters",
                 longest_common_prefix(["interspecies", "interstellar", "interstate"]))
  end

  def test_empty_string_in_input
    assert_equal("", longest_common_prefix(["abc", ""]))
  end
end
