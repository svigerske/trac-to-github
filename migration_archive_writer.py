import json
import pathlib
from urllib.parse import urlparse, urlunparse, urljoin, quote
from collections import defaultdict
from copy import copy

# class MigrationArchiveWriter:

#     # https://github.com/PyGithub/PyGithub/blob/master/github/Repository.py
#     def create_issue(
#         self,
#         title,
#         body=None,
#         assignee=None,
#         milestone=None,
#         labels=None,
#         assignees=None,
#     ):

def pluralize(t):
    if t.endswith('y'):
        return t[:-1] + 'ies'
    return t + 's'

class MigrationArchiveWritingRequester:

    def __init__(self, migration_archive=None, wiki=None):
        if migration_archive is None:
            self._migration_archive = None
        else:
            self._migration_archive = pathlib.Path(migration_archive)
            self._migration_archive.mkdir(parents=True, exist_ok=True)
        if wiki is None:
            self._wiki = None
        else:
            self._wiki = pathlib.Path(wiki)
            self._wiki.mkdir(parents=True, exist_ok=True)
        self._num_issues = 0
        self._num_issue_comments = 0
        self._num_issue_events = 0
        self._num_json_by_type = defaultdict(lambda: 0)

    def requestJsonAndCheck(self, verb, url, parameters=None, headers=None, input=None):
        print(f'# {verb=} {url=} {parameters=} {headers=} {input=}')
        parse_result = urlparse(url)
        # print(parse_result.path)
        endpoint = parse_result.path.split('/')[3:]
        base_url = urlunparse([parse_result.scheme,
                               parse_result.netloc,
                               '/'.join(parse_result.path.split('/')[:3]) + '/',
                               None, None, None])
        # print(f'{base_url=} {endpoint=}')
        responseHeaders = None
        output = copy(input)
        match verb, endpoint:
            case 'POST', ['labels']:
                output['type'] = 'label'
                url = urljoin(base_url, 'labels/' + quote(input['name']))
            case 'POST', ['milestones']:
                output['type'] = 'milestone'
                url = urljoin(base_url, 'milestones/' + quote(input['title']))
            case 'POST', ['issues']:
                # Create a new issue
                output['type'] = 'issue'
                self._num_issues += 1
                issue = self._num_issues
                url = urljoin(base_url, f'issues/{issue}')
            case 'POST', ['issues', issue, 'comments']:
                # Create an issue comment
                output['type'] = 'issue_comment'
                output['issue'] = urljoin(base_url, f'issues/{issue}')
                self._num_issue_comments += 1
                id = self._num_issue_comments
                url = urljoin(base_url, f'issues/{issue}#issuecomment-{id}')
            case 'POST', ['issues', issue, 'events']:
                # Create an issue event
                output['type'] = 'issue_event'
                output['issue'] = urljoin(base_url, f'issues/{issue}')
                self._num_issue_events += 1
                id = self._num_issue_events
                url = urljoin(base_url, f'issues/{issue}#event-{id}')
        if isinstance(output, dict):
            output['url'] = url
            dump = json.dumps(output, sort_keys=True, indent=4)
            if self._migration_archive and 'type' in output:
                t = output['type']
                self._num_json_by_type[t] += 1
                id = self._num_json_by_type[t]
                json_file = self._migration_archive / f'{pluralize(t)}_{id:06}.json'
                with open(json_file, 'w') as f:
                    f.write(dump)
                print(f'# Wrote {json_file}')
            else:
                print(dump)

            if self._wiki:

                def issue_wiki_file():
                    thousands = int(issue) // 1000
                    dir = self._wiki / f'Issues-{thousands:02}xxx'
                    dir.mkdir(parents=True, exist_ok=True)
                    return dir / f'{issue}.md'

                match verb, endpoint:
                    case 'POST', ['issues']:
                        with open(issue_wiki_file(), 'w') as f:
                            title = output['title']
                            f.write(f'# Issue {issue}: {title}\n\n')
                            f.write(f'{json_file}:\n')
                            f.write(f'```json\n{dump}\n```\n')
                            f.write(output['body'])
                            f.write('\n')
                    case 'POST', ['issues', issue, 'comments']:
                        with open(issue_wiki_file(), 'a') as f:
                            f.write('\n\n\n---\n\n')
                            f.write(f'{json_file}:\n')
                            f.write(f'```json\n{dump}\n```\n\n')
                            f.write(output['body'])
                            f.write('\n')
                    case 'POST', ['issues', issue, 'events']:
                        with open(issue_wiki_file(), 'a') as f:
                            f.write('\n\n\n---\n\n')
                            f.write(f'{json_file}:\n')
                            f.write(f'```json\n{dump}\n```\n')

        return responseHeaders, output
