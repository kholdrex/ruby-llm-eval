def justify(words, max_width)
  lines = []
  current = []
  letters = 0

  words.each do |word|
    if letters + current.size + word.length > max_width
      lines << build_line(current, letters, max_width)
      current = []
      letters = 0
    end
    current << word
    letters += word.length
  end

  last = current.join(" ")
  lines << last + (" " * (max_width - last.length))
  lines
end

def build_line(words, letters, max_width)
  return words.first + (" " * (max_width - letters)) if words.size == 1

  gaps = words.size - 1
  total_spaces = max_width - letters
  base = total_spaces / gaps
  extra = total_spaces % gaps

  line = +""
  words.each_with_index do |word, index|
    line << word
    line << (" " * (base + (index < extra ? 1 : 0))) if index < gaps
  end
  line
end
