def word_frequency(text)
  counts = Hash.new(0)
  text.downcase.scan(/[a-z0-9]+/) { |word| counts[word] += 1 }
  counts
end
