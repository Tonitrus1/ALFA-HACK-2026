#!/bin/sh
set -eu
if [ ! -f /bundle/manifest.json ]; then
    python -m feed.prepare --bundle /bundle --download
fi
