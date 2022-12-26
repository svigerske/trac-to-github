#!/usr/bin/env python3
# vim: autoindent tabstop=4 shiftwidth=4 expandtab softtabstop=4 filetype=python fileencoding=utf-8
'''
Copyright © 2018-2019
    Stefan Vigerske <svigerske@gams.com>
This is a modified/extended version of trac-to-gitlab from https://github.com/moimael/trac-to-gitlab.
It has been adapted to fit the needs of a specific Trac to GitLab conversion.
Then it has been adapted to fit the needs to another Trac to GitHub conversion.

Copyright © 2013
    Eric van der Vlist <vdv@dyomedea.com>
    Jens Neuhalfen <http://www.neuhalfen.name/>

This sotfware is free software: you can redistribute it and/or modify
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
import warnings
from datetime import datetime
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

# 6-digit hex notation with leading '#' sign (e.g. #FFAABB) or one of the CSS color names (https://developer.mozilla.org/en-US/docs/Web/CSS/color_value#Color_keywords)
labelcolor = {
  'component' : '08517b',
  'priority' : 'ff0000',
  'severity' : 'ee0000',
  'type' : '008080',
  'keyword' : 'eeeeee'
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
keywords_to_labels = config.getboolean('issues', 'keywords_to_labels')
migrate_milestones = config.getboolean('issues', 'migrate_milestones')
add_label = None
if config.has_option('issues', 'add_label'):
    add_label = config.get('issues', 'add_label')

svngit_mapfile = None
if config.has_option('source', 'svngitmap') :
    svngit_mapfile = config.get('source', 'svngitmap')
svngit_map = None

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

skip_line_with_leading_whitespaces = 0
if config.has_option('source', 'skip_line_with_leading_whitespaces') :
    # set this integer in the source section of the configuration file
    # to the number of leading whitespaces that a line must have to
    # be skipped in the function trac2markdown. Zero means that no
    # line is skipped.
    skip_line_with_leading_whitespaces = config.getint('source', 'skip_line_with_leading_whitespaces')


from diskcache import Cache
cache = Cache('trac_cache', size_limit=int(20e9))


#pattern_changeset = r'(?sm)In \[changeset:"([^"/]+?)(?:/[^"]+)?"\]:\n\{\{\{(\n#![^\n]+)?\n(.*?)\n\}\}\}'
pattern_changeset = r'(?sm)In \[changeset:"[0-9]+" ([0-9]+)\]:\n\{\{\{(\n#![^\n]+)?\n(.*?)\n\}\}\}'
matcher_changeset = re.compile(pattern_changeset)

pattern_changeset2 = r'\[changeset:([a-zA-Z0-9]+)\]'
matcher_changeset2 = re.compile(pattern_changeset2)

pattern_svnrev1 = r'(?:\bchangeset *)|(?<=\s)\[([0-9]+)\]'
matcher_svnrev1 = re.compile(pattern_svnrev1)

pattern_svnrev2 = r'\b(?:changeset *)?r([0-9]+)\b'
matcher_svnrev2 = re.compile(pattern_svnrev2)

gh_labels = dict()
gh_user = None

def format_changeset_comment(m):
    if svngit_map is not None and m.group(1) in svngit_map :
        r = 'In ' + svngit_map[m.group(1)][0][:10]
    else :
        if svngit_map is not None :
            print ('  WARNING: svn revision', m.group(1), 'not given in svn to git mapping')
        r = 'In changeset ' + m.group(1)
    r += ':\n> ' + m.group(3).replace('\n', '\n> ')
    return r


def handle_svnrev_reference(m) :
    assert svngit_map is not None
    if m.group(1) in svngit_map :
        return svngit_map[m.group(1)][0][:10]
    else :
        #print '  WARNING: svn revision', m.group(1), 'not given in svn to git mapping'
        return m.group(0)


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
RE_TICKET1 = re.compile(r'[\s]%s/([1-9]\d{0,4})' % trac_url_ticket)
RE_TICKET2 = re.compile(r'\#([1-9]\d{0,4})')
RE_COLOR = re.compile(r'<span style="color: ([a-zA-Z]+)">([a-zA-Z]+)</span>')
RE_RULE = re.compile(r'^[-]{4,}\s*')

RE_GIT_SERVER = re.compile(r'https?://git.sagemath.org/sage.git/tree/src')
RE_TRAC_REPORT = re.compile(r'\[report:([0-9]+)\s*(.*?)\]')

def trac2markdown(text, base_path, conv_help, multilines=default_multilines):
    text = matcher_changeset.sub(format_changeset_comment, text)
    text = matcher_changeset2.sub(r'\1', text)

    if svngit_map is not None :
        text = matcher_svnrev1.sub(handle_svnrev_reference, text)
        text = matcher_svnrev2.sub(handle_svnrev_reference, text)

    # some normalization
    text = re.sub('\r\n', '\n', text)
    text = re.sub(r'(?sm){{{\n#!', r'{{{#!', text)
    text = re.sub(r'\swiki:([a-zA-Z]+)', r' [wiki:\1]', text)

    # inline code snippets
    text = re.sub(r'{{{(.*?)}}}', r'`\1`', text)

    text = re.sub(r'\[\[TOC[^]]*\]\]', '', text)
    text = re.sub(r'(?m)\[\[PageOutline\]\]\s*\n', '', text)
    text = text.replace('[[BR]]', '\n')
    text = text.replace('[[br]]', '\n')

    if multilines:
        text = re.sub(r'^\S[^\n]+([^=-_|])\n([^\s`*0-9#=->-_|])', r'\1 \2', text)

    def convert_heading(level, text):
        """
        Return the given text with converted headings
        """
        def replace(match):
            """
            Return the replacement for the heading
            """
            heading = match.groups()[0]
            # There might be a second item if an anchor is set.
            # We ignore this anchor since it is automatically
            # set it GitHub Markdown.
            return '%s %s' % (('#'*level), heading)

        text = re.sub(r'(?m)^%s\s+([^=]+)[^\n=]*([\#][\w-]*)?$' % ('='*level), replace, text)
        text = re.sub(r'(?m)^%s\s+(.*?)\s+%s[^\n]*([\#][\w-]*)?$' % ('='*level, '='*level), replace, text)
        return text

    for level in [6, 5, 4, 3, 2, 1]:
        text = convert_heading(level, text)

    a = []
    level = 0
    in_td = False
    in_code = False
    in_html = False
    is_table = False
    in_list = False
    list_indents = []
    previous_line = ''
    quote_prefix = ''
    for line in text.split('\n'):
        if skip_line_with_leading_whitespaces:
            if line.startswith(' '*skip_line_with_leading_whitespaces):
                is_table = False
                continue

        # cut quote prefix
        if line.startswith(quote_prefix):
            line = line[len(quote_prefix):]
        else:
            line = '\n' + line
            quote_prefix = ''

        if previous_line:
            line = previous_line + line
            previous_line = ''

        if line.startswith('{{{') and in_code:
            level += 1
        elif line.startswith('{{{#!td'):
            in_td = True
            in_td_level = level
            line =  re.sub(r'{{{#!td', r'OPENING__PROCESSOR__TD', line)
            level += 1
        elif line.startswith('{{{#!html') and not (in_code or in_html):
            in_html = True
            in_html_level = level
            line =  re.sub(r'{{{#!html', r'', line)
            level += 1
        elif line.startswith('{{{#!') and not (in_code or in_html):  # code: python, diff, ...
            in_code = True
            in_code_level = level
            if a and a[-1].strip():
                line = '\n' + line
            line =  re.sub(r'{{{#!([^\s]+)', r'OPENING__PROCESSOR__CODE\1', line)
            level += 1
        elif line.startswith('{{{') and not (in_code or in_html):
            in_code = True
            in_code_level = level
            if line.rstrip() == '{{{':
                if a and a[-1].strip():
                    line = '\n' + line
                line = line.replace('{{{', 'OPENING__PROCESSOR__CODE', 1)
            else:
                if a and a[-1].strip():
                    line = '\n' + line
                line = line.replace('{{{', 'OPENING__PROCESSOR__CODE' + '\n', 1)
            level += 1
        elif line.rstrip() == '}}}':
            level -= 1
            if in_td and in_td_level == level:
                in_td = False
                line =  re.sub(r'}}}', r'CLOSING__PROCESSOR__TD', line)
            elif in_html and in_html_level == level:
                in_html = False
                line =  re.sub(r'}}}', r'', line)
            elif in_code and in_code_level == level:
                in_code = False
                line =  re.sub(r'}}}', r'CLOSING__PROCESSOR__CODE', line)

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
                    converted_part = re.sub(r'(?<=\s)((?:[A-Z][a-z0-9]+){2,})(?=[\s\.\,\:\;\?\!])', conv_help.camelcase_wiki_link, line[start:end])
                    converted_part = re.sub(r'(?<=\s)((?:[A-Z][a-z0-9]+){2,})$', conv_help.camelcase_wiki_link, converted_part)  # CamelCase wiki link at end
                    new_line += converted_part

                    start = end
            line = new_line

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

            line = RE_TICKET1.sub(r' #\1', line) # replace global ticket references
            line = RE_TICKET2.sub(conv_help.ticket_link, line)
            line = line.replace('@', r'`@`')

            if RE_RULE.match(line):
                if not a or not a[-1].strip():
                    line = '---'
                else:
                    line = '\n---'

            line = re.sub(r'\!(([A-Z][a-z0-9]+){2,})', r'\1', line)  # no CamelCase wiki link because of leading "!"

            # convert a trac table to a github table
            if line.startswith('||'):
                if not is_table:  # header row
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
                    is_table = True
                # The wiki markup allows the alignment directives to be specified on a cell-by-cell
                # basis. This is used in many examples. AFAIK this can't be properly translated into
                # the GitHub markdown as it only allows to align statements column by column.
                line = line.replace('||=', '||')  # ignore cellwise align instructions
                line = line.replace('=||', '||')  # ignore cellwise align instructions
                line = line.replace('||', '|')
            else:
                is_table = False

            # lists
            if in_list:
                if line.strip():
                    indent = re.search('[^\s]', line).start()
                    if indent > list_leading_spaces:
                        line = line[list_leading_spaces:]

                        # nudge slightly-malformed paragraph in list for right indent -- fingers crossed
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

        for l in line.split('\n'):
            a.append(quote_prefix + l)

    # Deal with a github table if the corresponding trac table contains td processors
    b = []
    table = []
    in_table = False
    in_block = False
    in_td = False
    previous_line = ''
    for line in a:
        if previous_line:
            line = previous_line + line
            previous_line = ''
        if line == '|\\' or line == '| \\':  #  ||\ or || \ in trac
            in_block = True
            block = []
        elif line.startswith('|'):
            if in_block:  # terminate a block
                table.append('|' + 'NEW__LINE'.join(block) +'|')
                in_block = False
            else:
                if line.endswith('|\\'):
                    line = line[:-2]
                    previous_line = line
                elif line.endswith('| \\'):
                    line = line[:-3]
                    previous_line = line
                elif line == '|':
                    previous_line = ''
                else:
                    table.append(line)
            in_table = True
        elif line:
            if in_block:
                if line.startswith('OPENING__PROCESSOR__TD'):
                    in_td = True
                    if len(block) > 1:
                        block.append('|')
                elif line.startswith('CLOSING__PROCESSOR__TD'):
                    in_td = False
                block.append(line)
            else:
                line = re.sub('SEPARATOR__BETWEEN__BRACKETS', r'|', line)
                b.append(line)
        else:
            if in_block and in_td:
                block.append(line)
            elif in_table:  # terminate a table
                if in_block:  # terminate a block
                    table.append(' | ' + 'NEW__LINE'.join(block) +'|')
                    in_block = False

                table_text = '\n'.join(table)
                if 'OPENING__PROCESSOR__TD' in table_text:
                    html = markdown.markdown(table_text, extensions=[TableExtension(use_align_attribute=True)])
                    html = re.sub('OPENING__PROCESSOR__TD', r'<div align="left">', html)
                    html = re.sub('CLOSING__PROCESSOR__TD', r'</div>', html)
                else:
                    html = table_text
                html = html.replace('NEW__LINE', '\n')
                html = html.replace('SEPARATOR__BETWEEN__BRACKETS', r'\|')
                b += html.split('\n')  # process table
                table = []
                in_table = False
            else:
                line = line.replace('SEPARATOR__BETWEEN__BRACKETS', r'|')
                b.append(line)

    text = '\n'.join(b)

    # remove artifacts
    text = text.replace('OPENING__PROCESSOR__CODE', '```')
    text = text.replace('CLOSING__PROCESSOR__CODE', '```')
    text = text.replace('OPENING__LEFT__BRACKET', '[')
    text = text.replace('CLOSING__RIGHT__BRACKET', ']')

    # final rewriting
    text = RE_COLOR.sub(r'$\\textcolor{\1}{\\text{\2}}$', text)
    text = RE_GIT_SERVER.sub(r'https://github.com/sagemath/sagetrac-mirror/blob/master/src', text)
    text = RE_TRAC_REPORT.sub(r'[This is the Trac report of id \1 that was inherited from the migration](https://trac.sagemath.org/report/\1)', text)

    return text


def convert_xmlrpc_datetime(dt):
    # datetime.strptime(str(dt), "%Y%m%dT%X").isoformat() + "Z"
    return datetime.strptime(str(dt), "%Y%m%dT%H:%M:%S")

def convert_trac_datetime(dt):
    return datetime.strptime(str(dt), "%Y-%m-%d %H:%M:%S")

def maptickettype(tickettype):
    "Return GitHub label corresponding to Trac ``tickettype``"
    if tickettype == 'defect':
        return 'bug'
    # if tickettype == 'clarification':
    #     return 'question'
    # if tickettype == 'task':
    #     return 'enhancement'
    if tickettype == 'PLEASE CHANGE':
        return None
    #return tickettype.lower()
    return None

def mapcomponent(component):
    "Return GitHub label corresponding to Trac ``component``"
    if component == 'PLEASE CHANGE':
        return None
    # Prefix it with "component: " so that they show up as one group in the GitHub dropdown list
    return f'component: {component}'

default_priority = 'major'
def mappriority(priority):
    "Return GitHub label corresponding to Trac ``priority``"
    if priority == default_priority:
        return None
    return priority

def mapstatus(status):
    if status in ['new', 'assigned', 'analyzed', 'reopened', 'needs_review',
                  'needs_work', 'needs_info', 'needs_info_new', 'positive_review']:
        return 'open'
    elif status in ['closed'] :
        return 'closed'
    else:
        warnings.warn("unknown ticket status: " + status)
        return 'open'

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
    print ('Create label %s with color #%s' % (labelname, labelcolor));
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

    print("  created issue " + str(gh_issue))
    sleep(sleep_after_request)

    return gh_issue

def gh_comment_issue(dest, issue, comment, src_ticket_id) :
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
            note = 'Attachment [%s](%s) by %s created at %s' % (filename, attachment_export_url + 'ticket' + str(src_ticket_id) + '/' + filename, comment['user'], comment['created_at'])
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

    if dest is None : return

    if not github:
        user_url = gh_user_url(dest, comment['user'])
        if user_url:
           comment['user'] = user_url

    issue.create_comment(note, **comment)
    sleep(sleep_after_request)

def gh_update_issue_property(dest, issue, key, val, oldval=None, **kwds):
    if dest is None : return

    if key == 'labels' :
        labels = [gh_labels[label.lower()] for label in val if label]
        issue.set_labels(*labels)
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
        issue.edit(body = val)
    elif key == 'title' :
        issue.edit(title = val)
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

unmapped_users = set()

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
    unmapped_users.add(origname)
    return origname

def gh_user_url(dest, username):
    if username.startswith('@'):
        return f'https://github.com/{username[1:]}'
    if re.fullmatch('[-A-Za-z._0-9]+', username):
        # heuristic pattern for valid Trac account name (not an email address or junk)
        # Use this URL as the id (this is current best guess what a mannequin user would look like)
        return f'https://trac.sagemath.org/admin/accounts/users/{username}'
    return None

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
    milestone_map = {}

    conv_help = ConversionHelper(source)

    if migrate_milestones:
        for milestone_name in get_all_milestones(source):
            milestone = get_milestone(source, milestone_name)
            title = milestone.pop('name')
            print("Creating milestone " + title)
            new_milestone = {
                'description' : trac2markdown(milestone.pop('description'), '/milestones/', conv_help, False),
                'title' : title,
                'state' : 'open' if str(milestone.pop('completed')) == '0'  else 'closed'
            }
            due = milestone.pop('due')
            if due:
                new_milestone['due_date'] = convert_xmlrpc_datetime(due)
            if milestone:
                print(f"Discarded milestone data: {milestone}")
            milestone_map[milestone_name] = gh_create_milestone(dest, new_milestone)
            print(milestone_map[milestone_name])

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

        print("\n\n## Migrate ticket #%s (%d changes): %s" % (src_ticket_id, len(changelog), src_ticket_data['summary'][:30]))

        def issue_description(src_ticket_data):
            description_pre = ""
            description_post = ""

            owner = src_ticket_data.pop('owner', None)
            if owner:
                description_post += '\n\nAssignee: ' + gh_username(dest, owner)

            version = src_ticket_data.pop('version', None)
            if version is not None and version != 'trunk' :
                description_post += '\n\nVersion: ' + version

            # subscribe persons in cc
            cc = src_ticket_data.pop('cc', '').lower()
            ccstr = ''
            for person in cc.replace(';', ',').split(',') :
                person = person.strip()
                if person == '' : continue
                person = gh_username(dest, person)
                ccstr += ' ' + person
            if ccstr != '' :
                description_post += '\n\nCC: ' + ccstr

            if not keywords_to_labels:
                keywords = src_ticket_data.pop('keywords', '')
                if keywords:
                    description_post += '\n\nKeywords: ' + keywords

            description = src_ticket_data.pop('description', '')

            for field, value in src_ticket_data.items():
                if (not field.startswith('_')
                    and field not in ['status', 'changetime', 'time']
                    and value and value not in ['N/A', 'tba']):
                    description_post += f'\n\n{field.title()}: {value}'

            description_post += f'\n\nIssue created by migration from {trac_url_ticket}/{src_ticket_id}\n\n'

            return description_pre + trac2markdown(description, '/issues/', conv_help, False) + description_post

        # get original component, owner
        # src_ticket_data['component'] is the component after all changes, but for creating the issue we want the component
        # that was set when the issue was created; we should get this from the first changelog entry that changed a component
        # ... and similar for other attributes
        first_old_values = {}
        for change in changelog :
            time, author, field, oldvalue, newvalue, permanent = change
            if field not in first_old_values:
                if field not in ['milestone', 'cc', 'reporter']:
                    if isinstance(oldvalue, str):
                        oldvalue = oldvalue.strip()
                    first_old_values[field] = oldvalue

        # If no change changed a certain attribute, then that attribute is given by ticket data
        # (When writing migration archives, this is true unconditionally.)
        if github:
            src_ticket_data.update(first_old_values)

        # Process src_ticket_data and remove (using pop) attributes that are processed already.
        # issue_description dumps everything that has not been processed in the description.

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
            labels.append(mappriority(priority))
            gh_ensure_label(dest, priority, labelcolor['priority'])

        severity = src_ticket_data.pop('severity', 'normal')
        if severity != 'normal' :
            labels.append(severity)
            gh_ensure_label(dest, severity, labelcolor['severity'])

        tickettype = maptickettype(src_ticket_data.pop('type', None))
        if tickettype is not None :
            labels.append(tickettype)
            gh_ensure_label(dest, tickettype, labelcolor['type'])

        if keywords_to_labels:
            keywords = src_ticket_data.pop('keywords', '')
            if keywords:
                for keyword in keywords.split(','):
                    labels.append(keyword.strip())
                    gh_ensure_label(dest, keyword.strip(), labelcolor['keyword'])

        # collect all parameters
        issue_data = {
            'title' : src_ticket_data.pop('summary'),
            'labels' : labels,
            #'assignee' : assignee,
        }
        if not github:
            issue_data['user'] = gh_username(dest, src_ticket_data.pop('reporter'))
            issue_data['created_at'] = convert_xmlrpc_datetime(time_created)
            issue_data['number'] = int(src_ticket_id)
            # Find closed_at
            for time, author, change_type, oldvalue, newvalue, permanent in reversed(changelog):
                if change_type == 'status' and mapstatus(newvalue) == 'closed':
                    issue_data['closed_at'] = convert_xmlrpc_datetime(time)
                    break

        milestone = src_ticket_data.pop('milestone', None)
        if milestone and milestone in milestone_map:
            issue_data['milestone'] = milestone_map[milestone]

        issue_data['description'] = issue_description(src_ticket_data)

        issue = gh_create_issue(dest, issue_data)

        if github:
            status = src_ticket_data.pop('status')
            if status in ['closed']:
                # sometimes a ticket is already closed at creation, so close issue
                gh_update_issue_property(dest, issue, 'state', 'closed')
        else:
            src_ticket_data.update(first_old_values)
            status = src_ticket_data.pop('status')
        issue_state = mapstatus(status)

        attachment = None
        for change in changelog:
            time, author, change_type, oldvalue, newvalue, permanent = change
            change_time = str(convert_xmlrpc_datetime(time))
            #print(change)
            print(("  %s by %s (%s -> %s)" % (change_type, author, str(oldvalue)[:40].replace("\n", " "), str(newvalue)[:40].replace("\n", " "))).encode("ascii", "replace"))
            #assert attachment is None or change_type == "comment", "an attachment must be followed by a comment"
            if author in ['anonymous', 'Draftmen888'] :
                print ("  SKIPPING CHANGE BY", author)
                continue
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
                desc = newvalue.strip();
                if desc == '' and attachment is None :
                    # empty description and not description of attachment
                    continue
                comment_data['note'] = trac2markdown(desc, '/issues/', conv_help, False)

                if attachment is not None :
                    comment_data['attachment_name'] = attachment[4]  # name of attachment
                    comment_data['attachment'] = get_ticket_attachment(source, src_ticket_id, attachment[4]).data
                    attachment = None
                gh_comment_issue(dest, issue, comment_data, src_ticket_id)
            elif change_type.startswith("_comment") :
                # this is an old version of a comment, which has been edited later (given in previous change),
                # e.g., see http://localhost:8080/ticket/3431#comment:9 http://localhost:8080/ticket/3400#comment:14
                # we will forget about these old versions and only keep the latest one
                pass
            elif change_type == "status" :
                newstate = mapstatus(newvalue)
                if newstate == 'open':
                    # mapstatus maps the various statuses we have in trac
                    # to just 2 statuses in gitlab/github (open or closed),
                    # so to avoid a loss of information, we add a comment.
                    comment_data['note'] = 'Changing status from ' + oldvalue + ' to ' + newvalue + '.'
                    gh_comment_issue(dest, issue, comment_data, src_ticket_id)
                if issue_state != newstate :
                    issue_state = newstate
                    gh_update_issue_property(dest, issue, 'state', newstate, **event_data)

            elif change_type == "resolution" :
                if oldvalue != '' :
                    desc = "Resolution changed from %s to %s" % (oldvalue, newvalue)
                else :
                    desc = "Resolution: " + newvalue
                comment_data['note'] = desc
                gh_comment_issue(dest, issue, comment_data, src_ticket_id)
            elif change_type == "component" :
                if oldvalue != '' :
                    with contextlib.suppress(ValueError):
                        label = mapcomponent(oldvalue)
                        if label:
                            labels.remove(label)
                label = mapcomponent(newvalue)
                if label:
                    labels.append(label)
                    gh_ensure_label(dest, label, labelcolor['component'])
                comment_data['note'] = 'Changing component from ' + oldvalue + ' to ' + newvalue + '.'
                gh_comment_issue(dest, issue, comment_data, src_ticket_id)
                gh_update_issue_property(dest, issue, 'labels', labels)
            elif change_type == "owner" :
                if oldvalue != '' and newvalue != '':
                    comment_data['note'] = 'Changing assignee from ' + gh_username(dest, oldvalue) + ' to ' + gh_username(dest, newvalue) + '.'
                elif oldvalue == '':
                    comment_data['note'] = 'Set assignee to ' + gh_username(dest, newvalue) + '.'
                else:
                    comment_data['note'] = 'Remove assignee ' + gh_username(dest, oldvalue) + '.'
                gh_comment_issue(dest, issue, comment_data, src_ticket_id)

                # if newvalue != oldvalue :
                #     assignee = gh_username(dest, newvalue)
                #     if not assignee.startswith('@') :
                #         assignee = GithubObject.NotSet
                #     gh_update_issue_property(dest, issue, 'assignee', assignee)
            elif change_type == "version" :
                if oldvalue != '' :
                    desc = "Version changed from %s to %s" % (oldvalue, newvalue)
                else :
                    desc = "Version: " + newvalue
                comment_data['note'] = desc
                gh_comment_issue(dest, issue, comment_data, src_ticket_id)
            elif change_type == "milestone" :
                oldvalue=issue_data.get('milestone', GithubObject.NotSet)
                if newvalue != '' and newvalue in milestone_map:
                    issue_data['milestone'] = milestone_map[newvalue]
                elif 'milestone' in issue_data :
                    del issue_data['milestone']
                gh_update_issue_property(dest, issue, 'milestone',
                                         issue_data.get('milestone', GithubObject.NotSet),
                                         oldval=oldvalue, **event_data)
            elif change_type == "cc" :
                pass  # we handle only the final list of CCs (above)
            elif change_type == "type" :
                if oldvalue != '' :
                    oldtype = maptickettype(oldvalue)
                    with contextlib.suppress(ValueError):
                        labels.remove(oldtype)
                newtype = maptickettype(newvalue)
                labels.append(newtype)
                gh_ensure_label(dest, newtype, labelcolor['type'])
                comment_data['note'] = 'Changing type from ' + oldvalue + ' to ' + newvalue + '.'
                gh_comment_issue(dest, issue, comment_data, src_ticket_id)
                gh_update_issue_property(dest, issue, 'labels', labels)
            elif change_type == "description" :
                issue_data['description'] = issue_description(src_ticket_data) + '\n\n(changed by ' + user + ' at ' + change_time + ')'
                gh_update_issue_property(dest, issue, 'description', issue_data['description'])
            elif change_type == "summary" :
                issue_data['title'] = newvalue
                gh_update_issue_property(dest, issue, 'title', issue_data['title'])
            elif change_type == "priority" :
                if oldvalue != '' and oldvalue != default_priority:
                    with contextlib.suppress(ValueError):
                        labels.remove(mappriority(oldvalue))
                if newvalue != '' and newvalue != default_priority:
                    label = mappriority(newvalue)
                    labels.append(label)
                    gh_ensure_label(dest, label, labelcolor['priority'])
                    comment_data['note'] = 'Changing priority from ' + oldvalue + ' to ' + newvalue + '.'
                    gh_comment_issue(dest, issue, comment_data, src_ticket_id)
                gh_update_issue_property(dest, issue, 'labels', labels)
            elif change_type == "severity" :
                if oldvalue != '' and oldvalue != 'normal' :
                    with contextlib.suppress(ValueError):
                        labels.remove(oldvalue)
                if newvalue != '' and newvalue != 'normal' :
                    labels.append(newvalue)
                    gh_ensure_label(dest, newvalue, labelcolor['severity'])
                    comment_data['note'] = 'Changing severity from ' + oldvalue + ' to ' + newvalue + '.'
                    gh_comment_issue(dest, issue, comment_data, src_ticket_id)
                gh_update_issue_property(dest, issue, 'labels', labels)
            elif change_type == "keywords" :
                if keywords_to_labels :
                    oldkeywords = oldvalue.split(',')
                    newkeywords = newvalue.split(',')
                    for keyword in oldkeywords :
                        keyword = keyword.strip()
                        if keyword != ''  :
                            with contextlib.suppress(ValueError):
                                labels.remove(keyword)
                    for keyword in newkeywords :
                        keyword = keyword.strip()
                        if keyword != '' :
                            labels.append(keyword)
                            gh_ensure_label(dest, keyword, labelcolor['keyword'])
                    oldkeywords = [ kw.strip() for kw in oldkeywords ]
                    newkeywords = [ kw.strip() for kw in newkeywords ]
                    comment_data['note'] = 'Changing keywords from "' + ','.join(oldkeywords) + '" to "' + ','.join(newkeywords) + '".'
                    gh_comment_issue(dest, issue, comment_data, src_ticket_id)
                    gh_update_issue_property(dest, issue, 'labels', labels)
                else :
                    comment_data['note'] = 'Changing keywords from "' + oldvalue + '" to "' + newvalue + '".'
                    gh_comment_issue(dest, issue, comment_data, src_ticket_id)
            elif change_type in ["commit",  "upstream",  "stopgaps", "branch", "reviewer", "work_issues", "merged", "dependencies", "author", "changetime", "reporter"] :
                print("TODO Change type: ", change_type)
            else:
                warnings.warn("Unknown change type " + change_type)
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

    for pagename in source.wiki.getAllPages():
        info = source.wiki.getPageInfo(pagename)
        if info['author'] in exclude_authors:
            continue

        page = source.wiki.getPage(pagename)
        print ("Migrate Wikipage", pagename)

        # Github wiki does not have folder structure
        gh_pagename = ' '.join(pagename.split('/'))

        conv_help.set_attachment_path(gh_pagename)
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

    def set_attachment_path(self, attachment_path):
        """
        Set the attachment_path for the wiki_image method.
        """
        self._attachment_path = attachment_path

    def ticket_link(self, match):
        """
        Return a formatted string that replaces the match object found by re
        in the case of a Trac ticket link.
        """
        ticket = match.groups()[0]
        if self._keep_trac_ticket_references:
            # as long as the ticket themselfs have not been migrated they should reference to the original place
            return r'[#%s](%s/%s)' % (ticket, trac_url_ticket, ticket)
        else:
            # leave them as is
            return r'#%s' % ticket

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


if __name__ == "__main__":
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
            print(dest.url)
            sleep_after_request = 0

    if svngit_mapfile is not None :
        svngit_map = dict()
        for line in open(svngit_mapfile, 'r') :
            l = line.split()
            if len(l) <= 1 :
                continue
            assert len(l) >= 2, line
            githash = l[0]
            svnrev = l[1][1:]
            svnbranch = l[2] if len(l) > 2 else 'trunk'
            #print l[1], l[0]
            # if already have a svn revision entry from branch trunk, then ignore others
            if svnrev in svngit_map and svngit_map[svnrev][1] == 'trunk' :
                continue
            svngit_map[svnrev] = [githash, svnbranch]

    try:
        if must_convert_issues:
            convert_issues(source, dest, only_issues = only_issues, blacklist_issues = blacklist_issues)

        if must_convert_wiki:
            convert_wiki(source, dest)
    finally:
        print(f'Unmapped users: {sorted(unmapped_users)}')
