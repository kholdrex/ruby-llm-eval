require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :authors do |t|
    t.string :name
  end
  create_table :articles do |t|
    t.string :title
    t.boolean :published, default: false
    t.integer :author_id
  end
  create_table :comments do |t|
    t.integer :article_id
  end
end

class Author < ActiveRecord::Base
  has_many :articles
end

class Article < ActiveRecord::Base
  belongs_to :author
  has_many :comments
end

class Comment < ActiveRecord::Base
  belongs_to :article
end

require_relative "solution"

class ArticleReportTest < Minitest::Test
  def setup
    Comment.delete_all
    Article.delete_all
    Author.delete_all

    ursula = Author.create!(name: "Ursula")
    isaac = Author.create!(name: "Isaac")

    zeta = Article.create!(title: "Zeta", published: true, author: ursula)
    2.times { zeta.comments.create! }
    Article.create!(title: "Alpha", published: true, author: isaac) # zero comments
    mid = Article.create!(title: "Mid", published: true, author: isaac)
    mid.comments.create!
    hidden = Article.create!(title: "Hidden", published: false, author: ursula)
    5.times { hidden.comments.create! } # unpublished -> excluded
  end

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

  def test_report_contents
    expected = [
      { title: "Alpha", author: "Isaac", comments: 0 },
      { title: "Mid", author: "Isaac", comments: 1 },
      { title: "Zeta", author: "Ursula", comments: 2 }
    ]
    assert_equal(expected, ArticleReport.published)
  end

  def test_runs_in_constant_queries
    queries = count_queries { ArticleReport.published }
    assert_operator(
      queries, :<=, 3,
      "expected a constant number of queries (<= 3), got #{queries} — likely an N+1"
    )
  end
end
