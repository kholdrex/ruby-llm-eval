require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :users do |t|
    t.string :email
  end
end

require_relative "solution"

class CallbackOrderingTest < Minitest::Test
  def setup
    User.delete_all
  end

  def test_email_is_normalized
    user = User.create!(email: "  Foo@Example.COM ")
    assert_equal("foo@example.com", user.reload.email)
  end

  def test_presence_is_validated
    refute(User.new(email: "   ").valid?)
  end

  def test_uniqueness_enforced_on_normalized_value
    User.create!(email: "foo@example.com")
    # Normalizes to an existing email, so it must be rejected. A `before_save`
    # callback would normalize too late: uniqueness would run on the raw,
    # different-looking value and wrongly pass.
    duplicate = User.new(email: "FOO@EXAMPLE.COM")
    refute(duplicate.valid?)
    assert_includes(duplicate.errors[:email], "has already been taken")
  end
end
