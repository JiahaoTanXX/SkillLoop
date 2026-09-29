"""Container entry: current run only, no controller/vault/authority mount."""
import copy,json,os,sys
from pathlib import Path
sys.path.insert(0,'/code/scripts/vendor');sys.path.insert(0,'/code')
from transformers import AutoTokenizer
from skillloop.runtime.adapter import AgentAdapter
from skillloop.runtime.client import ProxyClient
from skillloop.runtime.gateway import SGLangGateway
from skillloop.discovery.mutation import RenderedMutation

class ExactLocalTokenizer:
    def __init__(self):self.tokenizer=AutoTokenizer.from_pretrained('/model',local_files_only=True,trust_remote_code=True)
    def count_text(self,text):return len(self.tokenizer.encode(text,add_special_tokens=False))
    def count(self,messages,tools,*,enable_thinking=True):
        messages=copy.deepcopy(messages)
        for message in messages:
            for call in message.get('tool_calls') or []:
                function=call.get('function',call)
                if isinstance(function.get('arguments'),str):function['arguments']=json.loads(function['arguments'])
        ids=self.tokenizer.apply_chat_template(messages,tools=tools,tokenize=True,add_generation_prompt=True,enable_thinking=enable_thinking)
        return len(ids['input_ids']) if hasattr(ids,'keys') else len(ids)

os.umask(0o077)
x=json.loads(Path('/current-request.json').read_text());c=x['config'];t=ExactLocalTokenizer()
result=AgentAdapter(proxy=ProxyClient(Path('/socket')),
    gateway=SGLangGateway('http://127.0.0.1:30000',t,enable_thinking=False,timeout_seconds=c['provider_timeout_seconds']),
    private_root=Path(x['evidence_path'])).run(profile_id=x['profile'],skill_bytes=x['skill'].encode(),
        run_request=x['request'],task_binding=x['binding'],fence=1,trust_revision=1,deployment_epoch=x['deployment'],
        deadline_seconds=c['agent_deadline_seconds'],rendered_mutation=RenderedMutation(**x['mutation']) if x['mutation'] else None,
        attempt_index=x['attempt'])
Path(x['evidence_path'],'adapter-result.json').write_text(json.dumps(result))
