#!/bin/sh
set -eu
if [ ! -f /app/model-cache/manifest.json ]; then
    attempt=1
    until python -c 'from alfa_assistant.cli import main; main()' prepare-models; do
        [ "$attempt" -lt 3 ] || exit 1
        echo "Model preparation interrupted; retrying ($attempt/3)." >&2
        sleep 5
        attempt=$((attempt + 1))
    done
fi
