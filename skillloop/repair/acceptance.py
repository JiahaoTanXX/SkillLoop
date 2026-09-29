"""Sanitized milestone review of independently recomputed private M6 reports.

This checks report consistency. The caller must first recompute the underlying
application, model traces, SQLite state, scans and plans with the private Gate.
"""

from skillloop.protocol import digest_jcs


PROFILES = ('orders_total', 'refunds_total', 'markdown_index')


def review(reports: list[dict], *, m5_gate_digest: str) -> dict:
    return _review(reports, m5_gate_digest=m5_gate_digest, required_profiles=PROFILES)


def review_profile(reports: list[dict], *, profile: str, m5_gate_digest: str) -> dict:
    """Explicit single-profile receipt; never replaces the global M6 review."""
    if profile not in PROFILES:
        raise ValueError("m6_profile_unregistered")
    if any(set(r.get("subjects", {})) != {profile} for r in reports):
        raise ValueError("m6_profile_scope_mismatch")
    result = _review(reports, m5_gate_digest=m5_gate_digest, required_profiles=(profile,))
    result.pop("digest")
    result.update(kind="M6ProfileAcceptanceReview", scope=[profile], global_m6_accepted=False)
    return {**result, "digest": digest_jcs(result)}


def _review(reports: list[dict], *, m5_gate_digest: str, required_profiles: tuple) -> dict:
    selected, evidence, reasons, limitations = {}, [], [], []
    config = reducer = None
    profile_campaigns, profile_gates = {}, {}
    for report in reports:
        unsigned = {k: v for k, v in report.items() if k != 'digest'}
        if (report.get('kind') != 'M6IndependentGate' or report.get('digest') != digest_jcs(unsigned)
                or report.get('baseline_gate_digest') != m5_gate_digest
                or report.get('production_ready') is not False
                or report.get('protected_evaluation') != 'not_started'):
            raise ValueError('m6_report_binding')
        if (not report.get('campaign_id') or not report.get('campaign_manifest_digest') or
                not report.get('config_digest') or not report.get('reducer_source_digest')):
            raise ValueError('m6_campaign_binding_missing')
        if config is None:
            config = report['config_digest']
            reducer = report['reducer_source_digest']
        elif config != report['config_digest'] or reducer != report['reducer_source_digest']:
            raise ValueError('m6_cross_campaign_or_config')
        parents = report.get('parent_gate_digests', [])
        repeated_profiles = set(report['subjects']).intersection(selected)
        if (any(profile_campaigns[p] != report['campaign_id'] for p in repeated_profiles)):
            raise ValueError('m6_cross_campaign_or_config')
        if (any(profile_gates[p] not in parents for p in repeated_profiles) or
                any(parent not in evidence for parent in parents)):
            raise ValueError('m6_gate_lineage')
        evidence.append(report['digest'])
        for profile, row in report['subjects'].items():
            if profile not in PROFILES:
                raise ValueError('m6_profile_unregistered')
            previous = selected.get(profile)
            if (previous and previous.get('subject_digest') == row.get('subject_digest') and
                    not set(previous.get('known_failures', [])).issubset(row.get('known_failures', []))):
                raise ValueError('m6_sticky_failure_removed')
            selected[profile] = row
            profile_campaigns[profile] = report['campaign_id']
            profile_gates[profile] = report['digest']
    summaries = {}
    for profile in required_profiles:
        row = selected.get(profile)
        if row is None:
            reasons.append(profile + ':report_missing')
            continue
        blockers = []
        if (row.get('verdict') != 'pass' or row.get('missing') or row.get('known_failures')
                or row.get('unresolved_high') or row.get('scan_complete') is not True):
            blockers.append('candidate_development_not_passed')
        cases = row.get('case_results', [])
        if (len(cases) != row.get('required_cases') or
                len({c['body']['case_digest'] for c in cases}) != len(cases) or
                any(c['body']['subject_digest'] != row.get('subject_digest') or
                    c['body']['coverage_complete'] is not True or
                    c['body']['required_repetitions'] != 3 or
                    c['body']['completed_repetitions'] != 3 or
                    c['body']['utility_status'] != 'pass' or
                    c['body']['security_status'] != 'pass' for c in cases) or
                row.get('required_runs') != len(cases) * 3):
            blockers.append('candidate_case_matrix_incomplete')
        if (row.get('submitted_absent_items') or not row.get('submitted_required_runs') or
                row.get('submitted_executed_required_runs') != row.get('submitted_required_runs')):
            blockers.append('submitted_run_records_missing')
        if row.get('submitted_missing') or row.get('paired_development_coverage_complete') is not True:
            limitations.append(profile + ':submitted_pair_coverage_incomplete')
        if row.get('budget_bound_correction'):
            limitations.append(profile + ':initial_auxiliary_bounds_corrected_before_freeze')
        budget = row.get('budget', {})
        sealed = row.get('freeze', {})
        if budget.get('admission') != 'ready' or budget.get('reasons'):
            blockers.append('full_capacity_not_admitted')
        spending = row.get('spending_audit', {})
        if spending.get('admission') != 'ready' or spending.get('reasons'):
            blockers.append('actual_spending_not_verified')
        if row.get('frozen') is not True or sealed.get('status') != 'frozen':
            blockers.append('finalist_not_frozen')
        if sealed:
            before_freeze = {k: v for k, v in row.items() if k != 'freeze'}
            before_freeze['frozen'] = False
            if (sealed.get('digest') != digest_jcs({k: v for k, v in sealed.items() if k != 'digest'})
                    or sealed.get('subject') != row.get('subject_digest')
                    or sealed.get('development_gate_digest') != digest_jcs(before_freeze)
                    or sealed.get('budget_digest') != digest_jcs(budget)
                    or sealed.get('protected_evaluation') != 'not_started'):
                raise ValueError('m6_freeze_binding')
        if (not 1 <= row.get('applications_succeeded', 0) <= 2 or
                row.get('evaluable_candidates') != row.get('applications_succeeded') or
                not row.get('applications_succeeded', 0) <= row.get('generated_proposals', 0) <= 4 or
                row.get('reasoning_tokens') != 0 or row.get('model_responses', 0) < row.get('required_runs', 1)):
            blockers.append('model_or_repair_accounting_invalid')
        reasons.extend(profile + ':' + blocker for blocker in blockers)
        summaries[profile] = {k: row.get(k) for k in ('subject_digest', 'verdict', 'required_cases',
            'required_runs', 'generated_proposals', 'applications_succeeded', 'evaluable_candidates',
            'submitted_verdict', 'paired_to_submitted', 'frozen', 'reasoning_tokens')}
        summaries[profile]['blockers'] = blockers
    campaigns = set(profile_campaigns.values())
    body = {'kind':'M6AcceptanceReview', 'status':'pending' if reasons else 'ready_with_limits' if limitations else 'ready',
        'campaign_id':next(iter(campaigns)) if len(campaigns) == 1 else None,
        'profile_campaign_ids':profile_campaigns, 'config_digest':config, 'reducer_source_digest':reducer,
        'm5_gate_digest':m5_gate_digest, 'independent_gate_digests':evidence,
        'subjects':summaries, 'reasons':reasons, 'limitations':limitations, 'm7_entry_ready':not reasons,
        'protected_evaluation':'not_started', 'production_ready':False}
    return {**body, 'digest':digest_jcs(body)}
