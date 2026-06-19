def caesar_cipher(str, shift)
  str.chars.map do |ch|
    case ch
    when "a".."z"
      (((ch.ord - 97 + shift) % 26) + 97).chr
    when "A".."Z"
      (((ch.ord - 65 + shift) % 26) + 65).chr
    else
      ch
    end
  end.join
end
