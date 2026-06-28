module ArticleReport
  def self.published
    Article.where(published: true).includes(:author, :comments).order(:title).map do |article|
      {
        title: article.title,
        author: article.author.name,
        comments: article.comments.size
      }
    end
  end
end
