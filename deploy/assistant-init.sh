#!/bin/sh
set -eu
if [ ! -f /app/model-cache/manifest.json ]; then
    alfa-assistant prepare-models
fi
