# Sandbox image for running untrusted, model-generated Ruby code.
# Nothing is baked in: the candidate solution + test are mounted read-only at
# /work at run time. Minitest ships with Ruby (no Bundler needed); RSpec does
# not, so we install it for tasks that ship a spec.rb instead of a test.rb.
FROM ruby:3.3-slim

RUN gem install rspec -v "~> 3.13" --no-document

# Execute as an unprivileged user (defense in depth alongside --network none,
# --read-only, and the resource limits set by the harness at `docker run`).
RUN useradd --create-home --uid 1000 runner
USER runner

WORKDIR /work
CMD ["ruby", "test.rb"]
