See also: https://trac.sagemath.org/ticket/30363

# Provisional workflow on GitHub

This is a guide for developers transiting from Trac to GitHub. The workflow proposed here will be consolidated into the [Sage Developer's Guide](https://doc.sagemath.org/html/en/developer/index.html) in due course.

## Preliminary one time action: Instead of depositing an SSH public key on Trac

  - No action needed if you have already contributed to any other project on GitHub and set up git credentials or SSH keys for this.
  - New users of GitHub should follow either

    - https://docs.github.com/en/get-started/getting-started-with-git/caching-your-github-credentials-in-git

    or generate an SSH keypair, or use an already existing one, and upload the public key to your GitHub account settings

    - https://docs.github.com/en/authentication/connecting-to-github-with-ssh

## Preliminary one time action: Instead of adding a git remote named `trac`  <a name="remote-trac"></a>

  - If you already have your personal GitHub fork of sagemath/sage, rename it (perhaps to `sage-archive-CURRENT-DATE`) and archive it; it is best to create a fresh fork of our new repository because *fork relationships on GitHub cannot be migrated.*
  - Create your personal GitHub fork https://github.com/USERNAME/sage of the main repository https://github.com/sagemath/sage,  where `USERNAME` is your GitHub account name, following

    - https://docs.github.com/en/get-started/quickstart/fork-a-repo#forking-a-repository

  - If you already have a clone of a Sage repository on your computer:

    - Check your current git remote repositories:
      ```
      git remote -v
      ```
    - If you already have the main Sage repository https://github.com/sagemath/sage as a remote, and its name is not `upstream`, rename it to `upstream`:
      ```
      git remote rename OLD-NAME upstream
      ```
      where `OLD-NAME` is the name of the remote.

      Otherwise, add a new remote by either
      ```
      git remote add upstream https://github.com/sagemath/sage.git
      ```
      or, if you are using SSH access with your SSH keypair
      ```
      git remote add upstream git@github.com:sagemath/sage.git
      ```
    - If you already have a remote named `origin` and it is not your personal fork, rename this remote to something else:
      ```
      git remote rename origin OLD-ORIGIN
      ```
      where `OLD-ORIGIN` is some name of your choosing.

      Finally, add your fork as a remote via (the URL `https://github.com/USERNAME/sage.git` can be copied from there)
      ```
      git remote add origin https://github.com/USERNAME/sage.git
      ```
      or, if you are using SSH access with your SSH keypair
      ```
      git remote add origin git@github.com:USERNAME/sage.git
      ```

    Otherwise, start afresh:

    - Clone the forked repository:

      - https://docs.github.com/en/get-started/quickstart/fork-a-repo#cloning-your-forked-repository

      and do one of the following, depending on the access type (https vs ssh):
      ```
      git clone https://github.com/USERNAME/sage.git
      ```
      or, if you are using SSH access with your SSH keypair
      ```
      git clone git@github.com:USERNAME/sage.git
      ```
      This will link your fork as the `origin` remote in the local git repo.
    - Configure git to sync your fork with the main Sage repository

      - https://docs.github.com/en/get-started/quickstart/fork-a-repo#configuring-git-to-sync-your-fork-with-the-original-repository

      and do one of the following, depending on the access type (https vs ssh):
      ```
      git remote add upstream https://github.com/sagemath/sage.git
      ```
      or, if you are using SSH access with your SSH keypair
      ```
      git remote add upstream git@github.com:sagemath/sage.git
      ```
   - In order to be able to fetch branches from existing Trac tickets, also set up the following (read-only) remote:
     ```
     git remote add trac https://github.com/sagemath/sagetrac-mirror.git
     ```
   - Of course, you can give arbitrary names to your git remotes, but `origin` and `upstream` are the established defaults, which will make it easier to use tools such as the GitHub command-line tools.

## Instead of opening a Trac ticket

For reporting a bug, planning an enhancement, describing a project:

  - Open an [issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/about-issues) on GitHub [in our repository sagemath/sage](https://github.com/sagemath/sage/issues)
  - Trac ticket box attributes are mapped (to [labels](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/managing-labels)) as follows:
    - **Type** ("defect", "enhancement", "task") are mapped to *type labels* `t: bug`, `t: enhancement`.
    - **Component** ("basic arithmetic", "linear algebra", "geometry", etc.) are mapped to *component labels*
      with prefix `c: `; except for "refactoring", "performance", "doctests" (and the like), "memleak", which are mapped to labels `t: refactoring`, `t: performance`, `t: tests`, `t: bug`, respectively.
    - **Priority** ("trivial"/"minor"/"major"/"critical"/"blocker") are mapped to *priority labels* with prefix `p: `
    - **Keywords** just add them in free form to the issue description if there's no suitable label.
    - **Cc**: use `@USERNAME` either in the issue description or in any comment. Optionally, regular developers who would like to get notified automatically when a PR touches a particular part of the Sage code can add themselves as a [Code Owner](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).
    - **Description** becomes just the first comment on the issue
    - **Branch**/**Commit**/**Authors**/**Reviewers**/**Work Issues**: via Pull Requests (PR), see below
    - **Report Upstream** is replaced by [automatic cross references between Issues/PRs in different repos](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/autolinked-references-and-urls#issues-and-pull-requests).
    - **Milestone duplicate/invalid/wontfix** and **Resolution** ("duplicate", "invalid", "wontfix")
      are replaced by
      - [marking as duplicate](https://docs.github.com/en/issues/tracking-your-work-with-issues/marking-issues-or-pull-requests-as-a-duplicate),
      - *resolution labels* `r: duplicate`, `r: invalid`, `r: wontfix`, or
      - closing with a comment; use drop-down option "Close as not wanted"
    - **Dependencies**: Use the phrase `Depends on `, followed by the issue or PR reference.
      Repeat this in separate lines if there is more than one dependency.
      This format is understood by various dependency managers (see https://www.dpulls.com/,
      https://github.com/z0al/dependent-issues, https://github.com/gregsdennis/dependencies-action/pull/5).

## Instead of pushing a git branch to a Trac ticket

### For contributing a change that does not address an existing open issue  <a name="pr-with-no-issue"></a>

  - Create a new local branch based on `upstream/develop`.
  - Push the branch to the remote named `origin`, that is, to your fork.
  - A git message will provide a URL for opening a Pull Request (PR).
  - [Create the PR](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request)
  - Apply labels as appropriate:
    - *type labels*:  `t: bug`, `t: enhancement`, `t: performance`, `t: refactoring`, `t: feature`, `t: tests`
    - *component labels*: many labels with prefix `c: `
    - *priority labels*: `p: trivial / 5`, `p: minor / 4`, `p: major / 3`, `p: critical / 2`, `p: blocker / 1`
    - *status labels*: `s: needs review`, `s: needs work`, `s: needs info`, `s: positive review`

  - If it is not ready for review, [mark the PR as a "Draft"](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/changing-the-stage-of-a-pull-request)

### For contributing a change that addresses an existing open issue that has been created on GitHub
  - Check if a PR is already attached. If so, follow [this section](#issue-with-pr) below.
  - Otherwise the same as [this section](#pr-with-no-issue) above.
  - Use `Fixes #ISSUE-NUMBER` [to link to an existing issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue); this will auto-close the linked issue when the PR is merged.

### For contributing a change that addresses an existing open issue that has been migrated from Trac

  - Check if a PR is already attached. If so, follow [this section](#issue-with-pr) below.
  - Pull the branch from your read-only `trac` remote (see [the section](#remote-trac)) as you used to do before.
  - Edit and commit your changes.
  - Push the branch to the remote named `origin`, that is, to your fork.
  - Follow the instructions above from [here](#pr-with-no-issue).

### For contributing a change that addresses an existing open issue that already has a PR <a name="issue-with-pr"></a>

**Instead of changing the branch-field of a Trac ticket:**
  - Find the id `PULL-REQUEST-ID` of the pull request you want to contribute to. This is the sequence of digits right after the pull request's title.
  - Pull the branch of the PR to a new local branch using
    ```
    git fetch origin pull/PULL-REQUEST-ID/head:BRANCH-NAME
    git checkout BRANCH-NAME
    ```
    where `BRANCH-NAME` will be the name of your local branch.
  - Edit and commit your changes.
  - Follow the instructions above from [here](#pr-with-no-issue), but create a new PR against the branch that the PR is based upon. For this, you navigate to `https://github.com/ORIGINAL-USER/sage/pulls`, where `ORIGINAL-USER` is the name of the original creator of the PR, and click on "Create new pull request", where you can select the correct target branch as "base".

## Instead of using Trac ticket reports

**For finding PRs that are waiting for review:**
  - [filter PRs by review status](https://docs.github.com/en/issues/tracking-your-work-with-issues/filtering-and-searching-issues-and-pull-requests#filtering-pull-requests-by-review-status)

## Instead of making changes to a Trac ticket

### For adding comment
  - If a PR is linked to the issue, you can alternatively comment on the PR.
  - Comments on the reported issue should go on the issue.
  - Comments on the submitted code should go on the linked PR.
  - When you are not sure where the comment should go, it may help to view both the issue and the PR on a large screen simultaneously.

### For reviewing a change
  - **Instead of looking at the patchbot**, use the [Checks on GitHub Actions](https://trac.sagemath.org/wiki/ReleaseTours/sage-9.6#BuildsandchecksofticketbranchesonGitHubActions), which are already available on Trac since the Sage 9.6 series; the [status of the check runs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks) will be clearer on GitHub [than on Trac](https://trac.sagemath.org/ticket/33818).
  - **Instead of copy-pasting parts of the diff of a branch to a comment**, use [pull request reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews): You can add comments directly to changed lines.
  - **Instead of making reviewer edits**, smaller suggestions can be made [through the github web interface](https://egghead.io/lessons/github-add-suggestions-in-a-github-pr-review) as part of the [pull request review](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/incorporating-feedback-in-your-pull-request).
  - **If you want to be able to make changes directly to others' PRs** (when the author selects to allow edits from maintainers), please contact one of the [Sagemath Github admins](https://github.com/orgs/sagemath/people?query=role%3Aowner), who can give you the relevant permissions.
  - **Instead of changing the status of the ticket** (e.g., "positive review" or "needs work"), choose the [correct type of your pull request review](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/reviewing-proposed-changes-in-a-pull-request#submitting-your-review) (i.e. "approve" vs "request changes")
  - For trying the branch of a PR locally, **instead of using `git trac checkout TICKETNUMBER` or `git trac try TICKETNUMBER`**, use
      ```
      git fetch upstream pull/PULL-REQUEST-ID/head:LOCAL-BRANCH-NAME
      ```
      Consult https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/checking-out-pull-requests-locally.

    Alternatively, with the [GitHub command-line interface](https://trac.sagemath.org/ticket/34523), use
    ```
    gh pr checkout PULL-REQUEST-ID
    ```
    Consult https://cli.github.com/manual/gh_pr_checkout.

### For closing issues
  - **Instead of using the milestone sage-invalid/duplicate/wontfix and setting needs_review**, use one of the resolution labels: `r: duplicate`, `r: invalid` etc.
  - Add a comment explaining why the issue has been closed if that's not already clear from the discussion
  - Users with the necessary permissions can then directly [close the issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/closing-an-issue): In the dropdown menu on the "Close issue" button, select "Close as not planned"
  - Otherwise, use the labels "needs review" or "positive review", and someone else with the necessary rights will take care of closing the issue.

If you think an issue has been prematurely be closed, feel free to reopen it.

### For organizing projects
  - **Instead of using meta-tickets,** open an issue including a checklist of things to do which can be checked off as they are dealt with by various PRs,
  - Alternatively [create a new Project](https://github.com/features/issues).

# Release Manager's Workflow

See also discussion in https://github.com/sagemath/trac-to-github/issues/85.

- Unchanged: Release Manager @vbraun merges positively reviewed tickets into his branch https://github.com/vbraun/sage.
  - The release manager uses [a filter to identify the pull requests that a reviewer has approved](https://docs.github.com/en/issues/tracking-your-work-with-issues/filtering-and-searching-issues-and-pull-requests#filtering-pull-requests-by-review-status).
  - Once released (currently targeted for Q4 2022), we instead use [Merge Queues](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).
- Unchanged: To make a beta or stable release, Release Manager merges (fast-forward) his branch into the `develop` branch and creates a tag.
- Unchanged: To make a stable release, Release Manager merges (fast-forward) the `develop` branch into the `main` branch.
  - Proposed in https://trac.sagemath.org/ticket/31287: Rename `master` to `main` due to cultural sensitivity.
  - In the future, we might migrate from this [Gitflow workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow) to the [Trunk-based workflow](https://www.atlassian.com/continuous-delivery/continuous-integration/trunk-based-development) where the `develop` branch is no longer needed and changes are directly merged into `main`.

# Proposed permissions and protections

See also discussion in https://github.com/sagemath/trac-to-github/issues/85.

Main repository https://github.com/sagemath/sage:
- Only 2 named [branches](https://github.com/sagemath/sage/branches), `develop` and `master`.
- Everything else goes through PRs.
- Create a new team: https://github.com/orgs/sagemath/teams "Release Manager".
- Set up [branch protection rule](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/about-protected-branches): Only "Release Manager" team can push; no override for users in Admin role; no deletions; no force pushes
- Review/update https://github.com/orgs/sagemath/teams/core/members
- Create a new team for other developers, [give Write access to team in repo](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/managing-teams-and-people-with-access-to-your-repository#inviting-a-team-or-person), add people to team
  - the Write access does not allow pushing to `develop` or `master`
  - the Write access allows members of the team to push commits to branches of PRs ([unless the PR owner has disabled this for this PR](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/allowing-changes-to-a-pull-request-branch-created-from-a-fork)).


# Retrieving data from GitHub (for backups etc)

[GitHub REST API](https://docs.github.com/en/rest)

Particularly, anything extracting/archiving discussions should probably look at [Issues API](https://docs.github.com/en/rest/issues/issues), because "Pull requests are just issues with code", although there is a separate [Pull request review comments API](https://docs.github.com/en/rest/pulls/comments). Special care may need to be taken to preserve cross-references when archiving.

3 minute video demoing importing github repos to gitlab, which emphasizes answers to a lot of natural frequent questions (involving users, issue comments, labels, etc.): https://www.youtube.com/watch?v=VYOXuOg9tQI

[Trac #34624: Backup Issues/PRs for projects hosted in https://github.com/sagemath/](https://trac.sagemath.org/ticket/34624)
