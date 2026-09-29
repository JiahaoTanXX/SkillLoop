"""Read-only API parallel-scope preflight; no model request or clock reset."""
import json,sys,time
from decimal import Decimal,ROUND_CEILING
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from skillloop.protocol import digest_jcs

def preflight(*,limit_rmb='10.00',reserved_micro=26336):
    input_rate=Decimal('0.8');output_rate=Decimal('2.7')
    def cost(runs):return int((Decimal(runs)*16*(14336*input_rate+2048*output_rate)).to_integral_value(rounding=ROUND_CEILING))
    auxiliary_micro=int((649216*input_rate+88064*output_rate).to_integral_value(rounding=ROUND_CEILING))
    profiles={
        'orders_total':{'stage':'M7','required_new_development_runs':42,'protected_runs':24,'new_model_full_capacity_runs':66,'retry_reserve':2},
        'refunds_total':{'stage':'M6','required_development_runs':66,'protected_capacity_runs':24,'new_model_full_capacity_runs':90,'retry_reserve':2},
        'markdown_index':{'stage':'M6','required_development_runs':48,'protected_capacity_runs':24,'new_model_full_capacity_runs':72,'retry_reserve':2}}
    for p,row in profiles.items():
        row['conservative_token_forecast_micro_rmb']=cost(row['new_model_full_capacity_runs']+2)+auxiliary_micro
        row['formal_admission']='rejected'
        row['reasons']=['shared_cost_limit_exceeded','raw_reasoning_usage_unavailable','new_backend_calibration_not_accepted']
        row['model_runs_started']=0
    total=sum(r['conservative_token_forecast_micro_rmb'] for r in profiles.values())+reserved_micro
    body={'kind':'APIParallelAdmissionReport','model':'qwen3.8-flash','enable_thinking':False,
        'at_unix_ms':int(time.time()*1000),'shared_limit_micro_rmb':int(Decimal(limit_rmb)*1000000),
        'calibration_charged_or_reserved_micro_rmb':reserved_micro,'profiles':profiles,
        'minimum_requested_matrix_runs':138,'minimum_requested_matrix_forecast_micro_rmb':cost(138),
        'full_capacity_forecast_micro_rmb':total,'admission':'rejected','raw_reasoning_tokens':None,
        'existing_source_snapshots_unchanged':True,'existing_clocks_reset':False,
        'scores_merged_across_model_configuration':False,'new_api_matrix_model_requests':0,
        'limitations':['matrix_counts_from_existing_requirements;new_discovery_may_add_cases',
            'API calibration does not replace genuine family task calibration',
            'shared cost limit remains 10 RMB;no per-profile duplicate allowance']}
    return {**body,'digest':digest_jcs(body)}
if __name__=='__main__':
    print(json.dumps(preflight(),ensure_ascii=False,indent=2))
