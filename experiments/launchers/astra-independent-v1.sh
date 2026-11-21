#!/bin/sh
exec /opt/homebrew/bin/codex -c 'model="gpt-6-astra"' -c 'model_reasoning_effort="high"' --disable memories --disable external_agent_memory_import "$@"
