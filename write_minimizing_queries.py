#!/usr/bin/env python3

import json

graphql_batch_size = 20

with open("minimized_issue_comment_node_ids.json", "r") as f:
    node_ids = json.load(f)

query = ""
batch = 0

def dump_batch():
    with open(f"minimizing_query_{batch}.json", "w") as f:
        json.dump({"query": "mutation Minimize{" + query +  "}"}, f, indent=4)

for i, node_id in enumerate(node_ids):
    query += """
minimizeComment%s: minimizeComment(input:{subjectId:"%s",classifier:OUTDATED}) {minimizedComment {isMinimized}}
""" % (i, node_id)
    if i % graphql_batch_size == 0:
        dump_batch()
        batch += 1
        query = ""
if query:
    dump_batch()
