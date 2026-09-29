"""Local decisions never promote a failed submitted Skill via a passing repair."""
from skillloop.protocol import digest_jcs
CODES={'pass':0,'fail':1,'needs_contract':3,'inconclusive':4}

def decide(*, submitted_verdict, candidate_verdict, m7_accepted, source_kind, source_head=None):
    if submitted_verdict not in CODES or candidate_verdict not in CODES:raise ValueError('unknown_verdict')
    if type(m7_accepted) is not bool:raise ValueError('m7_accepted_type')
    if source_kind not in {'immutable_snapshot','git_commit'}:raise ValueError('source_kind')
    if source_kind=='git_commit' and (not isinstance(source_head,str) or len(source_head)!=40 or any(c not in '0123456789abcdef' for c in source_head)):
        raise ValueError('source_head')
    final_submitted=submitted_verdict if submitted_verdict in {'fail','needs_contract'} else (
        submitted_verdict if m7_accepted else 'inconclusive')
    final_candidate=candidate_verdict if candidate_verdict in {'fail','needs_contract'} else (
        candidate_verdict if m7_accepted else 'inconclusive')
    blockers=[]
    if not m7_accepted:blockers.append('m7_not_accepted')
    if source_kind!='git_commit':blockers.append('adopted_git_commit_missing')
    result={'kind':'LocalCIDecision','submitted_decision':final_submitted,'candidate_decision':final_candidate,
        'development_submitted_verdict':submitted_verdict,'development_candidate_verdict':candidate_verdict,
        'exit_code':CODES[final_submitted],'repair_required':final_submitted=='fail','publishable':not blockers and final_submitted=='pass',
        'blockers':blockers,'source_kind':source_kind,'source_head':source_head,
        'github_check_published':False,'production_ready':False}
    return {**result,'digest':digest_jcs(result)}
