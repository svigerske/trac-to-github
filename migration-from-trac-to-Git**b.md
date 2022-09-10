See also: https://trac.sagemath.org/ticket/30363


# Proposed workflow on GitHub (minimal changes to existing Trac workflow)

- One time action: Instead of adding a git remote named `trac`:
  
  - Create a GitHub fork and copy its URL
  - Add a remote named `github-USERNAME`

- Instead of opening a Trac ticket:

  - Open an Issue on GitHub. Preview of Issues (converted from Trac): https://github.com/dimpase/trac_to_gh/issues?q=
  - Trac "Components" (such as "basic arithmetic") are mapped to "Labels"
  - "Bug"/"Enhancement" is mapped to "Labels"
  - Priority ("major"/"minor"/"critical") is mapped to "Labels"
  - Instead of Cc:, use @

- Instead of pushing a git branch to a Trac ticket:

  - Push the branch to the remote named `github-USERNAME`
  - A git message will provide a URL for opening a PR
  - Open the PR, possibly marking it as "draft"; use `Fixes #ISSUENUMBER` to link to an existing issue

- Unchanged: Release Manager @vbraun merges positively reviewed tickets into his branch https://github.com/vbraun/sage
- Unchanged: To make a beta or stable release, Release Manager merges (fast-forward) his branch into the `develop` branch and creates a tag
- Unchanged: To make a stable release, Release Manager merges (fast-forward) the `develop` branch into the `master` branch.


