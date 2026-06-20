class ProductsController < ActionController::Base
  def update
    product = Product.find_by(id: params[:id])
    return render json: { error: "not found" }, status: :not_found unless product

    product.update(product_params)
    render json: { id: product.id, name: product.name }
  end

  private

  def product_params
    params.require(:product).permit(:name)
  end
end
