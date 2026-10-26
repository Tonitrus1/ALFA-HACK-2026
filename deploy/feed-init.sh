#!/bin/sh
set -eu
if [ ! -f /bundle/manifest.json ]; then
    attempt=1
    until python -m feed.prepare --bundle /bundle --download; do
        [ "$attempt" -lt 3 ] || exit 1
        echo "Model preparation interrupted; retrying ($attempt/3)." >&2
        sleep 5
        attempt=$((attempt + 1))
    done
fi
