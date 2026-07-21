from __future__ import annotations

from evaluator_worker.config import EvaluatorWorkerSettings
from evaluator_worker.domain.models import GateDecision, GateResult, Scorecard


class CanaryGate:
    """Compare scorecard vs thresholds / baseline; block promote on regression (LLD §15)."""

    def __init__(self, settings: EvaluatorWorkerSettings) -> None:
        self._settings = settings

    def decide(
        self,
        scorecard: Scorecard,
        *,
        baseline: Scorecard | None = None,
    ) -> GateResult:
        reasons: list[str] = []
        kind = scorecard.kind.value

        if kind == "retrieval_recall":
            recall = scorecard.metric("recall_at_k") or 0.0
            if recall < self._settings.min_retrieval_recall_at_k:
                reasons.append(
                    f"recall_at_k {recall:.3f} < min {self._settings.min_retrieval_recall_at_k}"
                )
            self._check_regression(
                scorecard, baseline, "recall_at_k", reasons, higher_is_better=True
            )

        elif kind == "agent_success":
            rate = scorecard.metric("success_rate") or 0.0
            if rate < self._settings.min_agent_success_rate:
                reasons.append(
                    f"success_rate {rate:.3f} < min {self._settings.min_agent_success_rate}"
                )
            self._check_regression(
                scorecard, baseline, "success_rate", reasons, higher_is_better=True
            )

        elif kind == "attribution":
            rate = scorecard.metric("unsupported_claim_rate") or 0.0
            if rate > self._settings.max_unsupported_claim_rate:
                reasons.append(
                    f"unsupported_claim_rate {rate:.3f} > max "
                    f"{self._settings.max_unsupported_claim_rate}"
                )
            self._check_regression(
                scorecard,
                baseline,
                "unsupported_claim_rate",
                reasons,
                higher_is_better=False,
            )

        elif kind == "safety":
            rate = scorecard.metric("fail_rate") or 0.0
            if rate > self._settings.max_safety_fail_rate:
                reasons.append(
                    f"fail_rate {rate:.3f} > max {self._settings.max_safety_fail_rate}"
                )
            self._check_regression(
                scorecard, baseline, "fail_rate", reasons, higher_is_better=False
            )

        elif kind == "cost":
            usd = scorecard.metric("total_usd_micros") or 0.0
            if usd > self._settings.max_cost_usd_micros:
                reasons.append(
                    f"total_usd_micros {usd:.0f} > max {self._settings.max_cost_usd_micros}"
                )
            self._check_regression(
                scorecard,
                baseline,
                "total_usd_micros",
                reasons,
                higher_is_better=False,
            )

        decision = GateDecision.BLOCK if reasons else GateDecision.PROMOTE
        return GateResult(
            decision=decision,
            reasons=tuple(reasons),
            scorecard_id=scorecard.id,
            baseline_scorecard_id=baseline.id if baseline else None,
        )

    def _check_regression(
        self,
        scorecard: Scorecard,
        baseline: Scorecard | None,
        metric_name: str,
        reasons: list[str],
        *,
        higher_is_better: bool,
    ) -> None:
        if baseline is None:
            return
        current = scorecard.metric(metric_name)
        prior = baseline.metric(metric_name)
        if current is None or prior is None or prior == 0:
            return
        if higher_is_better:
            drop = (prior - current) / abs(prior)
            if drop > self._settings.max_regression:
                reasons.append(
                    f"{metric_name} regressed {drop:.3f} > max {self._settings.max_regression}"
                )
        else:
            rise = (current - prior) / abs(prior)
            if rise > self._settings.max_regression:
                reasons.append(
                    f"{metric_name} worsened {rise:.3f} > max {self._settings.max_regression}"
                )
