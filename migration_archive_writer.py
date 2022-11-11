import json
from urllib.parse import urlparse
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


class MigrationArchiveWritingRequester:

    def requestJsonAndCheck(self, verb, url, parameters=None, headers=None, input=None):

        parse_result = urlparse(url)
        endpoint = parse_result.path.split('/')[3:]
        #if endpoint[0] == 'issues'
        responseHeaders = None
        output = copy(input)
        # TODO: On POST, append number
        if isinstance(output, dict):
            output['url'] = url
        print(json.dumps(output, sort_keys=True, indent=4))
        return responseHeaders, output
