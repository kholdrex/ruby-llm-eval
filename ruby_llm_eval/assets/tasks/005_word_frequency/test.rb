require "minitest/autorun"
require_relative "solution"

class WordFrequencyTest < Minitest::Test
  def test_basic_sentence
    expected = { "the" => 3, "cat" => 2, "sat" => 1, "on" => 1, "mat" => 1 }
    assert_equal(expected, word_frequency("The cat sat on the mat. The cat!"))
  end

  def test_empty
    assert_equal({}, word_frequency(""))
  end

  def test_case_insensitive
    assert_equal({ "go" => 2 }, word_frequency("Go go"))
  end

  def test_numbers_count_as_words
    assert_equal({ "a1" => 2, "b2" => 1 }, word_frequency("a1 b2 a1"))
  end

  def test_punctuation_separates
    assert_equal({ "one" => 1, "two" => 1 }, word_frequency("one---two"))
  end
end
