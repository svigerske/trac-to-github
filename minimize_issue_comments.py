#!/usr/bin/env python3

import re
import os
import sys
import configparser
import logging
import json
from github import Github, GithubObject, InputFileContent
from github.Issue import Issue
from github.IssueComment import IssueComment
from github.Repository import Repository
from github.GithubException import IncompletableObject
from rich.console import Console
from rich.table import Table

#import github as gh
#gh.enable_console_debug_logging()

log = logging.getLogger("trac_to_gh")

default_config = {
    'url' : 'https://api.github.com'
}

config = configparser.ConfigParser(default_config)
if len(sys.argv) > 1 :
    config.read(sys.argv[1])
else :
    config.read('migrate.cfg')

github_api_url = config.get('target', 'url')
github_token = None
if config.has_option('target', 'token') :
    github_token = config.get('target', 'token')
elif config.has_option('target', 'username'):
    github_username = config.get('target', 'username')
    github_password = config.get('target', 'password')
else:
    github_username = None
github_project = config.get('target', 'project_name')

def to_minimize(c):
    return c.body.startswith('Description changed:\n')


if __name__ == "__main__":

    if github_token is not None:
        github = Github(github_token, base_url=github_api_url)
    elif github_username is not None:
        github = Github(github_username, github_password, base_url=github_api_url)
    if github:
        repo = github.get_repo(github_project)


    with open("minimized_issue_comments.json", "r") as f:
        comment_urls = json.load(f)

    issue_numbers = set()
    for url in comment_urls:
        issue_url = url.partition('#')[0]
        issue_number = int(issue_url.rpartition('/')[2])
        issue_numbers.add(issue_number)

    minimized_node_ids = []
    for issue_number in sorted(issue_numbers):
        i = repo.get_issue(issue_number)
        node_ids = [c.node_id for c in i.get_comments() if to_minimize(c)]
        print(i.html_url, node_ids)
        minimized_node_ids.extend(node_ids)

    with open("minimized_issue_comment_node_ids.json", "w") as f:
        json.dump(minimized_issue_comments, f, indent=4)
