"""AMD Token Factory client and bounded concurrency probe. Never logs credentials."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.client import HTTPException
import json
import math
import os
from pathlib import Path
import statistics
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = 'https://radeon-global.anruicloud.com/api/v1'


def settings(env_file):
    values = {}
    path = Path(env_file)
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip().strip('\"\'')
    key = os.environ.get('RADEON_API_KEY', values.get('RADEON_API_KEY'))
    model = os.environ.get('RADEON_MODEL', values.get('RADEON_MODEL', 'Qwen3.8-27B'))
    if not key:
        raise ValueError('Set RADEON_API_KEY in the environment or an ignored .env file')
    return key, model


class TokenFactory:
    def __init__(self, key, model='Qwen3.8-27B', timeout=90):
        self.key, self.model, self.timeout = key, model, timeout

    def request(self, path, payload=None):
        if path not in ('/models', '/chat/completions'):
            raise ValueError('Unsupported API path')
        headers = {'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'}
        request = Request(BASE_URL + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        started = time.monotonic()
        try:
            response = urlopen(request, timeout=self.timeout)
        except HTTPError as error:
            response = error
        except (URLError, TimeoutError, OSError) as error:
            return {'status': None, 'latency_seconds': time.monotonic()-started,
                    'headers': {}, 'error': str(error).replace(self.key, '[redacted]')[:500]}
        with response:
            raw = response.read().decode(errors='replace')
            limits = {k.lower():v for k,v in response.headers.items()
                      if 'ratelimit' in k.lower() or 'rate-limit' in k.lower() or k.lower() in ('retry-after', 'x-request-id')}
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {'error': {'message': raw[:500]}}
            # Redact even if an upstream error unexpectedly echoes the credential.
            data = json.loads(json.dumps(data).replace(self.key, '[redacted]'))
            return {'status': response.status, 'latency_seconds': time.monotonic()-started,
                    'headers': limits, 'data': data}

    def chat(self, messages, max_tokens=64, reasoning_effort='low'):
        return self.request('/chat/completions', {'model': self.model, 'messages': messages,
                            'max_tokens': max_tokens, 'reasoning_effort': reasoning_effort,
                            'temperature': 0})

    def chat_stream(self, messages, max_tokens=4096, reasoning_effort='low',
                    response_format=None, max_seconds=300):
        """Read one SSE completion without retries or executing model output.

        Reasoning consumes max_tokens too. Keep its text out of the result.
        self.timeout limits a blocked read; max_seconds is checked between reads.
        A supervisor must enforce any strict wall-clock deadline externally.
        A 200 response alone is not success: inspect usable_completion and, for
        structured tasks, independently validate the returned content/schema.
        """
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError('Token limit must be a positive integer')
        if (isinstance(max_seconds, bool) or not isinstance(max_seconds, (int, float))
                or not math.isfinite(max_seconds) or max_seconds <= 0):
            raise ValueError('Duration limit must be finite and positive')
        payload = {'model': self.model, 'messages': messages, 'stream': True,
                   'max_tokens': max_tokens, 'reasoning_effort': reasoning_effort,
                   'temperature': 0}
        if response_format is not None:
            payload['response_format'] = response_format
        request = Request(BASE_URL + '/chat/completions', data=json.dumps(payload).encode(),
                          headers={'Authorization': 'Bearer ' + self.key,
                                   'Content-Type': 'application/json',
                                   'Accept': 'text/event-stream'})
        started = time.monotonic()
        result = {'status': None, 'headers': {}, 'stream_done': False,
                  'first_event_seconds': None, 'first_content_seconds': None,
                  'reasoning_characters': 0, 'usable_completion': False}
        content, finish_reason, usage = [], None, None
        response = None

        def consume(lines):
            nonlocal finish_reason, usage
            raw = '\n'.join(lines)
            if raw == '[DONE]':
                result['stream_done'] = True
                return
            event = json.loads(raw)
            if not isinstance(event, dict):
                raise ValueError('SSE payload is not an object')
            if result['first_event_seconds'] is None:
                result['first_event_seconds'] = time.monotonic() - started
            if event.get('error'):
                raise ValueError('Provider stream error: ' + str(event['error']))
            if event.get('usage') is not None:
                usage = event['usage']
            for choice in event.get('choices', []):
                if not isinstance(choice, dict):
                    raise ValueError('SSE choice is not an object')
                if choice.get('index', 0) != 0:
                    continue
                finish_reason = choice.get('finish_reason') or finish_reason
                delta = choice.get('delta') or {}
                if not isinstance(delta, dict):
                    raise ValueError('SSE delta is not an object')
                value = delta.get('content') or ''
                if not isinstance(value, str):
                    raise ValueError('SSE content is not text')
                if value:
                    if result['first_content_seconds'] is None:
                        result['first_content_seconds'] = time.monotonic() - started
                    content.append(value)
                result['reasoning_characters'] += len(
                    delta.get('reasoning') or delta.get('reasoning_content') or '')

        try:
            try:
                response = urlopen(request, timeout=min(self.timeout, max_seconds))
            except HTTPError as error:
                response = error
            with response:
                result['status'] = response.status
                result['headers'] = {k.lower(): v for k, v in response.headers.items()
                                     if 'ratelimit' in k.lower() or 'rate-limit' in k.lower()
                                     or k.lower() in ('retry-after', 'x-request-id')}
                if response.status != 200:
                    raise ValueError('HTTP ' + str(response.status) + ': ' +
                                     response.read(1000).decode(errors='replace'))
                if 'text/event-stream' not in response.headers.get('Content-Type', '').lower():
                    raise ValueError('Expected text/event-stream response')
                lines, size = [], 0
                while not result['stream_done']:
                    if time.monotonic() - started >= max_seconds:
                        raise TimeoutError('Streaming duration limit reached')
                    raw = response.readline(65537)
                    if time.monotonic() - started >= max_seconds:
                        raise TimeoutError('Streaming duration limit reached')
                    if not raw:
                        if lines:
                            consume(lines)
                        break
                    size += len(raw)
                    if len(raw) > 65536 or size > 4 * 1024 * 1024:
                        raise ValueError('Streaming response exceeds byte limit')
                    line = raw.decode('utf-8').rstrip('\r\n')
                    if not line:
                        if lines:
                            consume(lines)
                            lines = []
                    elif line.startswith('data:'):
                        lines.append(line[5:].lstrip(' '))
                if not result['stream_done']:
                    raise ValueError('Stream ended before [DONE]')
        except (OSError, HTTPException, ValueError, TypeError, KeyError) as error:
            result['error'] = str(error).replace(self.key, '[redacted]')[:500]
        result['latency_seconds'] = time.monotonic() - started
        result['data'] = {'choices': [{'message': {'content': ''.join(content)},
                                       'finish_reason': finish_reason}], 'usage': usage}
        result['usable_completion'] = (result['status'] == 200 and result['stream_done']
                                       and finish_reason == 'stop' and bool(''.join(content).strip())
                                       and not result.get('error'))
        return json.loads(json.dumps(result).replace(self.key, '[redacted]'))


def summarize_response(response):
    data=response.get('data', {})
    choices=data.get('choices') or []
    choice=choices[0] if choices else {}
    content=choice.get('message', {}).get('content') or ''
    result={k:response.get(k) for k in ('status','latency_seconds','headers')}
    result.update(finish_reason=choice.get('finish_reason'), content_characters=len(content),
                  usage=data.get('usage', {}))
    if response.get('error'):result['error']=response['error']
    if data.get('error'):result['error']=data['error']
    return result


def probe(client, levels, output):
    if not levels or any(n<1 or n>32 for n in levels):
        raise ValueError('Probe concurrency must be between 1 and 32')
    report={'created_at_utc':datetime.now(timezone.utc).isoformat(),'base_url':BASE_URL,
            'model':client.model,'client_location':'local laptop','max_tokens_per_request':64,
            'reasoning_effort':'low','automatic_retries':False,'batches':[]}
    output=Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    for concurrency in levels:
        started=time.monotonic()
        def once(index):
            response=client.chat([{'role':'user','content':f'Connection check {concurrency}-{index}. Reply only with OK.'}])
            return summarize_response(response)
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            responses=[f.result() for f in as_completed([pool.submit(once,i) for i in range(concurrency)])]
        wall=time.monotonic()-started
        latencies=sorted(r['latency_seconds'] for r in responses)
        successes=sum(r['status']==200 for r in responses)
        batch={'concurrency':concurrency,'requests':len(responses),'http_200':successes,
               'nonempty_completions':sum(r['status']==200 and r['content_characters']>0 for r in responses),
               'http_429':sum(r['status']==429 for r in responses),'wall_seconds':wall,
               'median_latency_seconds':statistics.median(latencies),
               'p95_latency_seconds':latencies[max(0,math.ceil(.95*len(latencies))-1)],
               'completed_requests_per_second':successes/wall,'responses':responses}
        report['batches'].append(batch)
        output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        print(json.dumps({k:v for k,v in batch.items() if k!='responses'}),flush=True)
        if successes!=len(responses):
            report['stopped_reason']='Stopped increasing load after a non-200 response; inspect errors and Retry-After headers.'
            break
        time.sleep(2)
    else:report['stopped_reason']='Reached the configured probe ceiling; this does not establish the service maximum.'
    report['highest_all_200_concurrency']=max((b['concurrency'] for b in report['batches'] if b['http_200']==b['requests']),default=0)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',type=Path,default=Path('.env'))
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('check')
    run=sub.add_parser('probe')
    run.add_argument('--levels',default='1,2,4,8')
    run.add_argument('--output',type=Path,default=Path('.lab/token-factory/concurrency.json'))
    args=parser.parse_args()
    key,model=settings(args.env_file)
    client=TokenFactory(key,model)
    if args.command=='check':
        models=client.request('/models')
        ids=[m.get('id') for m in models.get('data',{}).get('data',[])]
        print(json.dumps({'models_status':models['status'],'available_model_count':len(ids),
                          'requested_model_available':model in ids,'headers':models['headers']}))
        if models['status']!=200:print(json.dumps(summarize_response(models)))
        response=client.chat([{'role':'user','content':'Reply only with OK.'}])
        result=summarize_response(response)
        choices=response.get('data',{}).get('choices') or []
        if choices:result['reply']=choices[0].get('message',{}).get('content')
        print(json.dumps(result,indent=2))
        if response['status']!=200:raise SystemExit(1)
    else:
        report=probe(client,[int(s) for s in args.levels.split(',')],args.output)
        print(json.dumps({'highest_all_200_concurrency':report['highest_all_200_concurrency'],
                          'stopped_reason':report['stopped_reason'],'report':str(args.output)}))


if __name__=='__main__':main()
