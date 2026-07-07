require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :users do |t|
    t.string :name
  end
end

require_relative "solution"

class UserSearchTest < Minitest::Test
  def setup
    User.delete_all
    User.create!(name: "Alice")
    User.create!(name: "Alicia")
    User.create!(name: "Bob")
  end

  def test_finds_substring_matches
    assert_equal(["Alice", "Alicia"], User.search("Ali").order(:name).pluck(:name))
  end

  def test_no_match_returns_empty
    assert_equal([], User.search("Zoe").pluck(:name))
  end

  def test_is_safe_against_sql_injection
    # No name contains this literal text. A safe (parameterized) query returns
    # nothing; a string-interpolated `LIKE '%#{query}%'` would break out of the
    # quotes and return every user.
    assert_equal([], User.search("' OR '1'='1").pluck(:name))
  end
end
