from ruby_llm_eval.pass_k import pass_at_k


def test_pass_at_1_is_fraction_passing():
    assert pass_at_k(n=5, c=0, k=1) == 0.0
    assert pass_at_k(n=5, c=5, k=1) == 1.0
    assert pass_at_k(n=5, c=1, k=1) == 0.2
    assert pass_at_k(n=4, c=3, k=1) == 0.75


def test_all_passing_is_one_for_any_k():
    assert pass_at_k(n=5, c=5, k=3) == 1.0


def test_none_passing_is_zero():
    assert pass_at_k(n=5, c=0, k=3) == 0.0


def test_more_passes_never_lowers_score():
    scores = [pass_at_k(n=10, c=c, k=2) for c in range(11)]
    assert scores == sorted(scores)


def test_known_estimator_value():
    # pass@2 with 1 of 5 passing: 1 - C(4,2)/C(5,2) = 1 - 6/10 = 0.4
    assert abs(pass_at_k(n=5, c=1, k=2) - 0.4) < 1e-9


def test_degenerate_inputs():
    assert pass_at_k(n=0, c=0, k=1) == 0.0
