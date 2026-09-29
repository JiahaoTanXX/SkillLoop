"""Stable, independently checked snapshots of actual development spending."""

from copy import deepcopy
import math

from skillloop.protocol import digest_jcs
from skillloop.repair.budget import LIMITS
from skillloop.repair.clock import make_clock


def remaining_capacity(state: dict, *, started_at_unix_ms: int, at_unix_ms: int,
                       planned_attempts: int, auxiliary_seconds: int) -> dict:
    if (type(planned_attempts) is not int or planned_attempts < 0 or
            type(auxiliary_seconds) is not int or auxiliary_seconds < 0 or
            type(started_at_unix_ms) is not int or type(at_unix_ms) is not int or
            at_unix_ms < started_at_unix_ms):
        raise ValueError('remaining_capacity_inputs')
    elapsed = math.ceil(max(state['elapsed_seconds'], (at_unix_ms - started_at_unix_ms) / 1000))
    remaining = planned_attempts - state['victim_attempts']
    seconds = max(0, remaining) * 265 + auxiliary_seconds
    reasons = ['remaining_full_capacity_does_not_fit_clock'] if (
        remaining < 0 or elapsed + seconds > LIMITS['wall_seconds']) else []
    return {'admission':'rejected' if reasons else 'ready', 'reasons':reasons,
            'remaining_reserved_attempts':remaining, 'remaining_reserved_seconds':seconds,
            'observed_elapsed_seconds':elapsed}


def verify_state(state: dict, *, clock: dict, victim_seconds: int, executions: list[dict]) -> None:
    if (clock != make_clock(clock['campaign_id'], clock['profile'], clock['started_at_unix_ms']) or
            type(victim_seconds) is not int or victim_seconds <= 0 or
            type(state['elapsed_seconds']) not in (int, float) or
            not math.isfinite(state['elapsed_seconds']) or state['elapsed_seconds'] < 0):
        raise ValueError('spending_state_shape')
    keys = [(e['item_key'], e['attempt']) for e in state['executions']]
    expected = [(e['item_key'], e['attempt']) for e in executions]
    if (len(keys) != len(set(keys)) or len(expected) != len(set(expected)) or
            set(keys) != set(expected) or any(type(a) is not int or a not in (0, 1) for _, a in keys)):
        raise ValueError('spending_execution_bindings')
    if (type(state['victim_attempts']) is not int or state['victim_attempts'] != len(keys) or
            type(state['retries']) is not int or state['retries'] != sum(a for _, a in keys) or
            state['charged_wall_seconds'] != len(keys) * victim_seconds or
            state['campaign_started_at'] != clock['started_at_unix_ms'] / 1000):
        raise ValueError('spending_counters_or_clock')


def snapshot(state: dict, *, clock: dict, victim_seconds: int, executions: list[dict],
             finished_at_unix_ms: int, finalization_reserve_seconds: int = 600) -> dict:
    verify_state(state, clock=clock, victim_seconds=victim_seconds, executions=executions)
    if type(finished_at_unix_ms) is not int or finished_at_unix_ms < clock['started_at_unix_ms']:
        raise ValueError('spending_finish_clock')
    reasons = []
    elapsed = (finished_at_unix_ms - clock['started_at_unix_ms']) / 1000
    if state['victim_attempts'] > LIMITS['victim_attempts']:
        reasons.append('actual_victim_attempts_exceeded')
    if state['retries'] > LIMITS['retry_reserve']:
        reasons.append('actual_retry_reserve_exceeded')
    if (max(elapsed, state['elapsed_seconds']) + finalization_reserve_seconds > LIMITS['wall_seconds'] or
            state['charged_wall_seconds'] + finalization_reserve_seconds > LIMITS['wall_seconds']):
        reasons.append('actual_wall_or_finalization_reserve_exceeded')
    if any(e['last_write_unix_ms'] > finished_at_unix_ms for e in executions):
        raise ValueError('spending_closed_before_execution')
    body = {'kind': 'M6ClosedDevelopmentSpending', 'clock': deepcopy(clock),
            'finished_at_unix_ms': finished_at_unix_ms, 'victim_seconds': victim_seconds,
            'finalization_reserve_seconds': finalization_reserve_seconds,
            'ledger': deepcopy(state), 'executions': deepcopy(executions),
            'admission': 'rejected' if reasons else 'ready', 'reasons': reasons}
    return {**body, 'digest': digest_jcs(body)}


def verify_snapshot(record: dict, *, current_state: dict, clock: dict,
                    victim_seconds: int, executions: list[dict]) -> dict:
    if record.get('clock') != clock or record.get('victim_seconds') != victim_seconds:
        raise ValueError('spending_snapshot_scope')
    expected = snapshot(record['ledger'], clock=clock, victim_seconds=victim_seconds,
                        executions=executions, finished_at_unix_ms=record['finished_at_unix_ms'],
                        finalization_reserve_seconds=600)
    if expected != record:
        raise ValueError('spending_snapshot_changed')
    # Round two appends to the same ledger. An earlier proof checks its prefix.
    previous = record['ledger']['executions']
    if (current_state['executions'][:len(previous)] != previous or
            current_state['victim_attempts'] != len(current_state['executions']) or
            current_state['retries'] != sum(e['attempt'] for e in current_state['executions']) or
            current_state['charged_wall_seconds'] != len(current_state['executions']) * victim_seconds or
            current_state['campaign_started_at'] != clock['started_at_unix_ms'] / 1000):
        raise ValueError('spending_snapshot_prefix_or_current_counters')
    return record
