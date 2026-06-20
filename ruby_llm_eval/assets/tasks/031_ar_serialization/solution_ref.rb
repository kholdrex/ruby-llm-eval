class Product < ActiveRecord::Base
  def as_json(_options = nil)
    { "name" => name, "code" => sku }
  end
end
