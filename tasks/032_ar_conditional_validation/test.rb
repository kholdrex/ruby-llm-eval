require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :subscriptions do |t|
    t.string :plan
    t.string :card_number
  end
end

require_relative "solution"

class ConditionalValidationTest < Minitest::Test
  def test_paid_requires_card
    refute(Subscription.new(plan: "paid", card_number: nil).valid?)
    refute(Subscription.new(plan: "paid", card_number: "").valid?)
  end

  def test_paid_with_card_is_valid
    assert(Subscription.new(plan: "paid", card_number: "4111111111111111").valid?)
  end

  def test_free_does_not_require_card
    assert(Subscription.new(plan: "free", card_number: nil).valid?)
    assert(Subscription.new(plan: "free").valid?)
  end
end
