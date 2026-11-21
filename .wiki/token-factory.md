# AMD Token Factory

The local client is `lab/token_factory.py`. It calls `Qwen3.8-27B` at `https://radeon-global.anruicloud.com/api/v1` without launching a GPU or changing the Codex agent's model.

The credential is in the main checkout's ignored `.env`, mode `0600`. `.env.example` contains placeholders only. Never commit the real key, include it in agent notes or copy it into experiment reports. The client also accepts `RADEON_API_KEY` and `RADEON_MODEL` environment variables, which take precedence over the file.

From the main checkout:

```bash
python3 -m lab.token_factory check
python3 -m lab.token_factory probe --levels 1,2,4,8
```

From another working directory, point `--env-file` at the main checkout's `.env` before the subcommand. Separate agent worktrees do not automatically receive the credential.

For Python use:

```python
from lab.token_factory import TokenFactory, settings

key, model = settings('.env')
client = TokenFactory(key, model)
response = client.chat(
    [{'role': 'user', 'content': 'Explain one optimization idea.'}],
    max_tokens=512,
    reasoning_effort='low',
)
if response['status'] == 200:
    print(response['data']['choices'][0]['message']['content'])
else:
    print(response['status'], response['headers'])
```

The response includes HTTP status, latency, rate headers and parsed response data. The probe records metadata only, with no automatic retries. It stops increasing concurrency after any non-200 response. Results are written to `.lab/token-factory/concurrency.json`.

## Observed account limits

The initial authenticated model-list request returned HTTP 200 and included the selected model among 10 models. A short chat request returned `OK` with HTTP 200, taking 19.81 seconds. The service advertised:

- `x-ratelimit-limit-user-rpm: 20`
- `x-ratelimit-limit-user-daily-usd: 1`
- Remaining request and daily allowance headers, plus a daily reset timestamp.

These are the service's account limits observed during this test, not a guarantee for other accounts or future settings. The header's USD unit should not be read as a separate payment obligation; the event console describes its allowance in points.

## Concurrency measurement

All 15 short requests succeeded with visible responses, with no HTTP 429 errors:

| Concurrent requests | Successful requests | Median response time | Batch duration |
| --- | --- | --- | --- |
| 1 | 1/1 | 4.03 s | 4.04 s |
| 2 | 2/2 | 3.07 s | 3.36 s |
| 4 | 4/4 | 3.01 s | 3.52 s |
| 8 | 8/8 | 2.98 s | 3.44 s |

Each request had a 64-token completion cap and low reasoning effort. The test stopped at eight concurrent requests to remain within the advertised per-minute allowance. Eight is a successfully tested level, not a discovered service maximum. Full measurements and observed rate headers are in [the probe report](../experiments/services/token-factory-probe.json).

For multiple agents sharing this key, enforce the request budget across all agents. Start with four concurrent requests and at least 3.2 seconds between request starts globally; this leaves a small margin beneath 20 requests/minute. If a request returns 429, honor `Retry-After` if supplied and back off. Do not retry repeatedly when the daily allowance is exhausted.

Short-request concurrency tests do not establish long-generation throughput or a maximum supported concurrency. Reasoning tokens consume the completion budget too, so a tiny `max_tokens` can yield an empty visible answer even with HTTP 200.
