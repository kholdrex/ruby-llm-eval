def balanced?(str)
  closing = { ")" => "(", "]" => "[", "}" => "{" }
  openers = closing.values
  stack = []
  str.each_char do |char|
    if openers.include?(char)
      stack.push(char)
    elsif closing.key?(char)
      return false if stack.pop != closing[char]
    end
  end
  stack.empty?
end
