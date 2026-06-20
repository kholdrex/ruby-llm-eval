class Article < ActiveRecord::Base
  scope :published, -> { where(published: true) }
  scope :popular, -> { where(views: 100..).order(views: :desc) }
end
