#!/bin/sh
if [ -z "$SAGE_ROOT" ]; then
    echo >&2 "SAGE_ROOT needs to be set to a Sage worktree"
    exit 1
fi
(cd "$SAGE_ROOT" && git fetch trac develop && git log FETCH_HEAD --first-parent --author="Release Manager" --merges --grep="^Trac #" --oneline --no-abbrev-commit) | tee closing_commits.txt
