# AMD Codex connectivity diagnosis

Verified on 2026-11-21. Codex 0.171.0 and Claude Code 2.1.323 are installed from official native npm packages with SHA-512 verification under `/workspace/feyer-agents/bin`. Their executables run successfully. `/usr/local/bin/codex` and `/usr/local/bin/claude` link to those persistent binaries. The links are instance-local and need recreating after a relaunch; the binaries remain in persistent `/workspace` when that storage is preserved.

## Why Codex cannot authenticate and run here yet

The instance explicitly configures an AMD-managed HTTPS egress proxy. Requests used that existing configuration, with normal TLS certificate validation.

| Check | Observed result | Interpretation |
| --- | --- | --- |
| `codex --version` | `codex-cli 0.171.0` | Installation works |
| `codex exec --help` | Required headless flags present | Supervisor command syntax supported |
| `codex login --device-auth` | Device code request failed, HTTP 403 | Fresh server authentication failed before a user code was issued |
| `https://chatgpt.com/backend-api/codex/models` | Proxy CONNECT 403, `Server: squid/6.14`, `X-Squid-Error: ERR_ACCESS_DENIED` | AMD proxy denies access to the ChatGPT inference host |
| `https://auth.openai.com/oauth/token` | CONNECT succeeds, then HTTP 403 JSON with `unsupported_country_region_territory` | OpenAI rejects the current outbound connection's region; this does not independently identify the VM's physical location |
| `https://api.openai.com/v1/models` | Proxy CONNECT timeout | API connectivity unverified; timeout alone does not identify the cause |
| Official npm package metadata | HTTP 200 | HTTPS is not universally broken |

These checks require no account credentials. They rule out a missing binary as the current blocker. They also show why logging in again or using a browser callback alone cannot establish working inference. No proxy settings, evaluator settings or benchmark dependencies were changed. No credentials were copied from the laptop.

The exact sanitized endpoint observations are stored on the instance in `/workspace/feyer-agents/network-diagnostics.json`. The overall readiness record is `/workspace/feyer-agents/migration-status.json`.

## Platform resolution needed

AMD needs to investigate the proxy allowlist and provide a suitable supported-region environment, or correct an erroneous region classification with the provider. OpenAI's [supported countries guidance](https://help.openai.com/en/articles/7947663-chatgpt-and-openai-api-supported-countries-and-territories) describes service availability. An allowlist change alone does not resolve the independent region response.

Once those conditions are resolved, perform fresh server login and a minimal authenticated model call, then verify GitHub publishing access before transferring a branch's supervisor ownership. The [official authentication guide](https://learn.chatgpt.com/docs/auth#login-on-headless-devices) documents device login and the localhost callback fallback. The repository prohibits copying account tokens to the instance, so its auth-cache-copy fallback is not used.

The working fallback is to keep model-facing agents on the Mac and submit committed candidates to the AMD evaluator. This keeps the expensive physics workload on AMD. The local controller must remain awake and connected to continue iterations. Do not restart an expired optimization session or extend its budget as part of this network repair.

## Draft message for AMD / START support

> We can install and run Codex CLI on our Radeon hackathon instance, but cannot authenticate or reach inference. Using the instance's default managed HTTPS proxy, `chatgpt.com/backend-api/codex/models` returns CONNECT 403 with `X-Squid-Error: ERR_ACCESS_DENIED`. `auth.openai.com/oauth/token` passes CONNECT but returns HTTP 403 with error code `unsupported_country_region_territory`. `api.openai.com/v1/models` times out during CONNECT. Official npm metadata works. Could you check the provider-domain allowlist and whether this instance is in a supported service region, and provide a supported environment or help resolve an incorrect region classification? We have not changed the proxy or copied credentials. Our CPU benchmark worker is active, so please coordinate any instance replacement before stopping it.

This is a draft only; it has not been sent.
