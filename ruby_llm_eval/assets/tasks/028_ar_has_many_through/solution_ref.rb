class Doctor < ActiveRecord::Base
  has_many :appointments
  has_many :patients, through: :appointments
end

class Patient < ActiveRecord::Base
  has_many :appointments
  has_many :doctors, through: :appointments
end

class Appointment < ActiveRecord::Base
  belongs_to :doctor
  belongs_to :patient
end
