def transpose(matrix)
  return [] if matrix.empty?

  matrix.first.each_index.map do |col|
    matrix.map { |row| row[col] }
  end
end
