def column_to_number(title)
  title.each_char.reduce(0) do |number, char|
    number * 26 + (char.ord - "A".ord + 1)
  end
end

def number_to_column(number)
  title = ""
  while number.positive?
    number -= 1
    title.prepend(("A".ord + (number % 26)).chr)
    number /= 26
  end
  title
end
