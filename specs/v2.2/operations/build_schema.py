"""Generate the frozen V2.2 configuration schema explicitly, never during verification.

This schema locks THIS version's approved specification profiles, not arbitrary
future deployment evidence. Live core/control records use their own schemas.
"""
import json
from pathlib import Path
BASE=Path(__file__).resolve().parent

def frozen(value):
    if isinstance(value,dict):
        return {'type':'object','additionalProperties':False,'required':list(value),
                'properties':{key:frozen(v) for key,v in value.items()}}
    if isinstance(value,list):
        result={'type':'array','minItems':len(value),'maxItems':len(value),'items':False}
        if value:result['prefixItems']=[frozen(item) for item in value]
        return result
    return {'const':value}

def build():
    defs={p.stem:frozen(json.loads(p.read_text())) for p in sorted(BASE.glob('*.json'))
          if not p.name.endswith('.schema.json')}
    return {'$schema':'https://json-schema.org/draft/2020-12/schema',
            '$id':'urn:skillloop:operations-config:2.2',
            'description':'Frozen versioned specification configurations; not a live runtime-record validator.',
            'oneOf':[{'$ref':'#/$defs/'+name} for name in defs], '$defs':defs}
if __name__=='__main__':
    (BASE/'operations.schema.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
