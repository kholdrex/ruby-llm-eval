def palindrome?(str)
  cleaned = str.downcase.gsub(/[^a-z0-9]/, "")
  cleaned == cleaned.reverse
end
