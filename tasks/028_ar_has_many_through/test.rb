require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :doctors do |t|
    t.string :name
  end
  create_table :patients do |t|
    t.string :name
  end
  create_table :appointments do |t|
    t.integer :doctor_id
    t.integer :patient_id
  end
end

require_relative "solution"

class HasManyThroughTest < Minitest::Test
  def setup
    Appointment.delete_all
    Patient.delete_all
    Doctor.delete_all

    @house = Doctor.create!(name: "House")
    @wilson = Doctor.create!(name: "Wilson")
    @alice = Patient.create!(name: "Alice")
    @bob = Patient.create!(name: "Bob")

    Appointment.create!(doctor: @house, patient: @alice)
    Appointment.create!(doctor: @house, patient: @bob)
    Appointment.create!(doctor: @wilson, patient: @alice)
  end

  def test_doctor_has_many_patients_through_appointments
    assert_equal(["Alice", "Bob"], @house.patients.order(:name).pluck(:name))
    assert_equal(["Alice"], @wilson.patients.pluck(:name))
  end

  def test_patient_has_many_doctors_through_appointments
    assert_equal(["House", "Wilson"], @alice.doctors.order(:name).pluck(:name))
    assert_equal(["House"], @bob.doctors.pluck(:name))
  end
end
