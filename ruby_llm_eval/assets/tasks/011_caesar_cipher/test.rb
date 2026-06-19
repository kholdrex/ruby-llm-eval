require "minitest/autorun"
require_relative "solution"

class CaesarCipherTest < Minitest::Test
  def test_basic_shift
    assert_equal("bcd", caesar_cipher("abc", 1))
  end

  def test_zero_shift
    assert_equal("abc", caesar_cipher("abc", 0))
  end

  def test_full_wrap
    assert_equal("abc", caesar_cipher("abc", 26))
  end

  def test_preserves_case_and_punctuation
    assert_equal("Khoor, Zruog!", caesar_cipher("Hello, World!", 3))
  end

  def test_negative_shift
    assert_equal("abc", caesar_cipher("bcd", -1))
    assert_equal("yza", caesar_cipher("abc", -2))
  end

  def test_large_shift
    assert_equal("bcd", caesar_cipher("abc", 27))
  end
end
