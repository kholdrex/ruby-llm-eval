module Library
  def self.author_summaries
    Author.includes(:books).order(:name).map do |author|
      titles = author.books.sort_by(&:title).map(&:title).join(", ")
      "#{author.name}: #{titles}"
    end
  end
end
