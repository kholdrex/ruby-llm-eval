from ruby_llm_eval.evaluate import (
    FRAMEWORKS,
    STATUS_ERROR,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_TIMEOUT,
    _classify,
)

MINITEST = FRAMEWORKS["minitest"]["summary"]
RSPEC = FRAMEWORKS["rspec"]["summary"]

MINITEST_OK = "3 runs, 9 assertions, 0 failures, 0 errors, 0 skips"
MINITEST_FAIL = "3 runs, 9 assertions, 1 failures, 0 errors, 0 skips"
RSPEC_FAIL = "5 examples, 1 failure"


def test_exit_zero_is_passed():
    assert _classify(0, MINITEST_OK, "", MINITEST) == STATUS_PASSED


def test_exit_124_is_timeout():
    assert _classify(124, "", "", MINITEST) == STATUS_TIMEOUT


def test_failed_assertion_is_failed():
    assert _classify(1, MINITEST_FAIL, "", MINITEST) == STATUS_FAILED


def test_load_error_is_error():
    # No framework summary printed => the file blew up before tests ran.
    stderr = "solution.rb:1: syntax error, unexpected end-of-input"
    assert _classify(1, "", stderr, MINITEST) == STATUS_ERROR


def test_rspec_failure_is_failed():
    assert _classify(1, RSPEC_FAIL, "", RSPEC) == STATUS_FAILED


def test_minitest_regex_does_not_match_rspec_output():
    # A Minitest task whose output only has RSpec-style text never ran Minitest.
    assert _classify(1, RSPEC_FAIL, "", MINITEST) == STATUS_ERROR
