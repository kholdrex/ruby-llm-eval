require "minitest/autorun"
require_relative "solution"

class ToWordsTest < Minitest::Test
  def test_zero
    assert_equal("zero", to_words(0))
  end

  def test_single_digits
    assert_equal("seven", to_words(7))
  end

  def test_teens
    assert_equal("thirteen", to_words(13))
  end

  def test_hyphenated_tens
    assert_equal("twenty-one", to_words(21))
    assert_equal("forty-five", to_words(45))
    assert_equal("ninety-nine", to_words(99))
  end

  def test_round_tens
    assert_equal("seventy", to_words(70))
  end

  def test_hundreds
    assert_equal("one hundred", to_words(100))
    assert_equal("one hundred five", to_words(105))
    assert_equal("one hundred twenty-three", to_words(123))
  end

  def test_thousands
    assert_equal("one thousand", to_words(1000))
    assert_equal("twelve thousand three hundred forty-five", to_words(12_345))
  end

  def test_millions
    assert_equal(
      "one million two hundred thirty-four thousand five hundred sixty-seven",
      to_words(1_234_567)
    )
  end

  def test_billions
    assert_equal(
      "two billion one hundred forty-seven million four hundred eighty-three thousand six hundred forty-seven",
      to_words(2_147_483_647)
    )
  end
end
