def binary_search(sorted, target)
  low = 0
  high = sorted.length - 1
  while low <= high
    mid = (low + high) / 2
    value = sorted[mid]
    if value == target
      return mid
    elsif value < target
      low = mid + 1
    else
      high = mid - 1
    end
  end
  nil
end
