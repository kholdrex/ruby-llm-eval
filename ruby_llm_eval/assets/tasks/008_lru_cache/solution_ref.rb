class LRUCache
  def initialize(capacity)
    @capacity = capacity
    @store = {} # Ruby hashes preserve insertion order: oldest key is first.
  end

  def get(key)
    return nil unless @store.key?(key)

    value = @store.delete(key)
    @store[key] = value # re-insert to mark as most recently used
    value
  end

  def put(key, value)
    @store.delete(key)
    @store[key] = value
    @store.delete(@store.keys.first) if @store.size > @capacity
    nil
  end
end
