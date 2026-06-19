from ruby_llm_eval.evaluate import (
    STATUS_ERROR,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_TIMEOUT,
    _classify,
)

MINITEST_OK = "3 runs, 9 assertions, 0 failures, 0 errors, 0 skips"
MINITEST_FAIL = "3 runs, 9 assertions, 1 failures, 0 errors, 0 skips"


def test_exit_zero_is_passed():
    assert _classify(0, MINITEST_OK, "") == STATUS_PASSED


def test_exit_124_is_timeout():
    assert _classify(124, "", "") == STATUS_TIMEOUT


def test_failed_assertion_is_failed():
    assert _classify(1, MINITEST_FAIL, "") == STATUS_FAILED


def test_load_error_is_error():
    # No Minitest summary printed => the file blew up before tests ran.
    stderr = "solution.rb:1: syntax error, unexpected end-of-input"
    assert _classify(1, "", stderr) == STATUS_ERROR
