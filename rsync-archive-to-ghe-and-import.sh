#!/bin/sh
set -eu
. ./SECRETS
set -x
# We start a fresh migration, keyed to current time
GUID=cae4a192-8fed-11ed-84b0-$(date +"%y%m%d%H%M%S")
# Freshly named repository for each migration attempt
sed -e "s/@HOST_IP@/$HOST_IP/;s/@TARGET_REPO@/sage-$(date +"%Y%m%d%H%M%S")/" map-ghe.csv.in > map-ghe.csv
rsync --verbose --rsh='ssh -p122' -a archive map-ghe.csv admin@$HOST_IP:
# import
ssh -p 122 admin@$HOST_IP "set -x;
    (cd archive && rm -rf attach* && tar cfz - .) > archive.tgz &&
    ghe-migrator prepare archive.tgz -g $GUID &&
    ghe-migrator map -i map-ghe.csv -g $GUID &&
    if ghe-migrator import archive.tgz -g $GUID  -u mkoeppe -p $IMPORT_TOKEN; then
        ghe-migrator audit -g $GUID;
        ghe-migrator unlock -g $GUID;
    else
        ghe-migrator conflicts -g $GUID | tee conflicts.csv;
    fi;
    grep guid=$GUID /var/log/github/ghe-migrator.log"
