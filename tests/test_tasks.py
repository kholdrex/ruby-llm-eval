from pathlib import Path

import pytest

from ruby_llm_eval.tasks import (
    PROMPT_FILE,
    REFERENCE_FILE,
    TEST_FILES,
    discover_tasks,
    load_task,
    read_version,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"
MINITEST_FILE = TEST_FILES["minitest"]


def write_task(
    tasks_dir: Path,
    task_id: str,
    *,
    prompt: str = "Implement add(a, b).\n",
    test: str = 'require_relative "solution"\n',
    reference: str = "def add(a, b)\n  a + b\nend\n",
) -> Path:
    task_dir = tasks_dir / task_id
    task_dir.mkdir(parents=True)
    (task_dir / PROMPT_FILE).write_text(prompt, encoding="utf-8")
    (task_dir / MINITEST_FILE).write_text(test, encoding="utf-8")
    (task_dir / REFERENCE_FILE).write_text(reference, encoding="utf-8")
    return task_dir


def test_discovers_all_seed_tasks_sorted():
    tasks = discover_tasks(TASKS_DIR)
    assert len(tasks) >= 8
    ids = [t.id for t in tasks]
    assert ids == sorted(ids)
    assert "001_fizzbuzz" in ids


def test_only_filter():
    tasks = discover_tasks(TASKS_DIR, only=["001_fizzbuzz"])
    assert [t.id for t in tasks] == ["001_fizzbuzz"]


def test_unknown_task_id_raises():
    with pytest.raises(ValueError):
        discover_tasks(TASKS_DIR, only=["999_nope"])


def test_duplicate_selected_task_id_raises(tmp_path):
    write_task(tmp_path, "001_private")

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=["001_private", "001_private"])

    message = str(exc_info.value)
    assert "Duplicate task id(s)" in message
    assert "001_private" in message


@pytest.mark.parametrize("task_id", ["nested/001_private", "nested\\001_private", ".", ".."])
def test_path_like_selected_task_id_raises(tmp_path, task_id):
    write_task(tmp_path, "001_private")

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=[task_id])

    message = str(exc_info.value)
    assert "Invalid selected task id(s)" in message
    assert task_id in message
    assert "Task ids must be non-empty directory names, not paths" in message


def test_table_separator_selected_task_id_raises(tmp_path):
    write_task(tmp_path, "001_private")

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=["001|private"])

    message = str(exc_info.value)
    assert "Invalid selected task id(s)" in message
    assert "001|private" in message
    assert "non-printable characters or '|'" in message
    assert "Unknown task id" not in message


@pytest.mark.parametrize(
    ("task_id", "expected_label"),
    [
        ("001_private\n002_private", repr("001_private\n002_private")),
        ("001_private\r", repr("001_private\r")),
        ("001_private\x00", repr("001_private\x00")),
        ("001_private\u200b", repr("001_private\u200b")),
    ],
)
def test_non_printable_selected_task_id_raises(tmp_path, task_id, expected_label):
    write_task(tmp_path, "001_private")

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=[task_id])

    message = str(exc_info.value)
    assert "Invalid selected task id(s)" in message
    assert expected_label in message
    assert "must not contain control or non-printable characters" in message
    assert "Unknown task id" not in message


@pytest.mark.parametrize(("task_id", "label"), [("", "<empty>"), ("   ", "<blank>")])
def test_blank_selected_task_id_raises(tmp_path, task_id, label):
    write_task(tmp_path, "001_private")

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=[task_id])

    message = str(exc_info.value)
    assert "Invalid selected task id(s)" in message
    assert label in message
    assert "Task ids must be non-empty directory names" in message
    assert "Unknown task id" not in message


@pytest.mark.parametrize(
    ("task_id", "expected_label"),
    [
        (" 001_private", " 001_private"),
        ("001_private ", "001_private "),
        ("\t001_private", repr("\t001_private")),
    ],
)
def test_padded_selected_task_id_raises(tmp_path, task_id, expected_label):
    write_task(tmp_path, "001_private")

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=[task_id])

    message = str(exc_info.value)
    assert "Invalid selected task id(s)" in message
    assert expected_label in message
    assert "Task ids must be non-empty directory names" in message
    assert "Unknown task id" not in message


def test_padded_selected_task_ids_report_all_invalid_ids(tmp_path):
    write_task(tmp_path, "001_private")
    leading_padded = " 002_private"
    trailing_padded = "003_private "
    tab_padded = "\t004_private"

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(
            tmp_path,
            only=["001_private", leading_padded, trailing_padded, tab_padded],
        )

    message = str(exc_info.value)
    assert "Invalid selected task id(s)" in message
    assert leading_padded in message
    assert trailing_padded in message
    assert repr(tab_padded) in message
    assert "001_private" not in message


def test_padded_selected_task_id_is_rejected_before_unknown_handling(tmp_path):
    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=[" 999_nope"])

    message = str(exc_info.value)
    assert "Invalid selected task id(s)" in message
    assert " 999_nope" in message
    assert "Unknown task id" not in message


def test_path_like_selected_task_ids_report_all_invalid_ids(tmp_path):
    write_task(tmp_path, "001_private")

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(
            tmp_path, only=["001_private", "nested/002_private", "..", "nested\\003_private"]
        )

    message = str(exc_info.value)
    assert "Invalid selected task id(s)" in message
    assert "nested/002_private" in message
    assert ".." in message
    assert "nested\\003_private" in message
    assert "001_private" not in message


def test_invalid_selected_task_ids_report_blank_and_path_like_ids(tmp_path):
    write_task(tmp_path, "001_private")

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=["", "001_private", "../outside", "\t"])

    message = str(exc_info.value)
    assert "Invalid selected task id(s)" in message
    assert "<empty>" in message
    assert "../outside" in message
    assert "<blank>" in message
    assert "001_private" not in message


def test_path_like_selected_task_id_is_rejected_before_unknown_handling(tmp_path):
    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=["missing/001_private"])

    message = str(exc_info.value)
    assert "Invalid selected task id(s)" in message
    assert "missing/001_private" in message
    assert "Unknown task id" not in message


def test_parent_path_selected_task_id_is_rejected_before_interpreting_outside_path(tmp_path):
    outside_task_id = f"{tmp_path.name}_outside"
    write_task(tmp_path.parent, outside_task_id)
    selected_id = f"../{outside_task_id}"

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=[selected_id])

    message = str(exc_info.value)
    assert "Invalid selected task id(s)" in message
    assert selected_id in message
    assert "Unknown task id" not in message


def test_path_like_selected_task_id_is_rejected_before_duplicate_handling(tmp_path):
    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=[".", "."])

    message = str(exc_info.value)
    assert "Invalid selected task id(s)" in message
    assert "Duplicate task id" not in message


def test_selected_task_file_reports_not_directory(tmp_path):
    (tmp_path / "001_private").write_text("not a task directory", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=["001_private"])

    message = str(exc_info.value)
    assert "Selected task id(s) are not directories" in message
    assert "001_private" in message


def test_selected_task_files_report_all_not_directories(tmp_path):
    write_task(tmp_path, "001_valid")
    (tmp_path / "002_file").write_text("not a task directory", encoding="utf-8")
    (tmp_path / "003_file").write_text("not a task directory", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=["001_valid", "002_file", "003_file"])

    message = str(exc_info.value)
    assert "Selected task id(s) are not directories" in message
    assert "002_file" in message
    assert "003_file" in message


def test_selected_malformed_task_reports_missing_prompt(tmp_path):
    (tmp_path / "001_missing_prompt").mkdir()

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=["001_missing_prompt"])

    message = str(exc_info.value)
    assert "001_missing_prompt" in message
    assert "missing prompt.md" in message


def test_selected_malformed_task_reports_missing_reference(tmp_path):
    task_dir = write_task(tmp_path, "001_missing_reference")
    (task_dir / REFERENCE_FILE).unlink()

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=["001_missing_reference"])

    message = str(exc_info.value)
    assert "001_missing_reference" in message
    assert "missing solution_ref.rb" in message


def test_selected_malformed_task_reports_missing_test_file(tmp_path):
    task_dir = write_task(tmp_path, "001_missing_test")
    (task_dir / MINITEST_FILE).unlink()

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=["001_missing_test"])

    message = str(exc_info.value)
    assert "001_missing_test" in message
    assert "has no test file" in message
    assert "test.rb / spec.rb" in message


def test_selected_malformed_task_reports_multiple_test_files(tmp_path):
    task_dir = write_task(tmp_path, "001_multiple_tests")
    (task_dir / TEST_FILES["rspec"]).write_text('require_relative "solution"\n', encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=["001_multiple_tests"])

    message = str(exc_info.value)
    assert "001_multiple_tests" in message
    assert "multiple test files" in message
    assert "test.rb / spec.rb" in message


def test_selected_malformed_task_reports_multiple_file_errors(tmp_path):
    task_dir = tmp_path / "001_multiple_file_issues"
    task_dir.mkdir()
    (task_dir / TEST_FILES["minitest"]).write_text(
        'require_relative "solution"\n',
        encoding="utf-8",
    )
    (task_dir / TEST_FILES["rspec"]).write_text(
        'require_relative "solution"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=["001_multiple_file_issues"])

    message = str(exc_info.value)
    assert "001_multiple_file_issues" in message
    assert "missing prompt.md" in message
    assert "missing solution_ref.rb" in message
    assert "has multiple test files" in message


def test_selected_malformed_task_reports_missing_reference_and_test_file(tmp_path):
    task_dir = tmp_path / "001_missing_reference_and_test"
    task_dir.mkdir()
    (task_dir / PROMPT_FILE).write_text("Implement add(a, b).\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=["001_missing_reference_and_test"])

    message = str(exc_info.value)
    assert "001_missing_reference_and_test" in message
    assert "missing solution_ref.rb" in message
    assert "has no test file" in message


def test_task_has_reference_and_test():
    task = load_task(TASKS_DIR / "001_fizzbuzz")
    assert "fizzbuzz" in task.prompt.lower()
    assert "require_relative" in task.test
    assert "def fizzbuzz" in task.reference()


def test_discovers_valid_custom_task(tmp_path):
    write_task(tmp_path, "002_second")
    write_task(tmp_path, "001_first")

    tasks = discover_tasks(tmp_path)

    assert [task.id for task in tasks] == ["001_first", "002_second"]
    assert tasks[0].prompt == "Implement add(a, b).\n"
    assert tasks[0].test == 'require_relative "solution"\n'
    assert tasks[0].reference() == "def add(a, b)\n  a + b\nend\n"


def test_load_task_rejects_table_separator_task_directory_id(tmp_path):
    task_dir = write_task(tmp_path, "001|bad")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "Task directory id 001|bad" in message
    assert "single-line report label" in message
    assert "or the '|' character" in message


def test_discover_tasks_rejects_default_task_directory_id_with_table_separator(tmp_path):
    write_task(tmp_path, "001|bad")

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path)

    message = str(exc_info.value)
    assert "Task directory id 001|bad" in message
    assert "single-line report label" in message
    assert "or the '|' character" in message


def test_discover_tasks_rejects_default_task_directory_id_with_non_printable_char(tmp_path):
    task_id = "001_bad\x7fname"
    write_task(tmp_path, task_id)

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path)

    message = str(exc_info.value)
    assert f"Task directory id {task_id!r}" in message
    assert "single-line report label" in message
    assert "control or non-printable characters" in message


@pytest.mark.parametrize(
    ("filename", "overrides"),
    [
        ("prompt.md", {"prompt": "\n\t  \n"}),
        ("test.rb", {"test": "\n\t  \n"}),
        ("solution_ref.rb", {"reference": "\n\t  \n"}),
    ],
)
def test_load_task_rejects_blank_required_files(tmp_path, filename, overrides):
    task_dir = write_task(tmp_path, "001_blank", **overrides)

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_blank" in message
    assert filename in message
    assert "empty required file" in message


@pytest.mark.parametrize(
    ("task_id", "test_filename", "test_contents"),
    [
        ("001_missing_solution_require", MINITEST_FILE, 'require "minitest/autorun"\n'),
        (
            "001_missing_solution_require_rspec",
            TEST_FILES["rspec"],
            'RSpec.describe "task" do\n  it("works") { expect(true).to eq(true) }\nend\n',
        ),
    ],
)
def test_load_task_rejects_test_file_without_solution_requirement(
    tmp_path, task_id, test_filename, test_contents
):
    task_dir = write_task(tmp_path, task_id)
    (task_dir / MINITEST_FILE).unlink()
    (task_dir / test_filename).write_text(test_contents, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert task_id in message
    assert test_filename in message
    assert 'require_relative "solution"' in message
    assert "solution.rb" in message


def test_load_task_accepts_solution_requirement_with_single_quotes_and_indentation(tmp_path):
    task_dir = write_task(
        tmp_path,
        "001_single_quote_solution_require",
        test="require \"minitest/autorun\"\n  require_relative 'solution'\n",
    )

    task = load_task(task_dir)

    assert task.framework == "minitest"
    assert "require_relative 'solution'" in task.test


@pytest.mark.parametrize(
    "test_contents",
    [
        'require "minitest/autorun"\nrequire_relative "solution" # load benchmark implementation\n',
        'require "minitest/autorun"\nrequire_relative("solution")\n',
        'require "minitest/autorun"\n'
        'require_relative( "solution" ) # load benchmark implementation\n',
    ],
)
def test_load_task_accepts_executable_solution_requirement_variants(tmp_path, test_contents):
    task_dir = write_task(
        tmp_path,
        "001_solution_require_variant",
        test=test_contents,
    )

    task = load_task(task_dir)

    assert task.framework == "minitest"
    assert task.test == test_contents


def test_load_task_accepts_solution_requirement_after_escaped_single_quote_marker_text(tmp_path):
    task_dir = write_task(
        tmp_path,
        "001_solution_require_after_escaped_single_quote_marker_text",
        test="puts 'it\\'s <<~RUBY'\nrequire_relative \"solution\"\n",
    )

    task = load_task(task_dir)

    assert task.framework == "minitest"
    assert 'require_relative "solution"' in task.test


def test_load_task_rejects_solution_requirement_inside_heredoc_only(tmp_path):
    task_dir = write_task(
        tmp_path,
        "001_solution_require_in_heredoc",
        test=(
            'require "minitest/autorun"\nsnippet = <<~RUBY\n  require_relative "solution"\nRUBY\n'
        ),
    )

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_solution_require_in_heredoc" in message
    assert MINITEST_FILE in message
    assert 'require_relative "solution"' in message


def test_load_task_rejects_solution_requirement_inside_block_comment(tmp_path):
    task_dir = write_task(
        tmp_path,
        "001_solution_require_in_block_comment",
        test='=begin\nrequire_relative "solution"\n=end\n',
    )

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_solution_require_in_block_comment" in message
    assert MINITEST_FILE in message
    assert 'require_relative "solution"' in message


@pytest.mark.parametrize(
    ("task_id", "test_contents"),
    [
        (
            "001_solution_require_after_string_marker_text",
            'puts "<<~RUBY"\nrequire_relative "solution"\n',
        ),
        (
            "001_solution_require_after_percent_literal_marker_text",
            'puts %q(<<~RUBY)\nrequire_relative "solution"\n',
        ),
        (
            "001_solution_require_after_backtick_marker_text",
            'puts `<<~RUBY`\nrequire_relative "solution"\n',
        ),
        (
            "001_solution_require_after_regex_marker_text",
            'puts(/<<~RUBY/)\nrequire_relative "solution"\n',
        ),
        (
            "001_solution_require_after_command_form_regex_marker_text",
            'puts /<<~RUBY/\nrequire_relative "solution"\n',
        ),
        (
            "001_solution_require_after_keyword_regex_marker_text",
            'if /<<~RUBY/.match?("marker")\nend\nrequire_relative "solution"\n',
        ),
    ],
)
def test_load_task_accepts_solution_requirement_after_non_heredoc_marker_text(
    tmp_path, task_id, test_contents
):
    task_dir = write_task(
        tmp_path,
        task_id,
        test=test_contents,
    )

    task = load_task(task_dir)

    assert task.framework == "minitest"
    assert 'require_relative "solution"' in task.test


def test_load_task_rejects_solution_requirement_inside_expression_heredoc(tmp_path):
    task_dir = write_task(
        tmp_path,
        "001_solution_require_in_expression_heredoc",
        test='puts(<<~RUBY)\nrequire_relative "solution"\nRUBY\n',
    )

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_solution_require_in_expression_heredoc" in message
    assert MINITEST_FILE in message
    assert 'require_relative "solution"' in message


def test_load_task_rejects_solution_requirement_inside_slash_adjacent_heredoc(tmp_path):
    task_dir = write_task(
        tmp_path,
        "001_solution_require_in_slash_adjacent_heredoc",
        test='value = 1 / <<~RUBY\nrequire_relative "solution"\nRUBY\n',
    )

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_solution_require_in_slash_adjacent_heredoc" in message
    assert MINITEST_FILE in message
    assert 'require_relative "solution"' in message


def test_load_task_rejects_solution_requirement_inside_tight_slash_adjacent_heredoc(tmp_path):
    task_dir = write_task(
        tmp_path,
        "001_solution_require_in_tight_slash_adjacent_heredoc",
        test='value = 1/<<~RUBY\nrequire_relative "solution"\nRUBY\n',
    )

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_solution_require_in_tight_slash_adjacent_heredoc" in message
    assert MINITEST_FILE in message
    assert 'require_relative "solution"' in message


def test_load_task_rejects_solution_requirement_after_ruby_end_data_marker(tmp_path):
    task_dir = write_task(
        tmp_path,
        "001_solution_require_after_end_data",
        test='require "minitest/autorun"\n__END__\nrequire_relative "solution"\n',
    )

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_solution_require_after_end_data" in message
    assert MINITEST_FILE in message
    assert 'require_relative "solution"' in message


def test_load_task_rejects_solution_requirement_inside_second_parallel_heredoc(tmp_path):
    task_dir = write_task(
        tmp_path,
        "001_solution_require_in_second_parallel_heredoc",
        test='puts(<<~FIRST, <<~SECOND)\nignored\nFIRST\nrequire_relative "solution"\nSECOND\n',
    )

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_solution_require_in_second_parallel_heredoc" in message
    assert MINITEST_FILE in message
    assert 'require_relative "solution"' in message


@pytest.mark.parametrize("filename", [PROMPT_FILE, MINITEST_FILE, REFERENCE_FILE])
def test_load_task_rejects_required_files_with_invalid_utf8(tmp_path, filename):
    task_dir = write_task(tmp_path, "001_bad_encoding")
    (task_dir / filename).write_bytes(b"valid prefix\xff\xfe\n")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_bad_encoding" in message
    assert filename in message
    assert "must be UTF-8 text" in message
    assert "offset" in message
    assert exc_info.value.__cause__ is None


def test_load_task_rejects_rspec_required_file_with_invalid_utf8(tmp_path):
    task_dir = write_task(tmp_path, "001_bad_rspec_encoding")
    (task_dir / MINITEST_FILE).unlink()
    spec_file = TEST_FILES["rspec"]
    (task_dir / spec_file).write_bytes(b"valid prefix\xff\xfe\n")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_bad_rspec_encoding" in message
    assert spec_file in message
    assert "must be UTF-8 text" in message
    assert "offset" in message


def test_detects_minitest_framework():
    task = load_task(TASKS_DIR / "001_fizzbuzz")
    assert task.framework == "minitest"
    assert task.test_filename == "test.rb"


def test_detects_rspec_framework():
    task = load_task(TASKS_DIR / "016_stack")
    assert task.framework == "rspec"
    assert task.test_filename == "spec.rb"
    assert "RSpec.describe" in task.test


def test_activerecord_task_present():
    task = load_task(TASKS_DIR / "017_ar_scopes")
    assert task.framework == "minitest"
    assert "ActiveRecord::Base" in task.reference()
    assert "active_record" in task.test


def test_rails_task_is_categorized():
    assert load_task(TASKS_DIR / "017_ar_scopes").category == "rails"


def test_category_defaults_to_general():
    assert load_task(TASKS_DIR / "001_fizzbuzz").category == "general"


def test_load_task_rejects_meta_yml_with_invalid_utf8(tmp_path):
    task_dir = write_task(tmp_path, "001_bad_meta_encoding")
    (task_dir / "meta.yml").write_bytes(b"category: general\xff\xfe\n")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_bad_meta_encoding" in message
    assert "meta.yml" in message
    assert "must be UTF-8 text" in message
    assert "offset" in message
    assert exc_info.value.__cause__ is None


def test_load_task_rejects_meta_yml_with_non_mapping_top_level(tmp_path):
    task_dir = write_task(tmp_path, "001_list_meta")
    (task_dir / "meta.yml").write_text("- category\n- rails\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_list_meta" in message
    assert "meta.yml" in message
    assert "YAML mapping/object" in message


def test_load_task_rejects_malformed_meta_yml(tmp_path):
    task_dir = write_task(tmp_path, "001_malformed_meta")
    (task_dir / "meta.yml").write_text("category: [rails\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_malformed_meta" in message
    assert "meta.yml" in message
    assert "must be valid YAML" in message
    assert "Traceback" not in message
    assert exc_info.value.__cause__ is None


def test_load_task_rejects_meta_yml_with_unknown_key(tmp_path):
    task_dir = write_task(tmp_path, "001_unknown_meta")
    (task_dir / "meta.yml").write_text("difficulty: hard\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_unknown_meta" in message
    assert "meta.yml" in message
    assert "unknown key" in message
    assert "difficulty" in message
    assert "category" in message


@pytest.mark.parametrize(
    "meta",
    [
        "1: numeric\n",
        "true: boolean\n",
        "null: missing\n",
        "category: rails\n2: numeric\n",
    ],
)
def test_load_task_rejects_meta_yml_with_non_string_key(tmp_path, meta):
    task_dir = write_task(tmp_path, "001_non_string_meta_key")
    (task_dir / "meta.yml").write_text(meta, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_non_string_meta_key" in message
    assert "meta.yml" in message
    assert "non-string key" in message
    assert "keys must be strings" in message
    assert "unknown key" not in message


def test_load_task_rejects_meta_yml_with_multiple_unknown_keys(tmp_path):
    task_dir = write_task(tmp_path, "001_unknown_meta_keys")
    (task_dir / "meta.yml").write_text(
        "category: rails\ndifficulty: hard\ntags: private\n", encoding="utf-8"
    )

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_unknown_meta_keys" in message
    assert "meta.yml" in message
    assert "unknown key" in message
    assert "difficulty" in message
    assert "tags" in message


@pytest.mark.parametrize("meta", ["", "category: ''\n", "category: '   '\n", "category:\n"])
def test_meta_yml_empty_or_blank_category_defaults_to_general(tmp_path, meta):
    task_dir = write_task(tmp_path, "001_default_category")
    (task_dir / "meta.yml").write_text(meta, encoding="utf-8")

    assert load_task(task_dir).category == "general"


@pytest.mark.parametrize(
    "meta",
    [
        "category:\n  - rails\n",
        "category:\n  name: rails\n",
        "category: 123\n",
        "category: 1.5\n",
        "category: true\n",
    ],
)
def test_load_task_rejects_non_string_meta_category(tmp_path, meta):
    task_dir = write_task(tmp_path, "001_bad_category")
    (task_dir / "meta.yml").write_text(meta, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_bad_category" in message
    assert "meta.yml" in message
    assert "field 'category' must be a string" in message


@pytest.mark.parametrize(
    "meta",
    [
        "category: 'rails|security'\n",
        'category: "rails\\nsecurity"\n',
        'category: "rails\\rsecurity"\n',
        'category: "rails\\tsecurity"\n',
        'category: "rails\\x7fsecurity"\n',
        'category: "rails\\Nsecurity"\n',
        'category: "rails\\Lsecurity"\n',
        'category: "rails\\Psecurity"\n',
    ],
)
def test_load_task_rejects_unsafe_report_category_labels(tmp_path, meta):
    task_dir = write_task(tmp_path, "001_bad_category_label")
    (task_dir / "meta.yml").write_text(meta, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_bad_category_label" in message
    assert "meta.yml" in message
    assert "field 'category'" in message
    assert "single-line report label" in message


def test_rails_migration_task_present():
    task = load_task(TASKS_DIR / "021_ar_migration")
    assert "ActiveRecord::Migration" in task.reference()
    assert "migrate(:up)" in task.test


def test_rails_controller_task_present():
    task = load_task(TASKS_DIR / "022_rails_controller")
    assert "ActionController::Base" in task.reference()
    assert "rack/test" in task.test


def test_harder_tasks_present():
    for task_id in ("025_basic_calculator", "027_text_justification"):
        task = load_task(TASKS_DIR / task_id)
        assert task.framework == "minitest"
        assert task.prompt.strip()


def test_version_is_recorded():
    assert read_version(TASKS_DIR) == "0.6.0"


def test_blank_version_defaults_to_unknown(tmp_path):
    (tmp_path / "VERSION").write_text("  \n", encoding="utf-8")

    assert read_version(tmp_path) == "unknown"


@pytest.mark.parametrize("version", ["0.6.0|bad", "0.6.0\n0.7.0", "0.6.0\x00", "0.6.0\u200b"])
def test_unsafe_version_label_raises(tmp_path, version):
    (tmp_path / "VERSION").write_text(version, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        read_version(tmp_path)

    message = str(exc_info.value)
    assert "Task set VERSION file" in message
    assert "single-line report label" in message
    assert "control characters or '|'" in message


def test_rails_category_count():
    rails = [t for t in discover_tasks(TASKS_DIR) if t.category == "rails"]
    assert len(rails) >= 14
    assert all(t.framework == "minitest" for t in rails)
