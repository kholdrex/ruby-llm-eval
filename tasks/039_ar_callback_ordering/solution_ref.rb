class User < ActiveRecord::Base
  before_validation :normalize_email
  validates :email, presence: true, uniqueness: true

  private

  def normalize_email
    self.email = email.to_s.strip.downcase
  end
end
