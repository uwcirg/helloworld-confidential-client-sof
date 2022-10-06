#!/bin/sh -e

cmdname="$(basename "$0")"

usage() {
  cat << USAGE >&2
Usage:
  $cmdname [-h] FLASK_APP PORT

  -h
        Show this help message

  FLASK_APP: environment variable value, points to flask entry point
  PORT: port to expose

  Commands to run within docker container.  Script exists to launch
  more than a single as generally desired by docker.

USAGE
  exit 1
}

if [ "$1" = "-h" ]; then
  usage
fi

FLASK_APP=$1
PORT=$2

echo "initiate cron"
cron -f &
echo "launch gunicorn" 
gunicorn --bind "0.0.0.0:${PORT}" ${FLASK_APP}
