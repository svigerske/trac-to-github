#!/bin/sh
set -eu
. ./SECRETS
rsync --verbose --rsh='ssh -p122' -a archive admin@$HOST_IP:
