# Read the file sage_trac_users.xml (screenscraped from Trac admin interface)

from contributors_from_sage_developer_map import (
    sage_contributors_from_xmldoc,
    trac_to_github as _trac_to_github,
    trac_full_names as _trac_full_names
)

import pprint

from xml.dom.minidom import parse

def sage_contributors():
    with open('sage_trac_users.xml', 'r') as f:
        yield from sage_contributors_from_xmldoc(parse(f))


# API
def trac_to_github():
    return _trac_to_github(sage_contributors())


# API
def trac_full_names():
    return _trac_full_names(sage_contributors())


if __name__ == "__main__":

    usernames = trac_to_github()
    pprint.pp(usernames)
    pprint.pp(trac_full_names())
