"""pass@k estimation.

We use the standard unbiased estimator from the HumanEval paper (Chen et al.,
2021). For ``k = 1`` it reduces to ``c / n`` — the fraction of samples that
pass — which is exactly the pass@1 metric this tool reports today. The general
form is kept so pass@k for k > 1 (on the roadmap) drops in cleanly.
"""

from __future__ import annotations


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that at least one of ``k`` samples drawn from ``n`` passes.

    Args:
        n: total number of samples generated for the task.
        c: number of those samples that passed.
        k: the ``k`` in pass@k.
    """
    if n <= 0:
        return 0.0
    if c <= 0:
        return 0.0
    if k == 1:
        # Fast path: pass@1 is exactly the fraction passing (no float drift).
        return c / n
    if n - c < k:
        return 1.0
    # 1 - C(n-c, k) / C(n, k), computed iteratively to avoid overflow.
    prob_all_fail = 1.0
    for i in range(n - c + 1, n + 1):
        prob_all_fail *= 1.0 - k / i
    return 1.0 - prob_all_fail
