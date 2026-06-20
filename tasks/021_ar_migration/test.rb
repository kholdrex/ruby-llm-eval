require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")

require_relative "solution"

ActiveRecord::Migration.suppress_messages do
  CreateProducts.new.migrate(:up)
end

class CreateProductsMigrationTest < Minitest::Test
  def connection
    ActiveRecord::Base.connection
  end

  def test_table_created
    assert(connection.table_exists?(:products))
  end

  def test_column_types
    columns = connection.columns(:products).to_h { |c| [c.name, c.type] }
    assert_equal(:string, columns["name"])
    assert_equal(:decimal, columns["price"])
  end

  def test_name_is_not_null
    name_column = connection.columns(:products).find { |c| c.name == "name" }
    assert_equal(false, name_column.null)
  end

  def test_name_is_indexed
    assert(connection.indexes(:products).any? { |index| index.columns == ["name"] })
  end
end
