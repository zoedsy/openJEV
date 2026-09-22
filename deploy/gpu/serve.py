"""Pinned DiffusionGemma service for one NVIDIA H100 80GB GPU."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from urllib.request import Request, urlopen

ROOT = Path('/data/openjev')
ROOT.mkdir(parents=True, exist_ok=True)
MODEL = 'nvidia/diffusiongemma-26B-A4B-it-NVFP4'
REVISION = 'ec4ff3df205028f4e81c954c2227f9312b3ec2ea'
IMAGE = 'razorback16/openjev@sha256:c131a33e9a341489649c22654fb3c5b6b8c7094ae1ffca8c8e8bee0a37a40da5'


def status(phase, **extra):
    value = dict(phase=phase, model=MODEL, revision=REVISION, image=IMAGE, time=time.time(), **extra)
    (ROOT/'status.json').write_text(json.dumps(value, indent=2)+'\n')
    print('OPENJEV_STATUS '+json.dumps(value), flush=True)


def request(path, body=None):
    req=Request('http://127.0.0.1:8080'+path, data=json.dumps(body).encode() if body else None, headers={'Content-Type':'application/json'})
    with urlopen(req, timeout=180 if body else 5) as response:
        return json.load(response)


def main():
    os.environ.update(HF_HOME='/data/huggingface', HF_HUB_DISABLE_XET='1', HF_HUB_DOWNLOAD_TIMEOUT='1200', TOKENIZERS_PARALLELISM='false')
    import torch
    import vllm
    gpu=torch.cuda.get_device_name(0)
    print('RUNTIME',json.dumps(dict(gpu=gpu,torch=torch.__version__,cuda=torch.version.cuda,vllm=vllm.__version__)),flush=True)
    status('downloading',gpu=gpu)
    from huggingface_hub import snapshot_download
    local=snapshot_download(MODEL,revision=REVISION,max_workers=8)
    status('loading',gpu=gpu)
    env=os.environ.copy()
    env.update(OPENJEV_BACKEND='vllm',OPENJEV_MODEL=local,OPENJEV_TOKENIZER=local,
        OPENJEV_HOST='0.0.0.0',OPENJEV_PORT='8080',OPENJEV_GPU_UTIL='0.80',
        OPENJEV_MAX_NUM_SEQS='8',OPENJEV_MAX_MODEL_LEN='8192',OPENJEV_MAX_INFLIGHT='4',
        OPENJEV_GEN_MAX_INFLIGHT='1',OPENJEV_GEN_MAX_TOKENS='512',OPENJEV_MAX_IMAGES='0',
        OPENJEV_WARMUP='0',OPENJEV_VLLM_ARGS='--linear-backend marlin --moe-backend marlin')
    server=subprocess.Popen(['/usr/local/bin/openjev-entrypoint'],env=env,start_new_session=True)
    def stop(*args):
        os.killpg(server.pid,signal.SIGTERM)
        raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    try:
        for _ in range(360):
            if server.poll() is not None:
                raise RuntimeError(f'Model server exited: {server.returncode}')
            try:
                request('/health')
                break
            except Exception:
                time.sleep(5)
        else:
            raise RuntimeError('Model startup exceeded 30 minutes')
        status('testing',gpu=gpu)
        body={'model':'openjev-latest','state':'耳机坏了，我要退货退款。','questions':{
            'intent':{'type':'choice','instructions':'顾客想做什么？','criteria':{'refund':'退货退款','buy':'购买新品'}},
            'broken':{'type':'noul','instructions':'耳机存在故障。'},
            'tone':{'type':'score','instructions':'顾客情绪强度？','criteria':['平静','不满','愤怒']},
        }}
        began=time.monotonic(); result=request('/v1/systemone',body); duration=time.monotonic()-began
        (ROOT/'smoke.json').write_text(json.dumps(dict(request=body,response=result,seconds=duration),ensure_ascii=False,indent=2)+'\n')
        if set(result.get('answers',{})) != set(body['questions']):
            raise RuntimeError('Smoke request did not return all typed answers')
        status('ready',gpu=gpu,smoke_seconds=duration)
        code=server.wait()
        raise RuntimeError(f'Model server exited: {code}')
    finally:
        if server.poll() is None:
            os.killpg(server.pid,signal.SIGTERM)


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        status('error',error=str(exc))
        raise
