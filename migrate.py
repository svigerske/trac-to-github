#!/usr/bin/env python3
# vim: autoindent tabstop=4 shiftwidth=4 expandtab softtabstop=4 filetype=python fileencoding=utf-8
'''
Copyright © 2022
    Matthias Koeppe
    Kwankyu Lee
    Sebastian Oehms
    Dima Pasechnik
Modified and extended for the migration of SageMath from Trac to GitHub.

Copyright © 2018-2019
    Stefan Vigerske <svigerske@gams.com>
This is a modified/extended version of trac-to-gitlab from https://github.com/moimael/trac-to-gitlab.
It has been adapted to fit the needs of a specific Trac to GitLab conversion.
Then it has been adapted to fit the needs to another Trac to GitHub conversion.

Copyright © 2013
    Eric van der Vlist <vdv@dyomedea.com>
    Jens Neuhalfen <http://www.neuhalfen.name/>

This software is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This sotfware is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this library. If not, see <http://www.gnu.org/licenses/>.
'''

import re
import os
import sys
import configparser
import contextlib
import ast
import codecs
import logging
from collections import defaultdict
from copy import copy
from datetime import datetime
from difflib import unified_diff
from time import sleep
#from re import MULTILINE
from roman import toRoman
from xmlrpc import client
from github import Github, GithubObject, InputFileContent
from github.Repository import Repository
from github.GithubException import IncompletableObject

from migration_archive_writer import MigrationArchiveWritingRequester

import markdown
from markdown.extensions.tables import TableExtension

#import github as gh
#gh.enable_console_debug_logging()

log = logging.getLogger("trac_to_gh")

"""
What
=====

 This script migrates issues from trac to github.

License
========

 License: http://www.wtfpl.net/

Requirements
==============

 * Python 2, xmlrpclib, requests
 * Trac with xmlrpc plugin enabled
 * PyGithub

"""

default_config = {
    'migrate' : 'true',
    'keywords_to_labels' : 'false',
    'export' : 'true',  # attachments
    'url' : 'https://api.github.com'
}

# 6-digit hex notation with leading '#' sign (e.g. #FFAABB) or one of the CSS color names
# (https://developer.mozilla.org/en-US/docs/Web/CSS/color_value#Color_keywords)
labelcolor = {
  'component' : '08517b',
  'priority' : 'ff0000',
  'severity' : 'ee0000',
  'type' : '008080',
  'keyword' : 'eeeeee',
  'milestone' : '008080',
  'resolution' : '008080',
}

sleep_after_request = 2.0
sleep_after_attachment = 60.0
sleep_after_10tickets = 0.0  # TODO maybe this can be reduced due to the longer sleep after attaching something
sleep_before_xmlrpc = 0.33
sleep_before_xmlrpc_retry = 30.0

config = configparser.ConfigParser(default_config)
if len(sys.argv) > 1 :
    config.read(sys.argv[1])
else :
    config.read('migrate.cfg')

trac_url = config.get('source', 'url')
trac_url_dir = os.path.dirname(trac_url)
trac_url_ticket = os.path.join(trac_url_dir, 'ticket')
trac_url_wiki = os.path.join(trac_url_dir, 'wiki')
trac_url_query = os.path.join(trac_url_dir, 'query')

if config.has_option('target', 'issues_repo_url'):
    target_url_issues_repo = config.get('target', 'issues_repo_url')
    target_url_git_repo = config.get('target', 'git_repo_url')
if config.has_option('wiki', 'url'):
    target_url_wiki = config.get('wiki', 'url')

trac_path = None
if config.has_option('source', 'path') :
    trac_path = config.get('source', 'path')

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

migration_archive = None
if config.has_option('target', 'migration_archive'):
    migration_archive = config.get('target', 'migration_archive')

users_map = ast.literal_eval(config.get('target', 'usernames'))
must_convert_issues = config.getboolean('issues', 'migrate')
only_issues = None
if config.has_option('issues', 'only_issues'):
    only_issues = ast.literal_eval(config.get('issues', 'only_issues'))
blacklist_issues = None
if config.has_option('issues', 'blacklist_issues'):
    blacklist_issues = ast.literal_eval(config.get('issues', 'blacklist_issues'))
filter_issues = 'max=0&order=id'
if config.has_option('issues', 'filter_issues') :
    filter_issues = config.get('issues', 'filter_issues')
try:
    keywords_to_labels = config.getboolean('issues', 'keywords_to_labels')
except ValueError:
    keywords_to_labels = ast.literal_eval(config.get('issues', 'keywords_to_labels'))
migrate_milestones = config.getboolean('issues', 'migrate_milestones')
add_label = None
if config.has_option('issues', 'add_label'):
    add_label = config.get('issues', 'add_label')

attachment_export = config.getboolean('attachments', 'export')
if attachment_export :
    attachment_export_dir = config.get('attachments', 'export_dir')
    attachment_export_url = config.get('attachments', 'export_url')
    if not attachment_export_url.endswith('/') :
        attachment_export_url += '/'

must_convert_wiki = config.getboolean('wiki', 'migrate')
wiki_export_dir = None
if must_convert_wiki or config.has_option('wiki', 'export_dir'):
    wiki_export_dir = config.get('wiki', 'export_dir')

default_multilines = False
if config.has_option('source', 'default_multilines') :
    # set this boolean in the source section of the configuration file
    # to change the default of the multilines flag in the function
    # trac2markdown
    default_multilines = config.getboolean('source', 'default_multilines')


from diskcache import Cache
cache = Cache('trac_cache', size_limit=int(20e9))


#pattern_changeset = r'(?sm)In \[changeset:"([^"/]+?)(?:/[^"]+)?"\]:\n\{\{\{(\n#![^\n]+)?\n(.*?)\n\}\}\}'
pattern_changeset = r'(?sm)In \[changeset:"[0-9]+" ([0-9]+)\]:\n\{\{\{(\n#![^\n]+)?\n(.*?)\n\}\}\}'
matcher_changeset = re.compile(pattern_changeset)

pattern_changeset2 = r'\[changeset:([a-zA-Z0-9]+)\]'
matcher_changeset2 = re.compile(pattern_changeset2)

gh_labels = dict()
gh_user = None

# The file wiki_path_conversion_table.txt is created if not exists. If it
# exists, the table below is constructed from the data in the file.
create_wiki_link_conversion_table = False
wiki_path_conversion_table = {}
if os.path.exists('wiki_path_conversion_table.txt'):
    with open('wiki_path_conversion_table.txt', 'r') as f:
        for line in f.readlines():
            trac_wiki_path, wiki_path = line[:-1].split(' ')
            wiki_path_conversion_table[trac_wiki_path] = wiki_path
elif must_convert_wiki:
    create_wiki_link_conversion_table = True

RE_SUPERSCRIPT1 = re.compile(r'\^([^\s]+?)\^')
RE_SUBSCRIPT1 = re.compile(r',,([^\s]+?),,')
RE_IMAGE1 = re.compile(r'\[\[Image\(source:([^(]+)\)\]\]')
RE_IMAGE2 = re.compile(r'\[\[Image\(([^),]+)\)\]\]')
RE_IMAGE3 = re.compile(r'\[\[Image\(([^),]+),\slink=([^(]+)\)\]\]')
RE_IMAGE4 = re.compile(r'\[\[Image\((http[^),]+),\s([^)]+)\)\]\]')
RE_IMAGE5 = re.compile(r'\[\[Image\(([^),]+),\s([^)]+)\)\]\]')
RE_HTTPS1 = re.compile(r'\[\[(https?://[^\s\]\|]+)\s*\|\s*(.+?)\]\]')
RE_HTTPS2 = re.compile(r'\[\[(https?://[^\]]+)\]\]')
RE_HTTPS3 = re.compile(r'\[(https?://[^\s\[\]\|]+)\s*[\s\|]\s*([^\[\]]+)\]')
RE_HTTPS4 = re.compile(r'\[(https?://[^\s\[\]\|]+)\]')
RE_WIKI1 = re.compile(r'\[\["([^\]\|]+)["]\s*([^\[\]"]+)?["]?\]\]')
RE_WIKI2 = re.compile(r'\[\[\s*([^\]|]+)[\|]([^\[\]]+)\]\]')
RE_WIKI3 = re.compile(r'\[\[\s*([^\]]+)\]\]')
RE_WIKI4 = re.compile(r'\[wiki:"([^\[\]\|]+)["]\s*([^\[\]"]+)?["]?\]')
RE_WIKI5 = re.compile(r'\[wiki:([^\s\[\]\|]+)\s*[\s\|]\s*([^\[\]]+)\]')
RE_WIKI6 = re.compile(r'\[wiki:([^\s\[\]]+)\]')
RE_WIKI7 = re.compile(r'\[/wiki/([^\s\[\]]+)\s+([^\[\]]+)\]')
RE_QUERY1 = re.compile(r'\[query:\?')
RE_SOURCE1 = re.compile(r'\[source:([^\s\[\]]+)\s+([^\[\]]+)\]')
RE_SOURCE2 = re.compile(r'source:([\S]+)')
RE_BOLDTEXT1 = re.compile(r'\'\'\'(.*?)\'\'\'')
RE_ITALIC1 = re.compile(r'\'\'(.*?)\'\'')
RE_ITALIC2 = re.compile(r'(?<=\s)//(.*?)//')
RE_TICKET1 = re.compile(r'[\s]%s/([1-9]\d{0,4})' % trac_url_ticket)
RE_TICKET2 = re.compile(r'\#([1-9]\d{0,4})')
RE_COMMENT1 = re.compile(r'\[comment:([1-9]\d*)\s+(.*?)\]')
RE_COMMENT2 = re.compile(r'(?<=\s)comment:([1-9]\d*)')  # need to exclude the string as part of http url
RE_TICKET_COMMENT1 = re.compile(r'ticket:([1-9]\d*)#comment:([1-9]\d*)')
RE_COLOR = re.compile(r'<span style="color: ([a-zA-Z]+)">([a-zA-Z]+)</span>')
RE_RULE = re.compile(r'^[-]{4,}\s*')
RE_CAMELCASE1 = re.compile(r'(?<=\s)((?:[A-Z][a-z0-9]+){2,})(?=[\s\.\,\:\;\?\!])')
RE_CAMELCASE2 = re.compile(r'(?<=\s)((?:[A-Z][a-z0-9]+){2,})$')

RE_UNDERLINED_CODE1 = re.compile(r'(?<=\s)_([a-zA-Z_]+)_(?=[\s,)])')
RE_UNDERLINED_CODE2 = re.compile(r'(?<=\s)_([a-zA-Z_]+)_$')
RE_UNDERLINED_CODE3 = re.compile(r'^_([a-zA-Z_]+)_(?=\s)')

RE_COMMIT_LIST1 = re.compile(r'\|\[(.+?)\]\((.*)\)\|<code>(.*?)</code>\|')
RE_COMMIT_LIST2 = re.compile(r'\|\[(.+?)\]\((.*)\)\|`(.*?)`\|')
RE_COMMIT_LIST3 = re.compile(r'\|(.*?)\|(.*?)\|')

RE_NEW_COMMITS = re.compile(r'(?sm)(New commits:)\n((?:\|[^\n]*\|(?:\n|$))+)')
RE_LAST_NEW_COMMITS = re.compile(r'(?sm)(Last \d+ new commits:)\n((?:\|[^\n]*\|(?:\n|$))+)')

RE_BRANCH_FORCED_PUSH = re.compile(r'^(Branch pushed to git repo; I updated commit sha1[.] This was a forced push[.])')
RE_BRANCH_PUSH = re.compile(r'^(Branch pushed to git repo; I updated commit sha1( and set ticket back to needs_review)?[.])')

RE_GIT_SERVER_SRC = re.compile(r'https?://git\.sagemath\.org/sage\.git/tree/src')
RE_GIT_SERVER_COMMIT = re.compile(r'https?://git\.sagemath\.org/sage\.git/commit/?[?]id=([0-9a-f]+)')
RE_TRAC_REPORT = re.compile(r'\[report:([0-9]+)\s*(.*?)\]')

def convert_wiki_link(match):
    trac_path = match.group(1)

    if trac_path in wiki_path_conversion_table:
        wiki_path = wiki_path_conversion_table[trac_path]
        return os.path.join(target_url_wiki, wiki_path)

    return match.group(0)

def trac2markdown(text, base_path, conv_help, multilines=default_multilines):
    # Sage-specific normalization
    text = re.sub(r'https?://trac\.sagemath\.org/ticket/(\d+)#comment:(\d+)?', r'ticket:\1#comment:\2', text)
    text = re.sub(r'https://trac\.sagemath\.org/wiki/([/\-\w0-9@:%._+~#=]+)', convert_wiki_link, text)

    # some normalization
    text = re.sub('\r\n', '\n', text)
    text = re.sub(r'\swiki:([a-zA-Z]+)', r' [wiki:\1]', text)

    text = re.sub(r'\[\[TOC[^]]*\]\]', '', text)
    text = re.sub(r'(?m)\[\[PageOutline\]\]\s*\n', '', text)
    text = text.replace('[[BR]]', '\n')
    text = text.replace('[[br]]', '\n')

    if multilines:
        text = re.sub(r'^\S[^\n]+([^=-_|])\n([^\s`*0-9#=->-_|])', r'\1 \2', text)

    def heading_replace(match):
        """
        Return the replacement for the heading
        """
        level = len(match.group(1))
        heading = match.group(2).rstrip()

        if create_wiki_link_conversion_table:
            with open('wiki_path_conversion_table.txt', "a") as f:
                f.write(conv_help._trac_wiki_path + '#' + heading.replace(' ', '') + ' '
                        + conv_help._wiki_path + '#' + heading.replace(' ', '-'))
                f.write('\n')

        # There might be a second item if an anchor is set.
        # We ignore this anchor since it is automatically
        # set it GitHub Markdown.
        return '#'*level + ' ' + heading

    a = []
    level = 0
    in_td = False
    in_code = False
    in_html = False
    in_list = False
    in_table = False
    block = []
    table = []
    list_indents = []
    previous_line = ''
    quote_prefix = ''
    text_lines = text.split('\n') + ['']
    text_lines.reverse()
    line = True
    while text_lines:
        non_blank_previous_line = bool(line)
        line = text_lines.pop()

        # heading
        line = re.sub(r'^(=)\s(.+)\s=\s*([\#][^\s]*)?', heading_replace, line)
        line = re.sub(r'^(==)\s(.+)\s==\s*([\#][^\s]*)?', heading_replace, line)
        line = re.sub(r'^(===)\s(.+)\s===\s*([\#][^\s]*)?', heading_replace, line)
        line = re.sub(r'^(====)\s(.+)\s====\s*([\#][^\s]*)?', heading_replace, line)
        line = re.sub(r'^(=====)\s(.+)\s=====\s*([\#][^\s]*)?', heading_replace, line)
        line = re.sub(r'^(======)\s(.+)\s======\s*([\#][^\s]*)?', heading_replace, line)
        line = re.sub(r'^(=)\s([^#]+)([\#][^\s]*)?', heading_replace, line)
        line = re.sub(r'^(==)\s([^#]+)([\#][^\s]*)?', heading_replace, line)
        line = re.sub(r'^(===)\s([^#]+)([\#][^\s]*)?', heading_replace, line)
        line = re.sub(r'^(====)\s([^#]+)([\#][^\s]*)?', heading_replace, line)
        line = re.sub(r'^(=====)\s([^#]+)([\#][^\s]*)?', heading_replace, line)
        line = re.sub(r'^(======)\s([^#]+)([\#][^\s]*)?' , heading_replace, line)

        # cut quote prefix
        if line.startswith(quote_prefix):
            line = line[len(quote_prefix):]
        else:
            if in_code:  # to recover from interrupted codeblock
                text_lines.append(quote_prefix + '}}}')
                continue

            line = '\n' + line
            quote_prefix = ''

        if not (in_code or in_html):
            # quote
            m = re.match('^(>[>\s]*)', line)
            if m:
                prefix = m.group(0)
                l = len(prefix)
            else:
                prefix = ''
            quote_prefix += prefix
            line = line[len(prefix):]

        if previous_line:
            line = previous_line + line
            previous_line = ''

        line_temporary = line.lstrip()
        if line_temporary.startswith('{{{') and in_code:
            level += 1
        elif line_temporary.startswith('{{{#!td'):
            in_td = True
            in_td_level = level
            in_td_prefix = re.search('{{{', line).start()
            in_td_n = 0
            in_td_defect = 0
            line =  re.sub(r'{{{#!td', r'OPENING__PROCESSOR__TD', line)
            level += 1
        elif line_temporary.startswith('{{{#!html') and not (in_code or in_html):
            in_html = True
            in_html_level = level
            in_html_prefix = re.search('{{{', line).start()
            in_html_n = 0
            in_html_defect =0
            line =  re.sub(r'{{{#!html', r'', line)
            level += 1
        elif line_temporary.startswith('{{{#!') and not (in_code or in_html):  # code: python, diff, ...
            in_code = True
            in_code_level = level
            in_code_prefix = re.search('{{{', line).start()
            in_code_n = 0
            in_code_defect = 0
            if non_blank_previous_line:
                line = '\n' + line
            line =  re.sub(r'{{{#!([^\s]+)', r'OPENING__PROCESSOR__CODE\1', line)
            level += 1
        elif line_temporary.rstrip() == '{{{' and not (in_code or in_html):
            # check dangling #!...
            next_line = text_lines.pop()
            if next_line.startswith(quote_prefix):
                m =  re.match('#!([a-zA-Z]+)', next_line[len(quote_prefix):].strip())
                if m:
                    if m.group(1) == 'html':
                        text_lines.append(quote_prefix + line.replace('{{{', '{{{#!html'))
                        continue
                    line = line.rstrip() + m.group(1)
                else:
                    text_lines.append(next_line)
            else:
                text_lines.append(next_line)

            in_code = True
            in_code_level = level
            in_code_prefix = re.search('{{{', line).start()
            in_code_n = 0
            in_code_defect = 0
            if line_temporary.rstrip() == '{{{':
                if non_blank_previous_line:
                    line = '\n' + line
                line = line.replace('{{{', 'OPENING__PROCESSOR__CODE', 1)
            else:
                if non_blank_previous_line:
                    line = '\n' + line
                line = line.replace('{{{', 'OPENING__PROCESSOR__CODE' +'\n' , 1)
            level += 1
        elif line_temporary.rstrip() == '}}}':
            level -= 1
            if in_td and in_td_level == level:
                in_td = False
                in_td_prefix = 0
                if in_td_defect > 0:
                    for i in range(in_td_n):
                        prev_line = a[-i-1]
                        a[-i-1] = prev_line[:len(quote_prefix)] + in_td_defect*' ' + prev_line[len(quote_prefix):]
                line =  re.sub(r'}}}', r'CLOSING__PROCESSOR__TD', line)
            elif in_html and in_html_level == level:
                in_html = False
                id_html_prefix = 0
                if in_html_defect > 0:
                    for i in range(in_html_n):
                        prev_line = a[-i-1]
                        a[-i-1] = prev_line[:len(quote_prefix)] + in_html_defect*' ' + prev_line[len(quote_prefix):]
                line =  re.sub(r'}}}', r'', line)
            elif in_code and in_code_level == level:
                in_code = False
                in_code_prefix = 0
                if in_code_defect > 0:
                    for i in range(in_code_n):
                        prev_line = a[-i-1]
                        a[-i-1] = prev_line[:len(quote_prefix)] + in_code_defect*' ' + prev_line[len(quote_prefix):]
                line =  re.sub(r'}}}', r'CLOSING__PROCESSOR__CODE', line)
        else:
            # adjust badly indented codeblocks
            if in_td:
                if line.strip():
                    indent = re.search('[^\s]', line).start()
                    if indent < in_td_prefix:
                        in_td_defect = max(in_td_defect, in_td_prefix - indent)
                in_td_n += 1
            if in_html:
                if line.strip():
                    indent = re.search('[^\s]', line).start()
                    if indent < in_html_prefix:
                        in_html_defect = max(in_html_defect, in_html_prefix - indent)
                in_html_n += 1
            if in_code:
                if line.strip():
                    indent = re.search('[^\s]', line).start()
                    if indent < in_code_prefix:
                        in_code_defect = max(in_code_defect, in_code_prefix - indent)
                in_code_n += 1

        # CamelCase wiki link
        if not (in_code or in_html or in_td):
            new_line = ''
            depth = 0
            start = 0
            end = 0
            l = len(line)
            for i in range(l + 1):
                if i == l:
                    end = i
                elif line[i] == '[':
                    if depth == 0:
                        end = i
                    depth += 1
                elif line[i] == ']':
                    depth -= 1
                    if depth == 0:
                        start = i + 1
                        new_line += line[end:start]
                if end > start:
                    converted_part = RE_CAMELCASE1.sub(conv_help.camelcase_wiki_link, line[start:end])
                    converted_part = RE_CAMELCASE2.sub(conv_help.camelcase_wiki_link, converted_part)
                    new_line += converted_part

                    start = end
            line = new_line

        if not (in_code or in_html):
            line = RE_SUPERSCRIPT1.sub(r'<sup>\1</sup>', line)  # superscript ^abc^
            line = RE_SUBSCRIPT1.sub(r'<sub>\1</sub>', line)  # subscript ,,abc,,

            line = RE_QUERY1.sub(r'[%s?' % trac_url_query, line) # preconversion to URL format
            line = RE_HTTPS1.sub(r'OPENING__LEFT__BRACKET\2CLOSING__RIGHT__BRACKET(\1)', line)
            line = RE_HTTPS2.sub(r'OPENING__LEFT__BRACKET\1CLOSING__RIGHT__BRACKET(\1)', line)  # link without display text
            line = RE_HTTPS3.sub(r'OPENING__LEFT__BRACKET\2CLOSING__RIGHT__BRACKET(\1)', line)
            line = RE_HTTPS4.sub(r'OPENING__LEFT__BRACKET\1CLOSING__RIGHT__BRACKET(\1)', line)

            line = RE_IMAGE1.sub(r'!OPENING__LEFT__BRACKETCLOSING__RIGHT__BRACKET(%s/\1)' % os.path.relpath('/tree/master/'), line)
            line = RE_IMAGE2.sub(r'!OPENING__LEFT__BRACKETCLOSING__RIGHT__BRACKET(\1)', line)
            line = RE_IMAGE3.sub(r'!OPENING__LEFT__BRACKET\2CLOSING__RIGHT__BRACKET(\1)', line)
            line = RE_IMAGE4.sub(r'<img src="\1" \2>', line)
            line = RE_IMAGE5.sub(conv_help.wiki_image, line)  # \2 is the image width

            line = RE_WIKI1.sub(conv_help.wiki_link, line)
            line = RE_WIKI2.sub(conv_help.wiki_link, line)
            line = RE_WIKI3.sub(conv_help.wiki_link, line)  # wiki link without display text
            line = RE_WIKI4.sub(conv_help.wiki_link, line)  # for pagenames containing whitespaces
            line = RE_WIKI5.sub(conv_help.wiki_link, line)
            line = RE_WIKI6.sub(conv_help.wiki_link, line)  # link without display text
            line = RE_WIKI7.sub(conv_help.wiki_link, line)

            line = RE_SOURCE1.sub(r'[\2](%s/\1)' % os.path.relpath('/tree/master/', base_path), line)
            line = RE_SOURCE2.sub(r'[\1](%s/\1)' % os.path.relpath('/tree/master/', base_path), line)

            line = RE_BOLDTEXT1.sub(r'**\1**', line)
            line = RE_ITALIC1.sub(r'*\1*', line)
            line = RE_ITALIC2.sub(r'*\1*', line)

            line = RE_TICKET1.sub(r' #\1', line) # replace global ticket references
            line = RE_TICKET2.sub(conv_help.ticket_link, line)

            line = RE_COMMENT1.sub(r'OPENING__LEFT__BRACKET\2CLOSING__RIGHT__BRACKET(#comment%3A\1)', line)
            line = RE_COMMENT2.sub(r'OPENING__LEFT__BRACKETcomment:\1CLOSING__RIGHT__BRACKET(#comment%3A\1)', line)

            line = RE_TICKET_COMMENT1.sub(conv_help.ticket_comment_link, line)

            # code surrounded by underline, mistaken as italics by github
            line = RE_UNDERLINED_CODE1.sub(r'`_\1_`', line)
            line = RE_UNDERLINED_CODE2.sub(r'`_\1_`', line)
            line = RE_UNDERLINED_CODE3.sub(r'`_\1_`', line)

            # inline code snippets
            def inline_code_snippet(match):
                code = match.group(1)
                code = code.replace('@', 'AT__SIGN__IN__CODE')
                if '`' in code:
                    return '<code>' + code.replace('`', r'\`') + '</code>'
                else:
                    return '`' + code + '`'

            line = re.sub(r'(?<!`){{{(.*?)}}}', inline_code_snippet, line)

            def github_mention(match):
                trac_user = match.group(1)
                if trac_user in users_map:
                    github_user = users_map[trac_user]
                    if github_user:
                        return '@' + github_user
                return '`@`' + trac_user

            # to avoid unintended github mention
            line = re.sub('(?<=\s)@([a-zA-Z][a-zA-Z.]*)', github_mention, line)
            line = re.sub('^@([a-zA-Z][a-zA-Z.]*)', github_mention, line)

            if RE_RULE.match(line):
                if not a or not a[-1].strip():
                    line = '---'
                else:
                    line = '\n---'

            line = re.sub(r'\!(([A-Z][a-z0-9]+){2,})', r'\1', line)  # no CamelCase wiki link because of leading "!"

            # convert a trac table to a github table
            if line.startswith('||'):
                if not in_table:  # header row
                    if line.endswith('||\\'):
                        previous_line = line[:-3]
                        continue
                    elif line.endswith('|| \\'):
                        previous_line = line[:-4]
                        continue
                    # construct header separator
                    parts = line.split('||')
                    sep = []
                    for part in parts:
                        if part.startswith('='):
                            part = part[1:]
                            start = ':'
                        else:
                            start = ''
                        if part.endswith('='):
                            part = part[:-1]
                            end = ':'
                        else:
                            end = ''
                        sep.append(start + '-'*len(part) + end)
                    sep = '||'.join(sep)
                    if ':' in sep:
                        line = line + '\n' + sep
                    else:  # perhaps a table without header; github table needs header
                        header = re.sub(r'[^|]', ' ', sep)
                        line = header + '\n' + sep + '\n' + line
                    in_table = True
                # The wiki markup allows the alignment directives to be specified on a cell-by-cell
                # basis. This is used in many examples. AFAIK this can't be properly translated into
                # the GitHub markdown as it only allows to align statements column by column.
                line = line.replace('||=', '||')  # ignore cellwise align instructions
                line = line.replace('=||', '||')  # ignore cellwise align instructions
                line = line.replace('||', '|')

            # lists
            if in_list:
                if line.strip():
                    indent = re.search('[^\s]', line).start()
                    if indent > list_leading_spaces:
                        line = line[list_leading_spaces:]

                        # adjust slightly-malformed paragraph in list for right indent -- fingers crossed
                        indent = re.search('[^\s]', line).start()
                        if indent == 1 and list_indents[0][1] == '*':
                            line =  ' ' + line
                        elif indent == 1 and list_indents[0][1] == '-':
                            line =  ' ' + line
                        elif indent in [1, 2] and list_indents[0][1] not in ['*', '-']:
                            line =  (3 - indent)*' ' + line

                    elif indent < list_leading_spaces:
                        in_list = False
                        list_indents = []
                    elif indent == list_leading_spaces:
                        l = line[indent:]
                        if not (l.startswith('* ') or l.startswith('- ') or re.match('^[^\s]+\.\s', l)):
                            in_list = False
                            list_indents = []
                        else:
                            line = line[list_leading_spaces:]
            l = line.lstrip()
            if l.startswith('* ') or  l.startswith('- ') or re.match('^[^\s]+\.\s', l):
                if not in_list:
                    list_leading_spaces = re.search('[^\s]', line).start()
                    line = line[list_leading_spaces:]
                    in_list = True
                indent = re.search('[^\s]', line).start()
                for i in range(len(list_indents)):
                    d, t, c = list_indents[i]
                    if indent == d:
                        if line[indent] == t:
                            c += 1
                        else:
                            t = line[indent]
                            c = 1
                        list_indents = list_indents[:i] + [(d, t, c)]
                        break
                else:
                    d = indent
                    t = line[indent]
                    c = 1
                    list_indents.append((d, t, c))

                if t in ['*', '-'] :
                    #depth = 0
                    #for dd, tt, cc in list_indents:
                    #    if tt == t:
                    #        depth += 1
                    pass
                elif t == 'a':
                    line = line.replace('a', chr(ord('a') + c - 1), 1)
                elif t == '1':
                    line = line.replace('1', str(c), 1)
                elif t == 'i':
                    line = line.replace('i', toRoman(c).lower(), 1)

        # only for table with td blocks:
        if in_table:
            if line == '|\\' or line == '| \\':  # leads td block
                block = []
                continue
            if line == '|':
                table.append('|' + 'NEW__LINE'.join(block) +'|')
                block = []
                continue
            if line.startswith('OPENING__PROCESSOR__TD'):
                if len(block) > 1:
                    block.append('|')
                block.append(line)
                continue
            if in_td:
                line = re.sub('\n', 'NEW__LINE', line)
                block.append(line)
                continue
            if line.startswith('CLOSING__PROCESSOR__TD'):
                block.append(line)
                continue
            if line.startswith('|'):
                if line.endswith('|\\'):
                    previous_line = line[:-2].replace('|', '||')  # restore to trac table row
                elif line.endswith('| \\'):
                    previous_line = line[:-3].replace('|', '||')  # restore to trac table row
                else:
                    table.append(line)
                continue

            if block:  # td block may not be terminated by "|" (or trac "||")
                table.append('|' + 'NEW__LINE'.join(block) +'|')
                block = []

            if table:
                table_text = '\n'.join(table)
                if 'OPENING__PROCESSOR__TD' in table_text:
                    html = markdown.markdown(table_text, extensions=[TableExtension(use_align_attribute=True)])
                    html = re.sub('OPENING__PROCESSOR__TD', r'<div align="left">', html)
                    html = re.sub('CLOSING__PROCESSOR__TD', r'</div>', html)
                else:
                    html = table_text
                line = html.replace('NEW__LINE', '\n') + '\n' + line
                table = []

            in_table = False

        for l in line.split('\n'):
            a.append(quote_prefix + l)

    a = a[:-1]
    text = '\n'.join(a)

    # remove artifacts
    text = text.replace('OPENING__PROCESSOR__CODE', '```')
    text = text.replace('CLOSING__PROCESSOR__CODE', '```')
    text = text.replace('OPENING__LEFT__BRACKET', '[')
    text = text.replace('CLOSING__RIGHT__BRACKET', ']')
    text = text.replace('AT__SIGN__IN__CODE', '@')

    # Sage-specific rewritings

    text = RE_COLOR.sub(r'$\\textcolor{\1}{\\text{\2}}$', text)
    text = RE_GIT_SERVER_SRC.sub(fr'{target_url_git_repo}/blob/master/src', text)
    text = RE_GIT_SERVER_COMMIT.sub(fr'{target_url_git_repo}/commit/\1', text)
    text = RE_TRAC_REPORT.sub(r'[This is the Trac report of id \1 that was inherited from the migration](https://trac.sagemath.org/report/\1)', text)

    def commits_list(match):
        t = '**' + match.group(1) +'**\n'
        t += '<table>'
        for c in match.group(2).split('\n')[2:]:  # the first two are blank header
            if not c:
                continue
            m = RE_COMMIT_LIST1.match(c)
            if m:
                commit_id = m.group(1)
                commit_url = m.group(2)
                commit_msg = m.group(3).replace('\`', '`')
                t += r'<tr><td><a href="{}">{}</a></td><td><code>{}</code></td></tr>'.format(commit_url, commit_id, commit_msg)
            else:
                m = RE_COMMIT_LIST2.match(c)
                if m:
                    commit_id = m.group(1)
                    commit_url = m.group(2)
                    commit_msg = m.group(3)
                    t += r'<tr><td><a href="{}">{}</a></td><td><code>{}</code></td></tr>'.format(commit_url, commit_id, commit_msg)
                else: # unusual format
                    m = RE_COMMIT_LIST3.match(c)
                    commit_id = m.group(1)
                    commit_msg = m.group(2)
                    t += r'<tr><td>{}</td><td><code>{}</code></td></tr>'.format(commit_id, commit_msg)
        t += '</table>\n'
        return t

    try:
        text = RE_NEW_COMMITS.sub(commits_list, text)
        text = RE_LAST_NEW_COMMITS.sub(commits_list, text)
    except Exception:
        pass

    text = RE_BRANCH_FORCED_PUSH.sub(r'**\1**', text)
    text = RE_BRANCH_PUSH.sub(r'**\1**', text)

    return text


class ConversionHelper:
    """
    A class that provides conversion methods that depend on information collected
    at startup, such as Wiki page names and configuration flags.
    """
    def __init__(self, source):
        """
        The Python constructor collects all the necessary information.
        """
        pagenames = source.wiki.getAllPages()
        pagenames_splitted = []
        for p in pagenames:
            pagenames_splitted += p.split('/')
        pagenames_not_splitted = [p for p in pagenames if not p in pagenames_splitted]

        self._pagenames_splitted = pagenames_splitted
        self._pagenames_not_splitted = pagenames_not_splitted
        self._keep_trac_ticket_references = False
        self._attachment_path = ''
        if config.has_option('source', 'keep_trac_ticket_references') :
            self._keep_trac_ticket_references = config.getboolean('source', 'keep_trac_ticket_references')

    def set_path(self, pagename):
        """
        Set paths from pagename
        """
        gh_pagename = ' '.join(pagename.split('/'))
        self._attachment_path = gh_pagename  #  attachment_path for the wiki_image method
        self._trac_wiki_path = pagename.replace(' ', '%20')
        self._wiki_path = gh_pagename.replace(' ', '-')

        if create_wiki_link_conversion_table:
            with open('wiki_path_conversion_table.txt', "a") as f:
                f.write(self._trac_wiki_path + ' ' + self._wiki_path)
                f.write('\n')

    def ticket_link(self, match):
        """
        Return a formatted string that replaces the match object found by re
        in the case of a Trac ticket link.
        """
        ticket = match.groups()[0]
        if self._keep_trac_ticket_references:
            # as long as the ticket themselves have not been migrated they should reference to the original place
            return r'[#%s](%s/%s)' % (ticket, trac_url_ticket, ticket)
        else:
            # leave them as is
            return r'#%s' % ticket

    def ticket_comment_link(self, match):
        """
        Return a formatted string that replaces the match object found by re
        in the case of a Trac ticket comment link.
        """
        ticket = match.group(1)
        comment = match.group(2)
        if self._keep_trac_ticket_references:
            # as long as the ticket themselves have not been migrated they should reference to the original place
            return r'[#%s comment:%s](%s/%s#comment:%s)' % (ticket, comment, trac_url_ticket, ticket, comment)
        else:
            # leave them as is
            return r'ticket:%s#comment:%s' % (ticket, comment)

    def wiki_image(self, match):
        """
        Return a formatted string that replaces the match object found by re
        in the case of a wiki link to an attached image.
        """
        mg = match.groups()
        filename = os.path.join(self._attachment_path, mg[0])
        if len(mg) > 1:
            return r'<img src="%s" width=%s>' % (filename, mg[1])
        else:
            return r'<img src="%s">' % filename

    def wiki_link(self, match):
        """
        Return a formatted string that replaces the match object found by re
        in the case of a link to a wiki page.
        """
        mg = match.groups()
        pagename = mg[0]
        if len(mg) > 1:
            display = mg[1]
            if not display:
                display = pagename
        else:
            display = pagename

        # take care of section references
        pagename_sect = pagename.split('#')
        pagename_ori = pagename
        if len(pagename_sect) > 1:
            pagename = pagename_sect[0]
            if not display:
                display = pagename_sect[1]

        if pagename.startswith('http'):
            link = pagename_ori.strip()
            return r'OPENING__LEFT__BRACKET%sCLOSING__RIGHT__BRACKET(%s)' % (display, link)
        elif pagename in self._pagenames_splitted:
            link = pagename_ori.replace(' ', '-')
            return r'OPENING__LEFT__BRACKET%sCLOSING__RIGHT__BRACKET(%s)' % (display, link)
        elif pagename in self._pagenames_not_splitted:
            # Use normalized wiki pagename
            link = pagename_ori.replace('/', ' ').replace(' ', '-')
             # \| instead of | for wiki links in a table
            return r'OPENING__LEFT__BRACKET%sCLOSING__RIGHT__BRACKET(%s)' % (display, link)
        else:
            # we assume that this must be a Trac macro like TicketQuery
            # first lets extract arguments
            macro_split = pagename.split('(')
            macro = macro_split[0]
            args = None
            if len(macro_split) > 1:
                args =  macro_split[1]
            display = 'This is the Trac macro *%s* that was inherited from the migration' % macro
            link = '%s/WikiMacros#%s-macro' % (trac_url_wiki, macro)
            if args:
                return r'OPENING__LEFT__BRACKET%s called with arguments (%s)CLOSING__RIGHT__BRACKET(%s)' % (display, args, link)
            return r'OPENING__LEFT__BRACKET%sCLOSING__RIGHT__BRACKET(%s)' % (display, link)

    def camelcase_wiki_link(self, match):
        """
        Return a formatted string that replaces the match object found by re
        in the case of a link to a wiki page recognized from CamelCase.
        """
        if match.group(1) in self._pagenames_splitted:
            return self.wiki_link(match)
        return match.group(0)


def github_ref_url(ref):
    if re.fullmatch(r'[0-9a-f]{40}', ref):  # commit sha
        return f'{target_url_git_repo}/commit/{ref}'
    else:  # assume branch
        return f'{target_url_git_repo}/tree/{ref}'

def github_ref_markdown(ref):
    url = github_ref_url(ref)
    return f'[{ref}]({url})'

def convert_xmlrpc_datetime(dt):
    # datetime.strptime(str(dt), "%Y%m%dT%X").isoformat() + "Z"
    return datetime.strptime(str(dt), "%Y%m%dT%H:%M:%S")

def convert_trac_datetime(dt):
    return datetime.strptime(str(dt), "%Y-%m-%d %H:%M:%S")

def maptickettype(tickettype):
    "Return GitHub label corresponding to Trac ``tickettype``"
    if not tickettype:
        return None
    if tickettype == 'defect':
        return 'bug'
    if tickettype == 'enhancement':
        return 'enhancement'
    # if tickettype == 'clarification':
    #     return 'question'
    # if tickettype == 'task':
    #     return 'enhancement'
    if tickettype == 'PLEASE CHANGE':
        return None
    #return tickettype.lower()
    return None

def mapresolution(resolution):
    "Return GitHub label corresponding to Trac ``resolution``"
    if resolution == 'fixed':
        return None
    if not resolution:
        return None
    return resolution

component_frequency = defaultdict(lambda: 0)
def mapcomponent(component):
    "Return GitHub label corresponding to Trac ``component``"
    if component == 'PLEASE CHANGE':
        return None
    component = component.replace('_', ' ').lower()
    if component in ['solaris', 'cygwin']:
        component = 'porting: ' + component
    elif component == 'freebsd':
        component = 'porting: bsd'
    elif component == 'aix or hp-ux ports':
        component = 'porting: aix or hp-ux'
    elif component == 'experimental package':
        component = 'packages: experimental'
    elif component == 'optional packages':
        component = 'packages: optional'
    elif component == 'plotting':
        component = 'graphics'
    elif component == 'doctest':
        component = 'doctest coverage'
    elif component == 'sage-check':
        component = 'spkg-check'
    component_frequency[component] += 1
    # Prefix it with "component: " so that they show up as one group in the GitHub dropdown list
    return f'component: {component}'

default_priority = 'major'
def mappriority(priority):
    "Return GitHub label corresponding to Trac ``priority``"
    if priority == default_priority:
        return None
    return priority

default_severity = 'normal'
def mapseverity(severity):
    "Return GitHub label corresponding to Trac ``severity``"
    if severity == default_severity:
        return None
    return severity

def mapstatus(status):
    "Return a pair: (status, label)"
    status = status.lower()
    if status in ['needs_review', 'needs_work', 'needs_info', 'positive_review']:
        return 'open', status.replace('_', ' ')
    elif status in ['new', 'assigned', 'analyzed', 'reopened', 'open', 'needs_info_new']:
        return 'open', None
    elif status in ['closed'] :
        return 'closed', None
    else:
        log.warning("unknown ticket status: " + status)
        return 'open', status.replace('_', ' ')

keyword_frequency = defaultdict(lambda: 0)
def mapkeywords(keywords):
    "Return a pair: (list of keywords for ticket description, list of labels)"
    keep_as_keywords = []
    labels = []
    keywords = keywords.replace(';', ',')
    has_comma = ',' in keywords
    for keyword in keywords.split(','):
        keyword = keyword.strip()
        if not keyword:
            continue
        if keywords_to_labels is True:
            labels.append(keyword)
        elif isinstance(keywords_to_labels, dict) and keyword in keywords_to_labels:
            labels.append(keywords_to_labels[keyword])
        else:
            keep_as_keywords.append(keyword)
            keyword_frequency[keyword.lower()] += 1
            if not has_comma:
                # Maybe not a phrase but whitespace-separated keywords
                words = keywords.split()
                if len(words) > 1:
                    for word in words:
                        keyword_frequency[word.lower()] += 1

    return keep_as_keywords, labels

milestone_map = {}
unmapped_milestones = defaultdict(lambda: 0)
def mapmilestone(title):
    "Return a pair: (milestone title, label)"
    if not title:
        return None, None
    title = title.lower()
    if title in ['sage-duplicate/invalid/wontfix', 'sage-duplicate/invalid', 'sage-duplicate']:
        return None, 'duplicate/invalid/wontfix'
    if title == 'sage-wait':
        title = 'sage-pending'
    if title in ['sage-feature', 'sage-pending', 'sage-wishlist']:
        return None, title[5:]
    if title == 'sage-combinat':
        return None, mapcomponent('combinatorics')
    if title == 'sage-symbolics':
        return None, mapcomponent('symbolics')
    if title == 'sage-i18n':
        return None, mapcomponent('translations')
    if re.match('^[0-9]', title):
        title = 'sage-' + title
    if re.fullmatch('sage-[1-9]', title):
        title = title + '.0'
    # Remap milestones for releases that were canceled/renamed
    if title == 'sage-2.8.4.3':
        title = 'sage-2.8.5'
    elif title == 'sage-3.2.4':
        title = 'sage-3.3'
    elif title == 'sage-4.0.3':
        title = 'sage-4.1'
    elif title == 'sage-4.1.3':
        title = 'sage-4.2'
    elif title == 'sage-4.4.5':
        title = 'sage-4.5'
    elif title == 'sage-4.7.3':
        title = 'sage-4.8'
    elif title == 'sage-6.11':
        title = 'sage-7.0'
    elif title == 'sage-7.7':
        title = 'sage-8.0'

    return title, None

def gh_create_milestone(dest, milestone_data) :
    if dest is None : return None

    milestone = dest.create_milestone(milestone_data['title'], milestone_data['state'], milestone_data['description'], milestone_data.get('due_date', GithubObject.NotSet) )
    sleep(sleep_after_request)
    return milestone

def gh_ensure_label(dest, labelname, labelcolor) :
    if dest is None or labelname is None:
        return
    labelname = labelname.lower()
    if labelname in gh_labels:
        return
    log.info('Create label "%s" with color #%s' % (labelname, labelcolor));
    gh_label = dest.create_label(labelname, labelcolor);
    gh_labels[labelname] = gh_label;
    sleep(sleep_after_request)

def gh_create_issue(dest, issue_data) :
    if dest is None : return None
    if 'labels' in issue_data:
        labels = [gh_labels[label.lower()] for label in issue_data.pop('labels')]
    else:
        labels = GithubObject.NotSet

    description = issue_data.pop('description')

    if github:
        description_pre = ""
        description_pre += 'Original creator: ' + issue_data.pop('user') + '\n\n'
        description_pre += 'Original creation time: ' + str(issue_data.pop('created_at')) + '\n\n'
        description = description_pre + description
    else:
        user_url = gh_user_url(dest, issue_data['user'])
        if user_url:
            issue_data['user'] = user_url

    gh_issue = dest.create_issue(issue_data.pop('title'),
                                 description,
                                 assignee=issue_data.pop('assignee', GithubObject.NotSet),
                                 milestone=issue_data.pop('milestone', GithubObject.NotSet),
                                 labels=labels,
                                 **issue_data)

    log.debug("  created issue " + str(gh_issue))
    sleep(sleep_after_request)

    return gh_issue

def gh_comment_issue(dest, issue, comment, src_ticket_id, comment_id=None):
    # upload attachement, if there is one
    if 'attachment_name' in comment :
        filename = comment.pop('attachment_name')
        attachment = comment.pop('attachment')
        if attachment_export:
            dirname = os.path.join(attachment_export_dir, 'ticket' + str(src_ticket_id))
            if not os.path.isdir(dirname) :
                os.makedirs(dirname)
            # write attachment data to binary file
            open(os.path.join(dirname, filename), 'wb').write(attachment)
            attachment_url = attachment_export_url + 'ticket' + str(src_ticket_id) + '/' + filename
            if github:
                note = 'Attachment [%s](%s) by %s created at %s' % (filename, attachment_url, comment['user'], comment['created_at'])
            else:
                note = ''
                user_url = gh_user_url(dest, comment['user'])
                issue.create_attachment(filename,
                                        "application/octet-stream",
                                        attachment_url,
                                        user=user_url,
                                        created_at=comment['created_at'])
        elif gh_user is not None:
            if dest is None : return
            gistname = dest.name + ' issue ' + str(issue.number) + ' attachment ' + filename
            filecontent = InputFileContent(attachment)
            try :
                gist = gh_user.create_gist(False,
                                           { gistname : filecontent },
                                           'Attachment %s to issue #%d created by %s at %s' % (filename, issue.number, comment['user'], comment['created_at']) )
                note = 'Attachment [%s](%s) by %s created at %s' % (filename, gist.files[gistname].raw_url, comment['user'], comment['created_at'])
            except UnicodeDecodeError :
                note = 'Binary attachment %s by %s created at %s lost by Trac to GitHub conversion.' % (filename, comment['user'], comment['created_at'])
                print ('  LOSING ATTACHMENT', filename, 'in issue', issue.number)
            sleep(sleep_after_attachment)
        else:
            note = 'Attachment'
    else :
        if github:
            note = 'Comment by %s created at %s' % (comment.pop('user'), comment.pop('created_at'))
        else:
            note = ''

    body = comment.pop('note', '')
    if body:
        if note:
            note += '\n\n'
        note += body

    if comment_id:
        anchor = f"<a id='comment:{comment_id}'></a>"
        note = anchor + '\n' + note

    if dest is None : return

    if not github:
        user_url = gh_user_url(dest, comment['user'])
        if user_url:
           comment['user'] = user_url

    issue.create_comment(note, **comment)
    sleep(sleep_after_request)

def normalize_labels(labels):
    if 'duplicate/invalid/wontfix' in labels:
        labels.remove('duplicate/invalid/wontfix')
        if any(x in labels for x in ['duplicate', 'invalid', 'wontfix']):
            return
        labels.append('invalid')

def gh_update_issue_property(dest, issue, key, val, oldval=None, **kwds):
    if dest is None : return

    if key == 'labels':
        labels = [gh_labels[label.lower()] for label in val if label]
        normalize_labels(labels)
        if github:
            issue.set_labels(*labels)
        else:
            oldlabels = [gh_labels[label.lower()] for label in oldval if label]
            normalize_labels(oldlabels)
            for label in oldlabels:
                if label not in labels:
                    # https://docs.github.com/en/developers/webhooks-and-events/events/issue-event-types#unlabeled
                    issue.create_event('unlabeled', label=label, **kwds)
            for label in labels:
                if label not in oldlabels:
                    # https://docs.github.com/en/developers/webhooks-and-events/events/issue-event-types#labeled
                    issue.create_event('labeled', label=label, **kwds)
    elif key == 'assignee' :
        if issue.assignee == val:
            return
        if issue.assignees:
            issue.remove_from_assignees(issue.assignee)
        if val is not None and val is not GithubObject.NotSet and val != '' :
            issue.add_to_assignees(val)
    elif key == 'state' :
        if github:
            issue.edit(state = val)
        else:
            # https://docs.github.com/en/developers/webhooks-and-events/events/issue-event-types#reopened
            # https://docs.github.com/en/developers/webhooks-and-events/events/issue-event-types#closed
            issue.create_event('reopened' if val=='open' else 'closed', **kwds)
    elif key == 'description' :
        issue.edit(body=val)
    elif key == 'title' :
        if github:
            issue.edit(title = val)
        else:
            issue.create_event('renamed', rename={'from': oldval, 'to': val}, **kwds)
    elif key == 'milestone' :
        if github:
            issue.edit(milestone=val)
        else:
            if oldval and oldval is not GithubObject.NotSet:
                # https://docs.github.com/en/developers/webhooks-and-events/events/issue-event-types#demilestoned
                issue.create_event('demilestoned', milestone=oldval, **kwds)
            if val and val is not GithubObject.NotSet:
                # https://docs.github.com/en/developers/webhooks-and-events/events/issue-event-types#milestoned
                issue.create_event('milestoned', milestone=val, **kwds)
    else :
        raise ValueError('Unknown key ' + key)

    sleep(sleep_after_request)

unmapped_users = defaultdict(lambda: 0)

def gh_username(dest, origname) :
    origname = origname.strip('\u200b')
    if origname.startswith('gh-'):
        return '@' + origname[3:]
    if origname.startswith('github/'):
        # example: https://trac.sagemath.org/ticket/17999
        return '@' + origname[7:]
    if origname.startswith('gh:'):
        # example: https://trac.sagemath.org/ticket/24876
        return '@' + origname[3:]
    gh_name = users_map.get(origname, None)
    if gh_name:
        return '@' + gh_name
    assert not origname.startswith('@')
    if re.fullmatch('[-A-Za-z._0-9]+', origname):
        # heuristic pattern for valid Trac account name (not an email address or full name or junk)
        unmapped_users[origname] += 1
    return origname

def gh_user_url(dest, username):
    if username.startswith('@'):
        return f'https://github.com/{username[1:]}'
    if re.fullmatch('[-A-Za-z._0-9]+', username):
        # heuristic pattern for valid Trac account name (not an email address or junk)
        # Use this URL as the id (this is current best guess what a mannequin user would look like)
        return f'https://trac.sagemath.org/admin/accounts/users/{username}'
    return None

def gh_username_list(dest, orignames, ignore=['somebody', 'tbd', 'tba']):
    "Split and transform comma- separated lists of names"
    if not orignames:
        return ''
    names = []
    for origname in orignames.split(','):
        name = gh_username(dest, origname.strip())
        if name and name not in ignore:
            names.append(name)
    return ', '.join(names)

@cache.memoize(ignore=[0, 'source'])
def get_all_milestones(source):
    return source.ticket.milestone.getAll()

@cache.memoize(ignore=[0, 'source'])
def get_milestone(source, milestone_name):
    return source.ticket.milestone.get(milestone_name)

@cache.memoize(ignore=[0, 'source'])
def get_changeLog(source, src_ticket_id):
    while True:
        try:
            if sleep_before_xmlrpc:
                sleep(sleep_before_xmlrpc)
            return source.ticket.changeLog(src_ticket_id)
        except Exception as e:
            print(e)
            print('Sleeping')
            sleep(sleep_before_xmlrpc_retry)
            print('Retrying')

@cache.memoize(ignore=[0, 'source'])
def get_ticket_attachment(source, src_ticket_id, attachment_name):
    while True:
        try:
            return source.ticket.getAttachment(src_ticket_id, attachment_name)
        except Exception as e:
            print(e)
            print('Sleeping')
            sleep(sleep_before_xmlrpc_retry)
            print('Retrying')

@cache.memoize()
def get_all_tickets(filter_issues):
    call = client.MultiCall(source)
    for ticket in source.ticket.query(filter_issues):
        call.ticket.get(ticket)
    return call()

def convert_issues(source, dest, only_issues = None, blacklist_issues = None):
    conv_help = ConversionHelper(source)

    if migrate_milestones:
        for milestone_name in get_all_milestones(source):
            milestone = get_milestone(source, milestone_name)
            title = milestone.pop('name')
            title, label = mapmilestone(title)
            if title:
                log.info("Creating milestone " + title)
                new_milestone = {
                    'description' : trac2markdown(milestone.pop('description'), '/milestones/', conv_help, False),
                    'title' : title,
                    'state' : 'open' if str(milestone.pop('completed')) == '0'  else 'closed'
                    }
                due = milestone.pop('due')
                if due:
                    new_milestone['due_date'] = convert_xmlrpc_datetime(due)
                if milestone:
                    log.warning(f"Discarded milestone data: {milestone}")
                milestone_map[milestone_name] = gh_create_milestone(dest, new_milestone)
                log.debug(milestone_map[milestone_name])

    nextticketid = 1
    ticketcount = 0

    for src_ticket in get_all_tickets(filter_issues):
        src_ticket_id, time_created, time_changed, src_ticket_data = src_ticket

        if only_issues and src_ticket_id not in only_issues:
            print("SKIP unwanted ticket #%s" % src_ticket_id)
            continue
        if blacklist_issues and src_ticket_id in blacklist_issues:
            print("SKIP blacklisted ticket #%s" % src_ticket_id)
            continue

        if github and not only_issues and not blacklist_issues and not config.has_option('issues', 'filter_issues') :
            while nextticketid < src_ticket_id :
                print("Ticket %d missing in Trac. Generating empty one in GitHub." % nextticketid)

                issue_data = {
                    'title' : 'Deleted trac ticket %d' % nextticketid,
                    'description' : 'Ticket %d had been deleted in the original Trac instance. This empty ticket serves as placeholder to ensure a proper 1:1 mapping of ticket ids to issue ids.' % nextticketid,
                    'labels' : []
                }

                issue = gh_create_issue(dest, issue_data)
                gh_update_issue_property(dest, issue, 'state', 'closed')

                nextticketid = nextticketid+1

        nextticketid = nextticketid+1;

        # src_ticket_data.keys(): ['status', 'changetime', 'description', 'reporter', 'cc', 'type', 'milestone', '_ts',
        # 'component', 'owner', 'summary', 'platform', 'version', 'time', 'keywords', 'resolution']

        changelog = get_changeLog(source, src_ticket_id)

        log.info('Migrating ticket #%s (%3d changes): "%s"' % (src_ticket_id, len(changelog), src_ticket_data['summary'][:50].replace('"', '\'')))

        def issue_description(src_ticket_data):
            description_pre = ""
            description_post = ""

            owner = gh_username_list(dest, src_ticket_data.pop('owner', None))
            if owner:
                description_post += '\n\n**Assignee:** ' + owner

            version = src_ticket_data.pop('version', None)
            if version is not None and version != 'trunk' :
                description_post += '\n\n**Version:** ' + version

            # subscribe persons in cc
            cc = src_ticket_data.pop('cc', '')
            ccstr = ''
            for person in cc.replace(';', ',').split(',') :
                person = person.strip()
                if person == '' : continue
                person = gh_username(dest, person)
                ccstr += ' ' + person
            if ccstr != '' :
                description_post += '\n\n**CC:** ' + ccstr

            keywords, labels = mapkeywords(src_ticket_data.pop('keywords', ''))
            if keywords:
                description_post += '\n\n**Keywords:** ' + ', '.join(keywords)

            branch = src_ticket_data.pop('branch', '')
            commit = src_ticket_data.pop('commit', '')
            # These two are the same in all closed-fixed tickets. Reduce noise.
            if branch and branch == commit:
                description_post += '\n\n**Branch/Commit:** ' + github_ref_markdown(branch)
            else:
                if branch:
                    description_post += f'\n\n**Branch:** ' + github_ref_markdown(branch)
                if commit:
                    description_post += f'\n\n**Commit:** ' + github_ref_markdown(commit)

            description = src_ticket_data.pop('description', '')

            for field, value in src_ticket_data.items():
                if (not field.startswith('_')
                    and field not in ['changetime', 'time']
                    and value and value not in ['N/A', 'tba', 'tbd', 'closed', 'somebody']):
                    field = field.title().replace('_', ' ')
                    description_post += f'\n\n**{field}:** {value}'

            description_post += f'\n\nIssue created by migration from {trac_url_ticket}/{src_ticket_id}\n\n'

            return description_pre + trac2markdown(description, '/issues/', conv_help, False) + description_post

        # get original component, owner
        # src_ticket_data['component'] is the component after all changes, but for creating the issue we want the component
        # that was set when the issue was created; we should get this from the first changelog entry that changed a component
        # ... and similar for other attributes
        first_old_values = {}
        for change in changelog :
            time, author, change_type, oldvalue, newvalue, permanent = change
            if change_type not in first_old_values:
                if (change_type not in ['milestone', 'cc', 'reporter', 'comment', 'attachment']
                    and not change_type.startswith('_comment')):
                    field = change_type
                    if isinstance(oldvalue, str):
                        oldvalue = oldvalue.strip()
                    first_old_values[field] = oldvalue

        # If no change changed a certain attribute, then that attribute is given by ticket data
        # (When writing migration archives, this is true unconditionally.)
        if github:
            src_ticket_data.update(first_old_values)

        # Process src_ticket_data and remove (using pop) attributes that are processed already.
        # issue_description dumps everything that has not been processed in the description.

        issue_data = {}

        def milestone_labels(src_ticket_data, status):
            labels = []
            if add_label:
                labels.append(add_label)

            component = src_ticket_data.pop('component', None)
            if component is not None and component.strip() != '' :
                label = mapcomponent(component)
                if label:
                    labels.append(label)
                    gh_ensure_label(dest, label, labelcolor['component'])

            priority = src_ticket_data.pop('priority', default_priority)
            if priority != default_priority:
                label = mappriority(priority)
                labels.append(label)
                gh_ensure_label(dest, label, labelcolor['priority'])

            severity = src_ticket_data.pop('severity', default_severity)
            if severity != default_severity:
                labels.append(severity)
                gh_ensure_label(dest, severity, labelcolor['severity'])

            tickettype = maptickettype(src_ticket_data.pop('type', None))
            if tickettype is not None :
                labels.append(tickettype)
                gh_ensure_label(dest, tickettype, labelcolor['type'])

            resolution = mapresolution(src_ticket_data.pop('resolution', None))
            if resolution is not None:
                labels.append(resolution)
                gh_ensure_label(dest, resolution, labelcolor['resolution'])

            keywords, keyword_labels = mapkeywords(src_ticket_data.get('keywords', ''))
            for label in keyword_labels:
                labels.append(label)
                gh_ensure_label(dest, label, labelcolor['keyword'])

            milestone, label = mapmilestone(src_ticket_data.pop('milestone', None))
            if milestone and milestone in milestone_map:
                milestone = milestone_map[milestone]
            elif milestone:
                # Unknown milestone, put it back
                logging.warning(f'Unknown milestone "{milestone}"')
                unmapped_milestones[milestone] += 1
                src_ticket_data['milestone'] = milestone
                milestone = None
            elif label:
                labels.append(label)
                gh_ensure_label(dest, label, labelcolor.get(label, None) or labelcolor['milestone'])

            status = src_ticket_data.pop('status', status)
            issue_state, label = mapstatus(status)
            if label:
                labels.append(label)
                gh_ensure_label(dest, label, labelcolor.get(label, None) or labelcolor['resolution'])

            normalize_labels(labels)
            return milestone, labels

        def title_status(summary, status=None):
            r"""
            Decode title prefixes such as [with patch, positive review] used in early Sage tickets.

            Return (cleaned up title, status)
            """
            if m := re.match(r'^\[([A-Za-z_ ,;?]*)\] *', summary):
                phrases = m.group(1).replace(';', ',').split(',')
                keep_phrases = []
                for phrase in phrases:
                    phrase = phrase.strip()
                    if re.fullmatch(r'needs review|(with )?positive review|needs work', phrase):
                        status = phrase.replace('with ', '').replace(' ', '_')
                    elif re.fullmatch(r'(with)? *(new|trivial)? *(patch|bundl)e?s?|(with)? *spkg', phrase):
                        pass
                    else:
                        keep_phrases.append(phrase)
                if keep_phrases:
                    summary = '[' + ', '.join(keep_phrases) + '] ' + summary[m.end(0):]
                else:
                    summary = summary[m.end(0):]
            return summary, status

        tmp_src_ticket_data = copy(src_ticket_data)

        title, status = title_status(tmp_src_ticket_data.pop('summary'))
        milestone, labels = milestone_labels(tmp_src_ticket_data, status)
        issue_data['title'] = title
        issue_data['labels'] = labels
        if milestone:
            issue_data['milestone'] = milestone
        #'assignee' : assignee,

        if not github:
            issue_data['user'] = gh_username(dest, tmp_src_ticket_data.pop('reporter'))
            issue_data['created_at'] = convert_xmlrpc_datetime(time_created)
            issue_data['number'] = int(src_ticket_id)
            # Find closed_at
            for time, author, change_type, oldvalue, newvalue, permanent in reversed(changelog):
                if change_type == 'status':
                    state, label = mapstatus(newvalue)
                    if state == 'closed':
                        issue_data['closed_at'] = convert_xmlrpc_datetime(time)
                        break

        issue_data['description'] = issue_description(tmp_src_ticket_data)

        issue = gh_create_issue(dest, issue_data)

        if github:
            status = src_ticket_data.pop('status')
            if status in ['closed']:
                # sometimes a ticket is already closed at creation, so close issue
                gh_update_issue_property(dest, issue, 'state', 'closed')
        else:
            src_ticket_data.update(first_old_values)
            title, status = title_status(src_ticket_data.get('summary'), src_ticket_data.get('status'))
            tmp_src_ticket_data = copy(src_ticket_data)
            milestone, labels = milestone_labels(tmp_src_ticket_data, status)

        issue_state, label = mapstatus(status)

        def update_labels(labels, add_label, remove_label, label_category='type'):
            oldlabels = copy(labels)
            if remove_label:
                with contextlib.suppress(ValueError):
                    labels.remove(remove_label)
            if add_label:
                labels.append(add_label)
                gh_ensure_label(dest, add_label, labelcolor[label_category])
            if labels != oldlabels:
                gh_update_issue_property(dest, issue, 'labels', labels, oldval=oldlabels, **event_data)
            return labels

        def change_status(newvalue):
            oldvalue = src_ticket_data.get('status')
            src_ticket_data['status'] = newvalue
            oldstate, oldlabel = mapstatus(oldvalue)
            newstate, newlabel = mapstatus(newvalue)
            new_labels = update_labels(labels, newlabel, oldlabel)
            if issue_state != newstate :
                gh_update_issue_property(dest, issue, 'state', newstate, **event_data)
            return issue_state, new_labels

        attachment = None
        for change in changelog:
            time, author, change_type, oldvalue, newvalue, permanent = change
            change_time = str(convert_xmlrpc_datetime(time))
            #print(change)
            log.debug("  %s by %s (%s -> %s)" % (change_type, author, str(oldvalue)[:40].replace("\n", " "), str(newvalue)[:40].replace("\n", " ")))
            #assert attachment is None or change_type == "comment", "an attachment must be followed by a comment"
            # if author in ['anonymous', 'Draftmen888'] :
            #     print ("  SKIPPING CHANGE BY", author)
            #     continue
            user = gh_username(dest, author)
            user_url = gh_user_url(dest, user)

            comment_data = {
                'created_at': convert_trac_datetime(change_time),
                'user': user,
            }
            event_data = {
                'created_at': convert_trac_datetime(change_time),
                'actor': user_url,
            }
            if change_type == "attachment":
                # The attachment will be described in the next change!
                attachment = change
            elif change_type == "comment":
                # oldvalue is here either x or y.x, where x is the number of this comment and y is the number of the comment that is replied to
                m = re.match('([0-9]+.)?([0-9]+)', oldvalue)
                x = m and m.group(2)
                desc = newvalue.strip();
                if desc == '' and attachment is None :
                    # empty description and not description of attachment
                    continue
                comment_data['note'] = trac2markdown(desc, '/issues/', conv_help, False)

                if attachment is not None :
                    comment_data['attachment_name'] = attachment[4]  # name of attachment
                    comment_data['attachment'] = get_ticket_attachment(source, src_ticket_id, attachment[4]).data
                    attachment = None
                gh_comment_issue(dest, issue, comment_data, src_ticket_id, comment_id=x)
            elif change_type.startswith("_comment") :
                # this is an old version of a comment, which has been edited later (given in previous change),
                # e.g., see http://localhost:8080/ticket/3431#comment:9 http://localhost:8080/ticket/3400#comment:14
                # we will forget about these old versions and only keep the latest one
                pass
            elif change_type == "status" :
                issue_state, labels = change_status(newvalue)
            elif change_type == "resolution" :
                oldresolution = mapresolution(oldvalue)
                newresolution = mapresolution(newvalue)
                labels = update_labels(labels, newresolution, oldresolution, 'type')
            elif change_type == "component" :
                oldlabel = mapcomponent(oldvalue)
                newlabel = mapcomponent(newvalue)
                labels = update_labels(labels, newlabel, oldlabel, 'component')
            elif change_type == "owner" :
                oldvalue = gh_username_list(dest, oldvalue)
                newvalue = gh_username_list(dest, newvalue)
                if oldvalue and newvalue:
                    comment_data['note'] = '**Changing assignee** from ' + oldvalue + ' to ' + newvalue + '.'
                elif newvalue:
                    comment_data['note'] = '**Assignee:** ' + newvalue
                else:
                    comment_data['note'] = '**Remove assignee** ' + oldvalue + '.'
                if newvalue != oldvalue:
                    gh_comment_issue(dest, issue, comment_data, src_ticket_id)

                # if newvalue != oldvalue :
                #     assignee = gh_username(dest, newvalue)
                #     if not assignee.startswith('@') :
                #         assignee = GithubObject.NotSet
                #     gh_update_issue_property(dest, issue, 'assignee', assignee)
            elif change_type == "version" :
                if oldvalue != '' :
                    desc = "**Version changed** from %s to %s." % (oldvalue, newvalue)
                else :
                    desc = "**Version:** " + newvalue
                comment_data['note'] = desc
                gh_comment_issue(dest, issue, comment_data, src_ticket_id)
            elif change_type == "milestone" :
                oldmilestone, oldlabel = mapmilestone(oldvalue)
                newmilestone, newlabel = mapmilestone(newvalue)
                if oldmilestone and oldmilestone in milestone_map:
                    oldmilestone = milestone_map[oldmilestone]
                else:
                    if oldmilestone:
                        logging.warning(f'Ignoring unknown milestone "{oldmilestone}"')
                        unmapped_milestones[oldmilestone] += 1
                    oldmilestone = GithubObject.NotSet
                if newmilestone and newmilestone in milestone_map:
                    newmilestone = milestone_map[newmilestone]
                else:
                    if newmilestone:
                        logging.warning(f'Ignoring unknown milestone "{newmilestone}"')
                        unmapped_milestones[newmilestone] += 1
                    newmilestone = GithubObject.NotSet
                if oldmilestone != newmilestone:
                    gh_update_issue_property(dest, issue, 'milestone',
                                             newmilestone, oldval=oldmilestone, **event_data)
                labels = update_labels(labels, newlabel, oldlabel, 'milestone')
            elif change_type == "cc" :
                pass  # we handle only the final list of CCs (above)
            elif change_type == "type" :
                oldtype = maptickettype(oldvalue)
                newtype = maptickettype(newvalue)
                labels = update_labels(labels, newtype, oldtype, 'type')
            elif change_type == "description" :
                if github:
                    issue_data['description'] = issue_description(src_ticket_data) + '\n\n(changed by ' + user + ' at ' + change_time + ')'
                    gh_update_issue_property(dest, issue, 'description', issue_data['description'], **event_data)
                else:
                    body = '**Description changed:**\n``````diff\n'
                    old_description = trac2markdown(oldvalue, '/issues/', conv_help, False)
                    new_description = trac2markdown(newvalue, '/issues/', conv_help, False)
                    body += '\n'.join(unified_diff(old_description.split('\n'),
                                                   new_description.split('\n'),
                                                   lineterm=''))
                    body += '\n``````\n'
                    comment_data['note'] = body
                    gh_comment_issue(dest, issue, comment_data, src_ticket_id)
            elif change_type == "summary" :
                oldtitle, oldstatus = title_status(oldvalue)
                title, status = title_status(newvalue)
                if title != oldtitle:
                    issue_data['title'] = title
                    gh_update_issue_property(dest, issue, 'title', title, oldval=oldtitle, **event_data)
                if status is not None:
                    issue_state, labels = change_status(status)
            elif change_type == "priority" :
                oldlabel = mappriority(oldvalue)
                newlabel = mappriority(newvalue)
                labels = update_labels(labels, newlabel, oldlabel, 'priority')
            elif change_type == "severity" :
                oldlabel = mapseverity(oldvalue)
                newlabel = mapseverity(newvalue)
                labels = update_labels(labels, newlabel, oldlabel, 'severity')
            elif change_type == "keywords" :
                oldlabels = copy(labels)
                oldkeywords, oldkeywordlabels = mapkeywords(oldvalue)
                newkeywords, newkeywordlabels = mapkeywords(newvalue)
                for label in oldkeywordlabels:
                    with contextlib.suppress(ValueError):
                        labels.remove(label)
                for label in newkeywordlabels:
                    labels.append(label)
                    gh_ensure_label(dest, label, labelcolor['keyword'])
                if oldkeywords != newkeywords:
                    comment_data['note'] = '**Changing keywords** from "' + ', '.join(oldkeywords) + '" to "' + ', '.join(newkeywords) + '".'
                    gh_comment_issue(dest, issue, comment_data, src_ticket_id)
                if labels != oldlabels:
                    gh_update_issue_property(dest, issue, 'labels', labels, oldval=oldlabels, **event_data)
            else:
                if oldvalue != newvalue:
                    if change_type in ['branch', 'commit']:
                        if oldvalue:
                            oldvalue = github_ref_markdown(oldvalue)
                        if newvalue:
                            newvalue = github_ref_markdown(newvalue)
                    if not oldvalue:
                        comment_data['note'] = f'**{change_type.title()}:** {newvalue}'
                    else:
                        comment_data['note'] = f'**Changing {change_type}** from "{oldvalue}" to "{newvalue}".'
                    gh_comment_issue(dest, issue, comment_data, src_ticket_id)

        #assert attachment is None

        ticketcount += 1
        if ticketcount % 10 == 0 and sleep_after_10tickets > 0 :
            print ('%d tickets migrated. Waiting %d seconds to let GitHub/Trac cool down.' % (ticketcount, sleep_after_10tickets))
            sleep(sleep_after_10tickets)

def convert_wiki(source, dest):
    exclude_authors = ['trac']

    if not os.path.isdir(wiki_export_dir):
        os.makedirs(wiki_export_dir)

    client.MultiCall(source)
    conv_help = ConversionHelper(source)

    if os.path.exists('links.txt'):
        os.remove('links.txt')

    for pagename in source.wiki.getAllPages():
        info = source.wiki.getPageInfo(pagename)
        if info['author'] in exclude_authors:
            continue

        page = source.wiki.getPage(pagename)
        print ("Migrate Wikipage", pagename)

        # Github wiki does not have folder structure
        gh_pagename = ' '.join(pagename.split('/'))

        conv_help.set_path(pagename)
        converted = trac2markdown(page, os.path.dirname('/wiki/%s' % gh_pagename), conv_help)

        attachments = []
        for attachment in source.wiki.listAttachments(pagename):
            print ("  Attachment", attachment)
            attachmentname = os.path.basename(attachment)
            attachmentdata = source.wiki.getAttachment(attachment).data

            dirname = os.path.join(wiki_export_dir, gh_pagename)
            if not os.path.isdir(dirname):
                os.makedirs(dirname)
            # write attachment data to binary file
            open(os.path.join(dirname, attachmentname), 'wb').write(attachmentdata)
            attachmenturl = gh_pagename + '/' + attachmentname

            converted = re.sub(r'\[attachment:%s\s([^\[\]]+)\]' % re.escape(attachmentname), r'[\1](%s)' % attachmenturl, converted)

            attachments.append((attachmentname, attachmenturl))

        # add a list of attachments
        if len(attachments) > 0 :
            converted += '\n---\n\nAttachments:\n'
            for (name, url) in attachments :
                converted += ' * [' + name + '](' + url + ')\n'

        # TODO we could use the GitHub API to write into the Wiki repository of the GitHub project
        outfile = os.path.join(wiki_export_dir, gh_pagename + '.md')
        # For wiki page names with slashes
        os.makedirs(os.path.dirname(outfile), exist_ok=True)
        try :
            open(outfile, 'w').write(converted)
        except UnicodeEncodeError as e :
            print ('EXCEPTION:', e)
            print ('  Context:', e.object[e.start-20:e.end+20])
            print ('  Retrying with UTF-8 encoding')
            codecs.open(outfile, 'w', 'utf-8').write(converted)


if __name__ == "__main__":

    from rich.logging import RichHandler
    FORMAT = "%(message)s"
    logging.basicConfig(
        level="INFO", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
    )

    source = client.ServerProxy(trac_url)

    github = None
    dest = None
    gh_user = None

    if must_convert_issues:
        if github_token is not None:
            github = Github(github_token, base_url=github_api_url)
        elif github_username is not None:
            github = Github(github_username, github_password, base_url=github_api_url)
        if github:
            dest = github.get_repo(github_project)
            gh_user = github.get_user()
            for l in dest.get_labels() :
                gh_labels[l.name.lower()] = l
            #print 'Existing labels:', gh_labels.keys()
        else:
            requester = MigrationArchiveWritingRequester(migration_archive, wiki_export_dir)
            dest = Repository(requester, None, dict(name="sagetest",
                                                    url="https://github.com/sagemath/sagetest"), None)
            #print(dest.url)
            sleep_after_request = 0

    try:
        if must_convert_issues:
            convert_issues(source, dest, only_issues = only_issues, blacklist_issues = blacklist_issues)

        if must_convert_wiki:
            convert_wiki(source, dest)
    finally:
        print(f'Unmapped users: {sorted(unmapped_users.items(), key=lambda x: -x[1])}')
        print(f'Unmapped keyword frequencies: {sorted(keyword_frequency.items(), key=lambda x: -x[1])}')
        print(f'Unmapped milestones: {sorted(unmapped_milestones.items(), key=lambda x: -x[1])}')
        print(f'Components: {sorted(component_frequency.items(), key=lambda x: -x[1])}')
