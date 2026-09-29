"""One protected Runtime container per execution; no full suite/vault mount."""
import dataclasses,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
IMAGE='sha256:4cba07b0c68725991890c64843403396effb7faa39ac47261166b2299095c513'
MODEL='/home/asus_gx10/skillloop/model-cache/Qwen3.8-27B-FP8'
UID=21002

def container_execute(output,profile,skill,request,binding,config,mutation,attempt,deployment):
    current={'profile':profile,'skill':skill.decode(),'request':request,'binding':binding,'config':config,
        'mutation':dataclasses.asdict(mutation) if mutation else None,'attempt':attempt,'deployment':deployment,
        'evidence_path':str(output/'evidence')}
    staged=output/'runtime-current-request.json';staged.write_text(json.dumps(current));os.chmod(staged,0o444)
    evidence=output/'evidence';evidence.mkdir(mode=0o700)
    def owner(uid):
        subprocess.run(['docker','run','--rm','--network','none','--cap-drop','ALL','--cap-add','CHOWN',
            '--user','0','--mount','type=bind,source='+str(evidence)+',target=/evidence',IMAGE,
            'chown','-R',str(uid)+':'+str(uid),'/evidence'],check=True,capture_output=True,timeout=20)
    owner(UID)
    command=['docker','run','--rm','--network','host','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--user',str(UID),'--tmpfs','/tmp:rw,nosuid,nodev,size=128m','-e','HF_HUB_OFFLINE=1','-e','TRANSFORMERS_OFFLINE=1',
        '-e','PYTHONPATH=/code/scripts/vendor:/code','-e','PYTHONDONTWRITEBYTECODE=1',
        '--mount','type=bind,source='+str(ROOT)+',target=/code,readonly',
        '--mount','type=bind,source='+MODEL+',target=/model,readonly',
        '--mount','type=bind,source='+str(staged)+',target=/current-request.json,readonly',
        '--mount','type=bind,source='+str(output/'sockets')+',target=/socket',
        '--mount','type=bind,source='+str(evidence)+',target='+str(evidence),
        IMAGE,'python3','/code/scripts/dgx_m7_runtime.py']
    try:
        p=subprocess.run(command,capture_output=True,timeout=240)
        (output/'runtime-container-stderr.log').write_bytes(p.stderr)
        if p.returncode:raise ValueError('isolated_runtime_failed')
    finally:
        owner(os.getuid());os.chmod(staged,0o600)
    return json.loads((evidence/'adapter-result.json').read_text())
