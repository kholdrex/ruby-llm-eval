require "minitest/autorun"
require_relative "solution"

class LRUCacheTest < Minitest::Test
  def test_classic_sequence
    cache = LRUCache.new(2)
    cache.put(1, 1)
    cache.put(2, 2)
    assert_equal(1, cache.get(1)) # touches 1; order is now [2, 1]
    cache.put(3, 3)               # evicts least recently used (2)
    assert_nil(cache.get(2))
    cache.put(4, 4)               # evicts least recently used (1)
    assert_nil(cache.get(1))
    assert_equal(3, cache.get(3))
    assert_equal(4, cache.get(4))
  end

  def test_update_existing_key
    cache = LRUCache.new(2)
    cache.put(1, 1)
    cache.put(1, 10)
    assert_equal(10, cache.get(1))
  end

  def test_capacity_one
    cache = LRUCache.new(1)
    cache.put(1, 1)
    cache.put(2, 2)
    assert_nil(cache.get(1))
    assert_equal(2, cache.get(2))
  end

  def test_get_refreshes_recency
    cache = LRUCache.new(2)
    cache.put(1, 1)
    cache.put(2, 2)
    cache.get(1)    # 1 is now most recently used
    cache.put(3, 3) # so 2 should be evicted, not 1
    assert_equal(1, cache.get(1))
    assert_nil(cache.get(2))
  end

  def test_missing_key
    cache = LRUCache.new(2)
    assert_nil(cache.get(42))
  end
end
