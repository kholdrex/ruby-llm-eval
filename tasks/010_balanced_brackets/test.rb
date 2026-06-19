require "minitest/autorun"
require_relative "solution"

class BalancedBracketsTest < Minitest::Test
  def test_simple_pair
    assert(balanced?("()"))
  end

  def test_all_kinds
    assert(balanced?("()[]{}"))
  end

  def test_nested
    assert(balanced?("{[]}"))
  end

  def test_mismatched
    refute(balanced?("(]"))
  end

  def test_wrong_order
    refute(balanced?("([)]"))
  end

  def test_empty
    assert(balanced?(""))
  end

  def test_unclosed
    refute(balanced?("("))
  end

  def test_ignores_other_characters
    assert(balanced?("a(b)c[d]"))
  end

  def test_closing_before_opening
    refute(balanced?(")("))
  end
end
