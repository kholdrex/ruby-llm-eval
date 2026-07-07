class ProductsController < ActionController::Base
  def index
    render json: Product.order(:name)
  end

  def show
    product = Product.find_by(id: params[:id])
    if product
      render json: product
    else
      render json: { error: "not found" }, status: :not_found
    end
  end
end
