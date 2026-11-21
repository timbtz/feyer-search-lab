# Qwen review worker: completion and correctness gates

The optional `TokenFactory.chat_stream` client reads SSE output, defaults to explicit `reasoning_effort="low"` and a 4,096-token total generation cap, and accepts `response_format={"type":"json_object"}`. Existing nonstream callers are unchanged; this is not a deployed repair loop or a new campaign.

```python
from lab.token_factory import TokenFactory, settings

key, model = settings('.env')
reply = TokenFactory(key, model, timeout=90).chat_stream(
    [{'role': 'system', 'content': 'Return a concise JSON diagnosis; do not change requirements.'},
     {'role': 'user', 'content': approved_failure_context}],
    max_tokens=4096,
    reasoning_effort='low',
    response_format={'type': 'json_object'},
    max_seconds=240,
)
if not reply['usable_completion']:
    # Save failure/usage and stop or hand off. Do not execute partial output.
    raise RuntimeError('No complete Qwen response')
# Parse and independently validate the expected JSON schema before use.
```

`max_seconds` is checked between reads; socket timeout bounds a stalled read. The caller's supervisor must enforce a strict wall-clock deadline externally. The live probe uses a separate process with a 240-second alarm. The client caps stream bytes/line size, preserves rate-limit headers, does not retry, and records time to first event versus time to first answer text. Reasoning text is not retained in its result. `usable_completion` requires a completed stream, nonempty text, `finish_reason="stop"` and no HTTP/provider/parser error; it is not a correctness judgment.

## Evidence and configuration limits

Two nonstream source reviews returned HTTP 504 after about 60 seconds. The shorter synthetic review took 48 seconds. An earlier streaming attempt used all 2,048 completion tokens for reasoning, ended with `length`, and returned no visible answer. Therefore changing socket timeout alone is insufficient. Increasing the token cap can still produce no answer; do not silently increase budgets.

AMD documents shared reasoning/answer token budgets, supported efforts `low`, `medium`, `xhigh`, and JSON output for this model: [Qwen model reference](https://amd-aim.github.io/radeon-cloud-docs/models/qwen3-8-27b/). Omitting effort defaults to the longest tier. Keep `max_tokens` rather than assuming unlisted API fields are forwarded. [Chat completions](https://amd-aim.github.io/radeon-cloud-docs/api/chat-completions/) documents streaming and a ten-minute timeout; the global endpoint's observed 60-second 504 differs, so the responsible intermediary has not been identified.

## Proposed bounded repair role

This is a design, not an enabled automatic patcher. A failed evaluator result should provide the exact candidate/parent SHA, failed checks, numerical error summaries and a small approved relevant diff. Qwen proposes a diagnosis, minimal repair and targeted regression test. It must not modify the benchmark, reference values, tolerances, frequency/variable count, precision or gradient checks. Separate infrastructure failures (timeout, dependency, worker failure) from physical/numerical failures; do not change physics to fix infrastructure.

A supervising agent reviews and applies any repair only in its assigned branch, then uses the shared exact-SHA queue. Screen is provisional; full official and strict saved-array/all-gradient comparisons remain required. Use bounded attempts and hand unresolved numerical cases to Codex/Claude. Preserve failures and token/latency evidence. Never infer that a model's explanation establishes physical correctness.

## Streamed source-review trial

The approved source task returned HTTP200 and first SSE event at14.07s, continued beyond60s, and completed at215.14s. First visible answer arrived at192.86s. The4,096-token cap contained3,643 reasoning tokens and453 other completion tokens; output ended with `length` and invalid truncated JSON. Thus streaming avoided the observed gateway cutoff but did not yield an admissible answer. Raw output also suggested an NVIDIA-specific monitor despite the AMD/CPU context, and an insufficient first/last-row equality check. Do not execute this answer.

Evidence: `experiments/services/qwen-streaming-trial.json`. The returned `total_tokens` field double-counts reasoning relative to prompt+completion in this response; retain the provider fields and show the components explicitly. The API reported0.0002886422points, not a dollar charge.

## Compact failed-candidate diagnosis

The user explicitly authorized diagnosing failures and proposing repairs while preserving correctness requirements. A single streamed review of historical candidate `7f3cf9c316ce87a98afccb402bffc34e4ff71532` / full job `a7b341dc0cc64363922bcb3023a14537` completed in71.57s, with first content at62.88s. It returned valid JSON and `stop`. Input441 + completion1,369 =1,810 tokens;1,140 reasoning tokens are already included in completion. Reported usage0.000111265points. The raw provider total again double-counted reasoning.

Qwen proposed restoring `d^H solve(A,Nw)` instead of the rewritten `w^H Nw`. This is a conservative fallback, not a demonstrated speed-preserving repair. Its assertion that the change guarantees identical rounding is unsupported; its bitwise-equality requirements are also stricter than the unchanged numeric gate. We retain `review_required`, not validated. No code was edited or evaluated.

The practical demonstrated role is compact failure diagnosis with a reviewed proposal. Keep broad open-ended source audits with stronger agents for now. Both source/repair response evidence and the compact approved input are stored under `experiments/services/qwen-*-trial.json` and `qwen-repair-diagnosis-input.json`. The optional client and17 focused tests are on `infra/qwen-streaming`; production campaigns have not been switched automatically.
