# Sandbox image for running untrusted, model-generated Ruby code.
# Nothing is baked in: the candidate solution + test are mounted read-only at
# /work at run time. Minitest ships with Ruby, so no Bundler is required.
FROM ruby:3.3-slim

# Execute as an unprivileged user (defense in depth alongside --network none,
# --read-only, and the resource limits set by the harness at `docker run`).
RUN useradd --create-home --uid 1000 runner
USER runner

WORKDIR /work
CMD ["ruby", "test.rb"]
