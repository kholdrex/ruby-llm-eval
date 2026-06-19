def flatten_deep(arr)
  arr.each_with_object([]) do |element, out|
    if element.is_a?(Array)
      out.concat(flatten_deep(element))
    else
      out << element
    end
  end
end
