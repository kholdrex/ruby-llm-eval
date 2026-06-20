class Account < ActiveRecord::Base
  before_save :normalize_email

  private

  def normalize_email
    self.email = email.to_s.strip.downcase
  end
end
