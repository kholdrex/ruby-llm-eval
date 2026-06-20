class User < ActiveRecord::Base
  validates :name, presence: true
  validates :email, presence: true, uniqueness: true
  validates :age, numericality: { only_integer: true, greater_than_or_equal_to: 18 }
end
