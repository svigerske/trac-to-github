# Adapted from scripts/geocode.py

import certifi
import urllib3
import pprint

from xml.dom.minidom import parseString

http = urllib3.PoolManager(
    cert_reqs='CERT_REQUIRED',
    ca_certs=certifi.where()
)

ack = parseString(http.request('GET', 'https://raw.githubusercontent.com/sagemath/website/master/conf/contributors.xml').data.decode('utf-8'))

names = set()
usernames = set()

for c in ack.getElementsByTagName("contributors")[0].childNodes:
    if c.nodeType != ack.ELEMENT_NODE:
        continue
    if c.tagName != "contributor":
        continue
    name = c.getAttribute("name")
    if name.strip():
        names.add(name.strip())
    altnames = c.getAttribute("altnames")
    names.update(n.strip() for n in altnames.split(',') if n.strip())
    trac = c.getAttribute("trac")
    usernames.update(t.strip() for t in trac.split(',') if t.strip())

changelog_contributors = http.request('GET', 'https://raw.githubusercontent.com/sagemath/sage-changelogs/master/merger/contributors/9.7').data.decode('utf-8')

def last_name(n):
    parts = n.split()
    if parts:
        return parts[-1]
    return ""

missing_names = [n
                 for n in changelog_contributors.split('\n')
                 if n and n not in names and n not in usernames]
missing_names.sort(key=last_name)
for n in missing_names:
    print(f'<contributor\n name="{n}"/>')
