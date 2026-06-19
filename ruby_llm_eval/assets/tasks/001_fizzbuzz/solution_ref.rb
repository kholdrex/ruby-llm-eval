def fizzbuzz(n)
  (1..n).map do |i|
    if (i % 15).zero?
      "FizzBuzz"
    elsif (i % 3).zero?
      "Fizz"
    elsif (i % 5).zero?
      "Buzz"
    else
      i.to_s
    end
  end
end
