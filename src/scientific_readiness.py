"""Deterministic recommendation eligibility, shared by orchestration and reports.

These are completed review checks, not proof of experimental success. Elo is
deliberately absent: a tournament preference cannot override missing evidence.
"""
from datetime import datetime, timezone

SCIENTIFIC_REVIEW_VERSION = 1


def _record(value):
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()
    except (ValueError, TypeError):
        return 0.0


def assess_readiness(hypotheses, reviews, observation_reviews=()):
    latest = {}
    for value in reviews:
        review = _record(value)
        key = (review["hypothesis_id"], review["review_type"])
        if key not in latest or _timestamp(review.get("created_at")) >= _timestamp(latest[key].get("created_at")):
            latest[key] = review
    observations = {_record(r)["hypothesis_id"]: _record(r) for r in observation_reviews}
    result = {}
    for value in hypotheses:
        hypothesis = _record(value)
        hid = hypothesis["id"]
        own = {kind: review for (rid, kind), review in latest.items() if rid == hid}
        issues = []
        failed = False
        if not own:
            result[hid] = {"eligible": False, "status": "unreviewed", "issues": ["No scientific review completed."]}
            continue
        if hypothesis.get("status") in ("archived", "requires_safety_review"):
            issues.append("This hypothesis is withheld from recommendations.")
        for kind in ("full", "deep_verification"):
            label = kind.replace("_", " ")
            if kind not in own:
                issues.append(f"The {label} review is not complete.")
            elif own[kind].get("passed") is not True:
                issues.append(f"The latest {label} review failed.")
                failed = True
        if "simulation" in own and own["simulation"].get("passed") is not True:
            issues.append("The mechanism walkthrough review failed.")
            failed = True
        citations = hypothesis.get("literature_citations") or []
        if not citations:
            issues.append("No supporting citations were supplied.")
        elif any(c.get("verification_status") != "verified" for c in citations):
            issues.append("One or more supporting citation identities are unverified.")
        observed = observations.get(hid)
        if not (observed and observed.get("assessment_status", "complete") == "complete"
                and observed.get("observations_total_count", 0) > 0
                and observed.get("overall_score") is not None):
            issues.append("The retrieved-observation review is not complete.")
        result[hid] = {"eligible": not issues,
                       "status": "ready" if not issues else "failed" if failed else "partial",
                       "issues": issues}
    return result
