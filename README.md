What
=====

This script migrates milestones, issues/tickets, and wiki pages from Trac to GitHub.

The script has its origin at https://github.com/moimael/trac-to-gitlab,
which then was [extended to suite a specific use case of SVN+Trac to GitLab migration](https://www.gams.com/~stefan/svn2git/).
Next, GitLab specific code was removed, and a migration to GitHub was added.

In its present form, it is used for the migration of SageMath from
https://trac.sagemath.org/ to GitHub. This migration is described in more detail in
https://trac.sagemath.org/ticket/30363

Why
===

[docs/Github-vs-Gitlab-vs-trac.md](docs/Github-vs-Gitlab-vs-trac.md) compares
[Github](https://github.com/) and [Trac](https://trac.sagemath.org/),
focusing on the specific differences that are important to the SageMath
community.

How
====

Migrating a Trac project to GitHub is a relatively complex process involving four steps:

 * Create a new project
 * Migrate the repository
 * Migrate issues and milestones
 * Migrate wiki pages

This script takes care of the third and fourth bullet points.

Usage:

  1. copy ```migrate.cfg.example``` to ```migrate.cfg```
  2. configure the values
  3. run (```./migrate.py```). Make sure you test it on a test project prior, if you run it twice against the same project you will get duplicated issues.

See [docs/Migration-Trac-to-Github.md](docs/Migration-Trac-to-Github.md) for details of the migration process
and a proposed workflow on GitHub (with transition guide from Trac for developers).

Features
--------
 * Title, description, comments to issues are copied over
 * Component, issue type, priority, severity, and keywords are converted to labels
 * Version and CC are added to the issue description
 * Resolution is added as comment
 * Issue text attachments are uploaded as Gist (GitHub doesn't allow to attach files to issues via the GitHub API)
   or all issue attachments are exported to files
 * Wiki pages including attachments are exported into files that can be
   added to the GitHub project wiki repository.

Missing
-------
 * Wiki pages could automatically be added to a projects wiki repository.
 * History on wiki pages is not kept.




License
=======

LGPL license version 3.0.

Requirements
==============

 * Python 3; requests, [PyGithub](https://github.com/PyGithub/PyGithub),
   see ```requirements.txt```
 * Trac with [XML-RPC plugin](http://trac-hacks.org/wiki/XmlRpcPlugin) enabled
