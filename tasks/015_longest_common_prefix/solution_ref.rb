def longest_common_prefix(strings)
  return "" if strings.empty?

  first = strings.first
  first.length.times do |i|
    char = first[i]
    return first[0...i] if strings.any? { |s| s[i] != char }
  end
  first
end
