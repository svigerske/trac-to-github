#! /bin/sh
. ./SECRETS
NODE_ID=$1
curl -H "Authorization: bearer $GH_REPO_MUTATE_TOKEN" -X POST -d " \
{ \
   \"query\": \"mutation HideIt {                                       \
  minimizeComment(input:{subjectId:\\\"$NODE_ID\\\",classifier:OUTDATED}) {   \
    minimizedComment {                                                         \
      isMinimized                                                       \
    }                                                                   \
  }                                                                     \
}                                                                       \
\"                                                                      \
}
" https://api.github.com/graphql
