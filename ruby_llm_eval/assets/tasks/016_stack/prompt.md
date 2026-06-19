# Stack (LIFO)

Implement a class with this exact interface:

```ruby
class Stack
  def push(item)  # add an item to the top
  end

  def pop         # remove and return the top item; nil if empty
  end

  def peek        # return the top item without removing it; nil if empty
  end

  def size        # number of items
  end

  def empty?      # true if there are no items
  end
end
```

Build a last-in-first-out stack. A new `Stack` starts empty. `pop` and `peek`
return `nil` when the stack is empty.

Example:

```ruby
stack = Stack.new
stack.push(1)
stack.push(2)
stack.pop   # => 2
stack.peek  # => 1
stack.size  # => 1
```
