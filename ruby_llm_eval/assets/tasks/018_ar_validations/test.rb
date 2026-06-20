require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :users do |t|
    t.string :name
    t.string :email
    t.integer :age
  end
end

require_relative "solution"

class UserValidationsTest < Minitest::Test
  def setup
    User.delete_all
  end

  def attrs(overrides = {})
    { name: "Ann", email: "ann@example.com", age: 30 }.merge(overrides)
  end

  def test_valid_user
    assert(User.new(attrs).valid?)
  end

  def test_name_required
    refute(User.new(attrs(name: nil)).valid?)
  end

  def test_email_required
    refute(User.new(attrs(email: "")).valid?)
  end

  def test_age_minimum
    refute(User.new(attrs(age: 17)).valid?)
    assert(User.new(attrs(age: 18)).valid?)
  end

  def test_age_must_be_integer
    refute(User.new(attrs(age: nil)).valid?)
  end

  def test_email_unique
    User.create!(attrs)
    duplicate = User.new(attrs(name: "Bob"))
    refute(duplicate.valid?)
    assert_includes(duplicate.errors[:email], "has already been taken")
  end
end
