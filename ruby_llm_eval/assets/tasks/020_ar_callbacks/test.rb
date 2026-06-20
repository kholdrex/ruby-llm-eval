require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :accounts do |t|
    t.string :name
    t.string :email
  end
end

require_relative "solution"

class AccountCallbackTest < Minitest::Test
  def setup
    Account.delete_all
  end

  def test_email_normalized_on_save
    account = Account.create!(name: "Foo", email: "  Foo@Example.COM ")
    assert_equal("foo@example.com", account.email)
    assert_equal("foo@example.com", account.reload.email)
  end

  def test_already_normalized_email_unchanged
    account = Account.create!(name: "Bar", email: "bar@example.com")
    assert_equal("bar@example.com", account.email)
  end

  def test_uppercase_without_spaces
    account = Account.create!(name: "Baz", email: "BAZ@EXAMPLE.COM")
    assert_equal("baz@example.com", account.reload.email)
  end
end
