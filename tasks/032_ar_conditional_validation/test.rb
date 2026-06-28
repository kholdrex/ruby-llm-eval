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

  def test_paid_rejects_blank_card
    # Whitespace-only is blank: a `presence` validation rejects it, but a manual
    # `card_number.nil?` check would wrongly accept it.
    refute(Subscription.new(plan: "paid", card_number: "   ").valid?)
  end

  def test_paid_with_card_is_valid
    assert(Subscription.new(plan: "paid", card_number: "4111111111111111").valid?)
  end

  def test_free_does_not_require_card
    assert(Subscription.new(plan: "free", card_number: nil).valid?)
    assert(Subscription.new(plan: "free").valid?)
  end

  def test_other_plans_do_not_require_card
    # Only "paid" requires a card. A too-broad `if: plan != "free"` would
    # wrongly require one here.
    assert(Subscription.new(plan: "trial", card_number: nil).valid?)
    assert(Subscription.new(plan: "enterprise").valid?)
  end
end
