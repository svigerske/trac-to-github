See also: https://trac.sagemath.org/ticket/30363


# Proposed workflow on GitHub (with transition guide from Trac)

- One time action: **Instead of adding a git remote named `trac`**:
  
  - [Create your personal GitHub fork](https://docs.github.com/en/get-started/quickstart/fork-a-repo#forking-a-repository) of the main repository https://github.com/sagemath/sage - this will become a repository in https://github.com/USERNAME
  - (Optional) generate ssh keypair, or use an already existing one, and upload the public key to your GitHub account settings
  - If you already have a clone of a Sage repository on your computer:
    - Check your current git remote repositories:
      ```
      git remote -v
      ```
    - If you already have the main Sage repository (https://github.com/sagemath/sage) as a remote, and its name is not `upstream`, rename it to `upstream` using `git remote rename OLD-NAME upstream`
    - Otherwise, add a new remote:
      ```
      git remote add upstream https://github.com/sagemath/sage.git
      ```
    - Alternatively, use ssh access with your ssh keypair - see (Optional) above:
      ```
      git remote add upstream git@github.com:sagemath/sage.git
      ```
    - If you already have a remote named `origin` and it is not your personal fork, rename this remote to something else using `git remote rename origin MY-OLD-ORIGIN`
    - Finally, add your fork as a remote via (the URL can be copied from there)
      ```
      git remote add origin https://github.com/USERNAME/sage.git
      ```
    - Alternatvively, with ssh access (see above):
      ```
      git remote add origin git@github.com:USERNAME/sage.git
      ``` 
  - Otherwise (fresh start):
    - [Clone the forked repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#cloning-your-forked-repository),
      and do one of the following, depending on the access type (https vs ssh)
      ```
      git clone https://github.com/USERNAME/sage.git   # https
      git clone git@github.com:USERNAME/sage.git       # ssh
      ```
      This will link your fork as the `origin` remote in the local git.
    - [Configure git to sync your fork with the main Sage repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#configuring-git-to-sync-your-fork-with-the-original-repository), and do one of the following, depending on the access type (https vs ssh):
      ```
      git remote add upstream https://github.com/sagemath/sage.git   # https
      git remote add upstream git@github.com:sagemath/sage.git       # ssh
      ```
  - (Of course, you can give arbitrary names to your git remotes, but `origin` and `upstream` are the established defaults, which will make it easier to use tools such as the GitHub command-line tools.)

- For reporting a bug, planning an enhancement, describing a project, **instead of opening a Trac ticket**:

  - [Open an Issue on GitHub](https://docs.github.com/en/issues). Preview of Issues (converted from Trac): https://github.com/sagemath/trac_to_gh/issues?q=
  - Trac ticket box attributes are mapped as follows:
    - "Type" ("defect", "enhancement", "task") is mapped to a "Label" with prefix `t:`, e.g., `t: bug`
    - "Component" ("basic arithmetic", "linear algebra", "geometry", ...) are mapped to "Labels" with prefix `c: `
    - "Priority" ("major"/"minor"/"critical") is mapped to "Labels" with prefix `p: `
    - "Keywords" can be mapped to "Labels"
    - "Cc": use `@USERNAME` either in the Issue description or in any comment. Regular developers who would like to get notified automatically when a PR touches a particular part of the sage code can add themselves as a [Code Owner](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).
    - "Branch"/"Commit"/"Authors"/"Reviewers"/"Work Issues": via Pull Requests (PR), see below
    - "Report Upstream" is replaced by [automatic cross references between Issues/PRs in different repos](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/autolinked-references-and-urls#issues-and-pull-requests)
    - "Milestone = duplicate/invalid/wontfix" is replaced by [marking as duplicate](https://docs.github.com/en/issues/tracking-your-work-with-issues/marking-issues-or-pull-requests-as-a-duplicate) or closing with a comment

- For contributing a change that does not address an existing open Issue, **instead of opening a Trac ticket and pushing a git branch to it**:
  - Create a new local branch based on `upstream/develop`
  - Push the branch to the remote named `origin`, i.e to your fork
  - A git message will provide a URL for opening a Pull Request (PR)
  - [Create the PR](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request)
  - If it is not ready for review, [mark the PR as a "Draft"](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/changing-the-stage-of-a-pull-request)

- For contributing a change that addresses an existing open Issue, **instead of pushing a git branch to a Trac ticket**:
  - same as above
  - [use `Fixes #ISSUENUMBER` to link to an existing issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue); this will auto-close the linked Issue when the PR is merged.

- For finding PRs that are waiting for review, **instead of using Trac ticket reports**:
  - [filter PRs by review status](https://docs.github.com/en/issues/tracking-your-work-with-issues/filtering-and-searching-issues-and-pull-requests#filtering-pull-requests-by-review-status)

- For reviewing a change:
  - **instead of looking at the patchbot**, use the [Checks on GitHub Actions](https://trac.sagemath.org/wiki/ReleaseTours/sage-9.6#BuildsandchecksofticketbranchesonGitHubActions), which are already available on Trac since the Sage 9.6 series; the status of the check runs will be clearer on GitHub [than on Trac](https://trac.sagemath.org/ticket/33818) 
  - **instead of copy-pasting parts of the diff of a branch to a comment**, use [pull request reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews): You can add comments directly to changed lines
  - **instead of changing the status of the ticket** (i.e. "positive review" or "needs work"), choose the [correct type of your pull request review](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/reviewing-proposed-changes-in-a-pull-request#submitting-your-review) (i.e. "approve" vs "request changes")
  - for trying the branch of a PR locally, **instead of using `git trac try TICKETNUMBER`**, use [`git fetch origin pull/PULL_REQUEST_ID/head:LOCAL_BRANCH_NAME`](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/checking-out-pull-requests-locally)
    
- For organizing, **instead of using meta-tickets**:
  - either open an Issue
  - or [create a new Project](https://github.com/features/issues)

- Unchanged: Release Manager @vbraun merges positively reviewed tickets into his branch https://github.com/vbraun/sage
  - The release manager uses [a filter to identify the pull requests that a reviewer has approved](https://docs.github.com/en/issues/tracking-your-work-with-issues/filtering-and-searching-issues-and-pull-requests#filtering-pull-requests-by-review-status)
  - Once released (currently targeted for Q4 2022), we instead use [Merge Queues](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).
- Unchanged: To make a beta or stable release, Release Manager merges (fast-forward) his branch into the `develop` branch and creates a tag
- Unchanged: To make a stable release, Release Manager merges (fast-forward) the `develop` branch into the `main` branch.
  - Only change is the rename of `master` to `main` due to cultural sensitivity - as proposed in https://trac.sagemath.org/ticket/31287
  - In the future, we might migrate from this [Gitflow workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow) to the [Trunk-based workflow](https://www.atlassian.com/continuous-delivery/continuous-integration/trunk-based-development) where the `develop` branch is no longer needed and changes are directly merged into `main`.


# Conversion of Trac tickets and the Trac wiki to GH Actions

- script: https://github.com/sagemath/trac-to-github
- Question: how are permissions for existing branches handled so that people can still update the migrated PR? As an idea, maybe we can create the PR based on the branch in the sagetrac-mirror (and remove the branch protection rule there)
