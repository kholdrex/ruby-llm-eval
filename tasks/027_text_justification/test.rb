require "minitest/autorun"
require_relative "solution"

class JustifyTest < Minitest::Test
  def test_example_one
    words = ["This", "is", "an", "example", "of", "text", "justification."]
    expected = [
      "This    is    an",
      "example  of text",
      "justification.  "
    ]
    assert_equal(expected, justify(words, 16))
  end

  def test_example_two_single_word_line
    words = ["What", "must", "be", "acknowledgment", "shall", "be"]
    expected = [
      "What   must   be",
      "acknowledgment  ",
      "shall be        "
    ]
    assert_equal(expected, justify(words, 16))
  end

  def test_all_lines_have_exact_width
    words = ["Science", "is", "what", "we", "understand", "well", "enough", "to",
             "explain", "to", "a", "computer."]
    lines = justify(words, 20)
    assert(lines.all? { |line| line.length == 20 })
  end

  def test_single_word
    assert_equal(["hello     "], justify(["hello"], 10))
  end

  def test_last_line_left_justified
    lines = justify(["a", "b", "c", "d", "e"], 5)
    assert_equal("a b c", lines.first)
    assert_equal("d e  ", lines.last) # last line: single-spaced, right-padded
  end
end
