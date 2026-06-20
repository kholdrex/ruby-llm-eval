class Subscription < ActiveRecord::Base
  validates :card_number, presence: true, if: :paid?

  private

  def paid?
    plan == "paid"
  end
end
