module ProductSearch
  def self.call(name: nil, max_price: nil)
    scope = Product.all
    scope = scope.where("name LIKE ?", "%#{name}%") if name && !name.empty?
    scope = scope.where(price: ..max_price) if max_price
    scope.order(:price).map { |product| { name: product.name, price: product.price } }
  end
end
