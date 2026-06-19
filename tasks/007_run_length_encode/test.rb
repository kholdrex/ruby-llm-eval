require "minitest/autorun"
require_relative "solution"

class RunLengthEncodeTest < Minitest::Test
  def test_basic
    assert_equal("a3b2c1", run_length_encode("aaabbc"))
  end

  def test_empty
    assert_equal("", run_length_encode(""))
  end

  def test_single_char
    assert_equal("a1", run_length_encode("a"))
  end

  def test_alternating
    assert_equal("a1b1a1", run_length_encode("aba"))
  end

  def test_long_run
    assert_equal("w4", run_length_encode("wwww"))
  end

  def test_double_digit_run
    assert_equal("x12", run_length_encode("x" * 12))
  end
end
