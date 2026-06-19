require "minitest/autorun"
require_relative "solution"

class PalindromeTest < Minitest::Test
  def test_classic_sentence
    assert(palindrome?("A man, a plan, a canal: Panama"))
  end

  def test_not_a_palindrome
    refute(palindrome?("hello"))
  end

  def test_empty_string
    assert(palindrome?(""))
  end

  def test_single_word_mixed_case
    assert(palindrome?("Racecar"))
  end

  def test_punctuation_only_difference
    assert(palindrome?("No 'x' in Nixon"))
  end

  def test_two_distinct_letters
    refute(palindrome?("ab"))
  end
end
