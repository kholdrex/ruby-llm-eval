def my_atoi(str)
  i = 0
  length = str.length
  i += 1 while i < length && str[i] == " "

  sign = 1
  if i < length && ["+", "-"].include?(str[i])
    sign = -1 if str[i] == "-"
    i += 1
  end

  num = 0
  while i < length && str[i] >= "0" && str[i] <= "9"
    num = num * 10 + (str[i].ord - "0".ord)
    i += 1
  end
  num *= sign

  int_min = -2_147_483_648
  int_max = 2_147_483_647
  return int_min if num < int_min
  return int_max if num > int_max

  num
end
