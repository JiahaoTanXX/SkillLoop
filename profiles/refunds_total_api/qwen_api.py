"""Pinned compatible API transport; private file credentials, no automatic retries."""
import json,os,urllib.request
from pathlib import Path
from skillloop.protocol import digest_bytes, digest_jcs
from skillloop.protection.api_budget import ScopedAPIBudget

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):raise ValueError('api_redirect_denied')

class QwenAPITransport:
    def __init__(self,config,private_root:Path,*,shared_budget_path:Path|None=None):
        if config.get('base_url')!='https://maas.qianwenaiapi.com/compatible-mode/v1' or config.get('model')!='qwen3.8-flash':
            raise ValueError('api_identity_not_authorized')
        if config.get('enable_thinking') is not False or config.get('pricing_verified') is not True:
            raise ValueError('api_pricing_or_thinking_not_admitted')
        private_root.mkdir(mode=0o700,parents=True,exist_ok=True)
        if private_root.stat().st_mode&0o077:raise ValueError('api_private_directory')
        key_path=Path(config['credential_file'])
        if key_path.stat().st_mode&0o077:raise ValueError('api_credential_permissions')
        self.key=key_path.read_text().strip();self.config=dict(config);self.root=private_root
        self.budget=ScopedAPIBudget(shared_budget_path or (private_root/'cost.sqlite'),
            input_rate=config['input_price_per_million_rmb'],
            output_rate=config['output_price_per_million_rmb'],limit_rmb='50.00',
            legacy_limit_rmb=config['max_cost_rmb'],scope_id='m6-markdown-refunds-api-v1')
        os.chmod(shared_budget_path or (private_root/'cost.sqlite'),0o600)
    def complete(self,*,request_id,messages,tools,max_output_tokens=2048,purpose='protected',timeout_seconds=120):
        if purpose not in {'calibration','development','protected'}:raise ValueError('api_purpose')
        if purpose!='calibration' and self.config.get('calibration_ready') is not True:
            raise ValueError('api_calibration_pending')
        if type(max_output_tokens) is not int or not 1<=max_output_tokens<=2048:raise ValueError('api_output_cap')
        payload={'model':self.config['model'],'messages':messages,'max_tokens':max_output_tokens,
            'temperature':1.0,'top_p':0.95,'enable_thinking':False}
        if tools:payload.update(tools=tools,tool_choice='auto')
        # Full admitted context reservation; unknown responses keep all reserved cost.
        input_bound=16384-max_output_tokens
        reserved_micro=self.budget.reserve(request_id,input_bound,max_output_tokens)
        path=self.root/(digest_jcs(request_id)[7:]+'.response.bin')
        if path.exists():raise ValueError('api_response_already_exists')
        req=urllib.request.Request(self.config['base_url']+'/chat/completions',
            data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        opener=urllib.request.build_opener(NoRedirect)
        with opener.open(req,timeout=min(120,max(1,timeout_seconds))) as response:raw=response.read(4194305)
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if len(raw)>4194304:raise ValueError('api_response_limit')
        value=json.loads(raw);usage=value.get('usage') or {}
        if value.get('model')!=self.config['model']:raise ValueError('api_returned_model_mismatch')
        input_tokens,output_tokens=usage.get('prompt_tokens'),usage.get('completion_tokens')
        reasoning=usage.get('reasoning_tokens',usage.get('completion_tokens_details',{}).get('reasoning_tokens'))
        if reasoning is not None and (type(reasoning) is not int or reasoning!=0):
            raise ValueError('api_reasoning_usage_nonzero')
        if any(type(v) is not int for v in (input_tokens,output_tokens)) or input_tokens>input_bound or output_tokens>max_output_tokens:
            raise ValueError('api_usage_not_admitted')
        if any(c.get('finish_reason')=='length' or c.get('message',{}).get('reasoning_content') for c in value.get('choices',[])):
            raise ValueError('api_truncation_or_reasoning')
        known_usage_cost=self.budget.legacy.price(input_tokens,output_tokens)
        if reasoning is None:
            # The provider omitted raw reasoning usage. Preserve the full pre-call
            # reservation in the shared $50 cap and keep the token cost separately.
            charged=None
            reasoning_status='unknown_missing_reservation_retained'
        else:
            charged=self.budget.finish(request_id,input_tokens,output_tokens)
            reasoning_status='provider_reported_zero'
        return value,{'prompt_tokens':input_tokens,'completion_tokens':output_tokens,
            'reasoning_tokens':reasoning,
            'reasoning_usage_status':reasoning_status,
            'raw_response_digest':digest_bytes(raw),
            'reserved_micro_rmb':reserved_micro,'charged_micro_rmb':charged,
            'known_usage_cost_micro_rmb':known_usage_cost,
            'reservation_retained':reasoning is None}
