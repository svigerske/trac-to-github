#! /bin/sh
VERSION=$(git describe --always)
cd wiki && git add -A && git commit -m "Update using trac-to-github @ $VERSION"
