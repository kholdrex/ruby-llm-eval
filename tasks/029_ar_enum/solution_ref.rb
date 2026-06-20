class Order < ActiveRecord::Base
  enum :status, { pending: 0, shipped: 1, delivered: 2 }
end
