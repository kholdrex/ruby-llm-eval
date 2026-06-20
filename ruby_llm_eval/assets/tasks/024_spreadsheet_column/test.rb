require "minitest/autorun"
require_relative "solution"

class SpreadsheetColumnTest < Minitest::Test
  def test_column_to_number_basics
    assert_equal(1, column_to_number("A"))
    assert_equal(26, column_to_number("Z"))
    assert_equal(27, column_to_number("AA"))
    assert_equal(28, column_to_number("AB"))
    assert_equal(52, column_to_number("AZ"))
    assert_equal(701, column_to_number("ZY"))
    assert_equal(703, column_to_number("AAA"))
  end

  def test_number_to_column_basics
    assert_equal("A", number_to_column(1))
    assert_equal("Z", number_to_column(26))
    assert_equal("AA", number_to_column(27))
    assert_equal("AB", number_to_column(28))
    assert_equal("AZ", number_to_column(52))
    assert_equal("ZY", number_to_column(701))
    assert_equal("AAA", number_to_column(703))
  end

  def test_round_trip
    [1, 2, 26, 27, 100, 701, 702, 16_384, 1_000_000].each do |n|
      assert_equal(n, column_to_number(number_to_column(n)))
    end
  end
end
