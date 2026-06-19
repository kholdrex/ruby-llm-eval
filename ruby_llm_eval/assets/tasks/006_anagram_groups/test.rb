require "minitest/autorun"
require_relative "solution"

class AnagramGroupsTest < Minitest::Test
  def test_basic
    expected = [["ate", "eat", "tea"], ["bat"], ["nat", "tan"]]
    assert_equal(expected, anagram_groups(%w[eat tea tan ate nat bat]))
  end

  def test_empty
    assert_equal([], anagram_groups([]))
  end

  def test_single_word
    assert_equal([["a"]], anagram_groups(["a"]))
  end

  def test_no_anagrams
    assert_equal([["abc"], ["def"], ["ghi"]],
                 anagram_groups(%w[def abc ghi]))
  end

  def test_all_anagrams
    assert_equal([["abc", "bca", "cab"]],
                 anagram_groups(%w[cab bca abc]))
  end
end
