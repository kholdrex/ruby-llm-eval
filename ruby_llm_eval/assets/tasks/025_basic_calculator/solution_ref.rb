PRECEDENCE = { "+" => 1, "-" => 1, "*" => 2, "/" => 2 }.freeze

def calculate(expression)
  output = []
  operators = []
  expression.scan(%r{\d+|[-+*/()]}) do |token|
    case token
    when /\A\d+\z/
      output << token.to_i
    when "("
      operators << token
    when ")"
      apply_operator(output, operators.pop) until operators.last == "("
      operators.pop
    else
      while !operators.empty? && operators.last != "(" &&
            PRECEDENCE[operators.last] >= PRECEDENCE[token]
        apply_operator(output, operators.pop)
      end
      operators << token
    end
  end
  apply_operator(output, operators.pop) until operators.empty?
  output.last
end

def apply_operator(stack, operator)
  right = stack.pop
  left = stack.pop
  case operator
  when "+" then stack << left + right
  when "-" then stack << left - right
  when "*" then stack << left * right
  when "/" then stack << truncating_divide(left, right)
  end
end

def truncating_divide(left, right)
  quotient = left.abs / right.abs
  left.negative? == right.negative? ? quotient : -quotient
end
