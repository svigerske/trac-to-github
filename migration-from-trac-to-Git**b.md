See also: https://trac.sagemath.org/ticket/30363


# Proposed workflow on GitHub (minimal changes to existing Trac workflow)

- One time action: **Instead of adding a git remote named `trac`**:
  
  - [Create a GitHub fork](https://docs.github.com/en/get-started/quickstart/fork-a-repo#forking-a-repository) of the main repository https://github.com/sagemath/sage
  - Add a remote named `github-USERNAME` for your fork (the URL can be copied from there)
    ```
    git remote add github-USERNAME https://github.com/USERNAME/sage.git
    ```

- For reporting a bug, planning an enhancement, describing a project, **instead of opening a Trac ticket**:

  - [Open an Issue on GitHub](https://docs.github.com/en/issues). Preview of Issues (converted from Trac): https://github.com/dimpase/trac_to_gh/issues?q=
  - Trac ticket box attributes are mapped as follows:
    - "Type" ("defect", "enhancement", "task") is mapped to a "Label"
    - "Component" ("basic arithmetic", ") are mapped to "Labels"
    - "Priority" ("major"/"minor"/"critical") is mapped to "Labels"
    - "Keywords" can be mapped to "Labels"
    - "Cc": use `@USERNAME` either in the Issue description or in any comment
    - "Branch"/"Commit"/"Authors"/"Reviewers"/"Work Issues": via Pull Requests (PR), see below
    - "Report Upstream" is replaced by [automatic cross references between Issues/PRs in different repos](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/autolinked-references-and-urls#issues-and-pull-requests)
    - "Milestone = duplicate/invalid/wontfix" is replaced by [marking as duplicate](https://docs.github.com/en/issues/tracking-your-work-with-issues/marking-issues-or-pull-requests-as-a-duplicate) or closing with a comment

- For contributing a change that does not address an existing open Issue, **instead of opening a Trac ticket and pushing a git branch to it**:
  - Push the branch to the remote named `github-USERNAME`
  - A git message will provide a URL for opening a Pull Request (PR)
  - Open the PR
  - If it is not ready for review, [mark the PR as a "Draft"](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/changing-the-stage-of-a-pull-request)

- For contributing a change that addresses an existing open Issue, **instead of pushing a git branch to a Trac ticket**:
  - same as above
  - [use `Fixes #ISSUENUMBER` to link to an existing issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue); this will auto-close the linked Issue when the PR is merged.

- For finding PRs that are waiting for review, **instead of using Trac ticket reports**:
  - [filter PRs by review status](https://docs.github.com/en/issues/tracking-your-work-with-issues/filtering-and-searching-issues-and-pull-requests#filtering-pull-requests-by-review-status)

- For reviewing a change:
  - **instead of looking at the patchbot**, use the [Checks on GitHub Actions](https://trac.sagemath.org/wiki/ReleaseTours/sage-9.6#BuildsandchecksofticketbranchesonGitHubActions), which are already available on Trac since the Sage 9.6 series; the status of the check runs will be clearer on GitHub [than on Trac](https://trac.sagemath.org/ticket/33818) 
  - **instead of copy-pasting parts of the diff of a branch to a comment**, use [pull request reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews)

- Unchanged: Release Manager @vbraun merges positively reviewed tickets into his branch https://github.com/vbraun/sage
- Unchanged: To make a beta or stable release, Release Manager merges (fast-forward) his branch into the `develop` branch and creates a tag
- Unchanged: To make a stable release, Release Manager merges (fast-forward) the `develop` branch into the `master` branch.


