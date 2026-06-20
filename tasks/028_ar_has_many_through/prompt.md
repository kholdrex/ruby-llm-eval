# ActiveRecord has_many :through

You are writing Rails models. ActiveRecord is available (no need to require it).
Three tables already exist:

- `doctors` — `name` (string)
- `patients` — `name` (string)
- `appointments` — `doctor_id` (integer), `patient_id` (integer)

An appointment links one doctor and one patient. Implement the models so that a
doctor has many patients **through** appointments, and a patient has many
doctors **through** appointments:

```ruby
class Doctor < ActiveRecord::Base
end

class Patient < ActiveRecord::Base
end

class Appointment < ActiveRecord::Base
end
```

After this, `doctor.patients` returns the patients that doctor has appointments
with, and `patient.doctors` returns that patient's doctors.
