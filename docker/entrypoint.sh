#!/bin/sh
set -eu

mkdir -p /app/data/jobs /app/data/outputs /app/data/tmp /app/data/piper

exec "$@"
