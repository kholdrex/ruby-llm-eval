class OrderPlacement
  def self.place(customer_name, item_prices)
    ActiveRecord::Base.transaction do
      order = Order.create!(customer_name: customer_name)
      item_prices.each { |price| order.line_items.create!(price: price) }
      order
    end
  end
end
