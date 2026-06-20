class Listing < ActiveRecord::Base
  scope :priced_between, ->(low, high) { where(price: low..high) }
end
