require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :authors do |t|
    t.string :name
  end
  create_table :books do |t|
    t.string :title
    t.integer :author_id
  end
end

class Author < ActiveRecord::Base
  has_many :books
end

class Book < ActiveRecord::Base
  belongs_to :author
end

require_relative "solution"

class NPlusOneTest < Minitest::Test
  def setup
    Book.delete_all
    Author.delete_all
    ursula = Author.create!(name: "Ursula")
    ursula.books.create!(title: "The Left Hand of Darkness")
    ursula.books.create!(title: "A Wizard of Earthsea")
    isaac = Author.create!(name: "Isaac")
    isaac.books.create!(title: "Foundation")
    Author.create!(name: "Nemo") # author with no books
  end

  # Count real data queries issued while the block runs (ignore schema and
  # transaction control statements).
  def count_queries
    queries = 0
    counter = lambda do |_name, _started, _finished, _id, payload|
      sql = payload[:sql].to_s
      next if payload[:name] == "SCHEMA"
      next if sql =~ /\A\s*(BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|PRAGMA)/i

      queries += 1
    end
    ActiveSupport::Notifications.subscribed(counter, "sql.active_record") { yield }
    queries
  end

  def test_summaries_content
    expected = [
      "Isaac: Foundation",
      "Nemo: ",
      "Ursula: A Wizard of Earthsea, The Left Hand of Darkness"
    ]
    assert_equal(expected, Library.author_summaries)
  end

  def test_avoids_n_plus_one_queries
    queries = count_queries { Library.author_summaries }
    assert_operator(
      queries, :<=, 2,
      "expected the query count to stay constant (<= 2), got #{queries} — likely an N+1"
    )
  end
end
