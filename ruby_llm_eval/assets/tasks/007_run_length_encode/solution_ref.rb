def run_length_encode(str)
  str.chars
     .chunk_while { |a, b| a == b }
     .map { |run| "#{run.first}#{run.size}" }
     .join
end
