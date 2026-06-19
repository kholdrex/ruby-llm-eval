def roman_to_integer(s)
  values = { "I" => 1, "V" => 5, "X" => 10, "L" => 50,
             "C" => 100, "D" => 500, "M" => 1000 }
  total = 0
  highest = 0
  s.reverse.each_char do |char|
    current = values[char]
    if current < highest
      total -= current
    else
      total += current
      highest = current
    end
  end
  total
end
