#! /bin/sh
. ./SECRETS
set -x
for f in minimizing_query_*.json; do
    curl -H "Authorization: bearer $GH_REPO_MUTATE_TOKEN" -X POST -d @$f https://api.github.com/graphql
done
