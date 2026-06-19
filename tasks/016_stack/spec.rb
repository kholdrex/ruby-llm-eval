require_relative "solution"

RSpec.describe Stack do
  it "starts empty" do
    stack = Stack.new
    expect(stack.empty?).to be true
    expect(stack.size).to eq 0
    expect(stack.peek).to be_nil
    expect(stack.pop).to be_nil
  end

  it "pushes and pops in LIFO order" do
    stack = Stack.new
    stack.push(1)
    stack.push(2)
    stack.push(3)
    expect(stack.size).to eq 3
    expect(stack.pop).to eq 3
    expect(stack.pop).to eq 2
    expect(stack.peek).to eq 1
    expect(stack.size).to eq 1
  end

  it "is empty again after popping everything" do
    stack = Stack.new
    stack.push(:a)
    stack.pop
    expect(stack.empty?).to be true
  end
end
