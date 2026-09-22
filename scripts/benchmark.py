#!/usr/bin/env python3
"""Measure real HTTP latency; one warm-up is separate from measured requests."""
import argparse
import json
import math
import os
from pathlib import Path
import statistics
import time
from urllib.request import ProxyHandler, Request, build_opener


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8766')
    parser.add_argument('--example', default='support')
    parser.add_argument('--repeat', type=int, default=10)
    parser.add_argument('--out', default='artifacts/benchmark.json')
    args = parser.parse_args()
    if args.repeat < 2:
        parser.error('--repeat must be at least 2')
    examples = json.loads((Path(__file__).resolve().parents[1]/'openjev/examples.json').read_text())
    example = next((e for e in examples if e['id'] == args.example), None)
    if example is None:
        parser.error('Unknown example')
    payload = {key: example[key] for key in ('state', 'questions')}
    headers = {'Content-Type': 'application/json'}
    if os.getenv('OPENJEV_API_KEY'):
        headers['Authorization'] = 'Bearer ' + os.environ['OPENJEV_API_KEY']
    opener = build_opener(ProxyHandler({}))
    measurements = []
    for i in range(args.repeat + 1):
        started = time.perf_counter()
        request = Request(args.url.rstrip('/')+'/v1/systemone', data=json.dumps(payload).encode(), headers=headers)
        with opener.open(request, timeout=240) as response:
            result = json.load(response)
        if set(result.get('answers', {})) != set(payload['questions']):
            raise RuntimeError('Missing answers; refusing to record a successful timing')
        ms = round((time.perf_counter() - started) * 1000, 1)
        row = {'client_ms': ms, 'api_ms': result.get('meta', {}).get('latency_ms'),
               'model_service_ms': result.get('meta', {}).get('inference_ms')}
        if i == 0:
            warmup = row
        else:
            measurements.append(row)
        print(f'{"warm-up" if i == 0 else i}: {ms} ms', flush=True)
    samples = sorted(r['client_ms'] for r in measurements)
    report = {'example': args.example, 'requests': len(samples), 'questions_per_request': len(payload['questions']),
              'concurrency': 1, 'warmup': warmup, 'p50_ms': statistics.median(samples),
              'p95_ms': samples[math.ceil(.95*len(samples))-1], 'min_ms': min(samples), 'max_ms': max(samples),
              'model': result['meta'].get('model_id'), 'revision': result['meta'].get('revision'),
              'measurements': measurements, 'note': 'Small sequential sample; not a throughput or quality benchmark.'}
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'measurements'}, indent=2))


if __name__ == '__main__':
    main()
