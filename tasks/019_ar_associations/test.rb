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

require_relative "solution"

class AssociationsTest < Minitest::Test
  def setup
    Book.delete_all
    Author.delete_all
    @ursula = Author.create!(name: "Ursula")
    @ursula.books.create!(title: "A Wizard of Earthsea")
    @ursula.books.create!(title: "The Left Hand of Darkness")
    isaac = Author.create!(name: "Isaac")
    isaac.books.create!(title: "Foundation")
  end

  def test_author_has_many_books
    assert_equal(2, @ursula.books.count)
    assert_equal(
      ["A Wizard of Earthsea", "The Left Hand of Darkness"],
      @ursula.books.order(:title).pluck(:title)
    )
  end

  def test_book_belongs_to_author
    book = Book.find_by(title: "Foundation")
    assert_equal("Isaac", book.author.name)
  end

  def test_books_are_scoped_to_their_author
    assert_equal(["Foundation"], Author.find_by(name: "Isaac").books.pluck(:title))
  end
end
