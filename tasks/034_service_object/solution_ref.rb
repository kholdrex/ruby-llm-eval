class CartSummary
  def initialize(items)
    @items = items
  end

  def call
    {
      count: @items.sum { |item| item[:quantity] },
      subtotal: @items.sum { |item| item[:price] * item[:quantity] }
    }
  end
end
