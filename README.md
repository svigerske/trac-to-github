What
=====

This script migrates milestones, issues, and wiki pages from Trac to GitHub.

The script has its origin at https://github.com/moimael/trac-to-gitlab,
which then has been [extended to suite a specific use case of SVN+Trac to GitLab migration](https://www.gams.com/~stefan/svn2git/).
Next, GitLab specific code has been removed and a migration to GitHub
has been added.

Features
--------
 * Title, description, comments to issues are copied over
 * Component, issue type, priority, severity, and keywords are converted to labels
 * Version and CC are added to the issue description
 * Resolution is added as comment
 * Text attachments are uploaded as Gist (GitHub doesn't allow to attach files to issues via the GitHub API)
   or all attachments are exported to files
 * References to SVN commits can be replaced by references to Githashes.
 * Wiki pages are exported in a form that they can be uploaded to GitHub.

Missing
-------
 * Wiki pages could automatically be added to a projects wiki repository.
 * History on wiki pages is not kept.


How
====

Migrating a Trac project to GitHub is a relatively complex process involving four steps:

 * Create a new project
 * Migrate the repository
 * Migrate issues and milestones
 * Migrate wiki pages

This script takes care of the third bullet point.

Usage:

  1. copy ```migrate.cfg.example``` to ```migrate.cfg```
  2. configure the values
  3. run (```./migrate.py```). Make sure you test it on a test project prior, if you run it twice against the same project you will get duplicated issues.


License
=======

LGPL license version 3.0.

Requirements
==============

 * Python 2 with xmlrpclib, requests, [PyGithub](https://github.com/PyGithub/PyGithub)
 * Trac with [XML-RPC plugin](http://trac-hacks.org/wiki/XmlRpcPlugin) enabled
