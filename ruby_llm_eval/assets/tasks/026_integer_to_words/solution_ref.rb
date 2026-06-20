ONES = %w[zero one two three four five six seven eight nine ten eleven twelve
          thirteen fourteen fifteen sixteen seventeen eighteen nineteen].freeze
TENS = %w[zero ten twenty thirty forty fifty sixty seventy eighty ninety].freeze
SCALES = [[1_000_000_000, "billion"], [1_000_000, "million"], [1_000, "thousand"]].freeze

def to_words(number)
  return "zero" if number.zero?

  parts = []
  SCALES.each do |value, name|
    next if number < value

    parts << "#{three_digits(number / value)} #{name}"
    number %= value
  end
  parts << three_digits(number) if number.positive?
  parts.join(" ")
end

def three_digits(number)
  words = []
  if number >= 100
    words << "#{ONES[number / 100]} hundred"
    number %= 100
  end
  if number >= 20
    tens = TENS[number / 10]
    ones = number % 10
    words << (ones.zero? ? tens : "#{tens}-#{ONES[ones]}")
  elsif number.positive?
    words << ONES[number]
  end
  words.join(" ")
end
