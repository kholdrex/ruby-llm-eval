def anagram_groups(words)
  groups = Hash.new { |hash, key| hash[key] = [] }
  words.each { |word| groups[word.chars.sort.join] << word }
  groups.values.map(&:sort).sort
end
