def merge_intervals(intervals)
  sorted = intervals.sort_by { |start, _finish| start }
  merged = []
  sorted.each do |start, finish|
    if merged.any? && start <= merged.last[1]
      merged.last[1] = [merged.last[1], finish].max
    else
      merged << [start, finish]
    end
  end
  merged
end
