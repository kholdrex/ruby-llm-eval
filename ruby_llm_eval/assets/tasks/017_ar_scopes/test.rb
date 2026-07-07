require "minitest/autorun"
require "active_record"

ActiveRecord::Base.establish_connection(adapter: "sqlite3", database: ":memory:")
ActiveRecord::Schema.verbose = false
ActiveRecord::Schema.define do
  create_table :articles do |t|
    t.string :title
    t.boolean :published, default: false
    t.integer :views, default: 0
  end
end

require_relative "solution"

class ArticleScopesTest < Minitest::Test
  def setup
    Article.delete_all
    Article.create!(title: "Alpha", published: true, views: 250)
    Article.create!(title: "Beta", published: false, views: 500)
    Article.create!(title: "Gamma", published: true, views: 50)
    Article.create!(title: "Delta", published: true, views: 100)
    # Boundary row: views == 99 must NOT count as popular (>= 100), which
    # catches an off-by-one such as `where(views: 99..)`.
    Article.create!(title: "Epsilon", published: true, views: 99)
  end

  def test_published_scope
    # published has no defined order, so compare as a set.
    assert_equal(["Alpha", "Delta", "Epsilon", "Gamma"], Article.published.pluck(:title).sort)
  end

  def test_popular_scope_filters_and_orders
    # Order is part of the spec: assert it directly (no .sort).
    assert_equal(["Beta", "Alpha", "Delta"], Article.popular.pluck(:title))
  end

  def test_popular_boundary_at_100
    titles = Article.popular.pluck(:title)
    assert_includes(titles, "Delta")     # views == 100 is popular (inclusive)
    refute_includes(titles, "Epsilon")   # views == 99 is not
  end

  def test_scopes_are_chainable
    assert_equal(["Alpha", "Delta"], Article.published.popular.pluck(:title))
  end
end
