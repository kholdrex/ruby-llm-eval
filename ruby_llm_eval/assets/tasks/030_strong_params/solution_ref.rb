class UsersController < ActionController::Base
  def create
    user = User.create(user_params)
    render json: { id: user.id, name: user.name, admin: user.admin }
  end

  private

  def user_params
    params.require(:user).permit(:name, :email)
  end
end
