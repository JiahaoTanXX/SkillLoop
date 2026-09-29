"""Immutable admission clocks for separately admitted profile campaigns."""

from skillloop.protocol import digest_jcs


def make_clock(campaign: str, profile: str, started_at_unix_ms: int) -> dict:
    if not campaign or not profile or type(started_at_unix_ms) is not int or started_at_unix_ms <= 0:
        raise ValueError('invalid_profile_admission_clock')
    body = {'kind': 'M6ProfileAdmissionClock', 'campaign_id': campaign,
            'profile': profile, 'started_at_unix_ms': started_at_unix_ms}
    return {**body, 'digest': digest_jcs(body)}


def start_seconds(manifest: dict, profile: str, *, legacy_started_at: float) -> float:
    clock = manifest.get('admission_clock')
    if clock is None:
        return legacy_started_at
    expected = make_clock(manifest['campaign_id'], profile, clock['started_at_unix_ms'])
    if clock != expected or set(manifest['subjects']) != {profile}:
        raise ValueError('profile_admission_clock_binding')
    return clock['started_at_unix_ms'] / 1000
