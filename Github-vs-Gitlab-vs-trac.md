This page compares [Github](https://github.com/), [Gitlab](https://about.gitlab.com/) and [Trac](https://trac.sagemath.org/), focusing on the specific differences that are important to the Sage community.

# Github vs trac

## In favor of github

* We are struggling with various aspects of self hosting.  Several Sage developers have spend a lot of time over the last month working to upgrade trac and the underlying virtual machine.  Hosting on Github means that someone else with more experience and economies of scale is providing this service for us.  Moreover, we are currently paying money for trac's servers, while Github would be free.
* Github is [the largest source code host](https://en.wikipedia.org/wiki/GitHub#:~:text=It%20is%20commonly%20used%20to,host%20as%20of%20November%202021.), making it far more likely to be familiar to new developers than trac.  We are losing many potential developers by having a workflow that is unfamiliar to them (though it is hard to measure this effect due to selection bias).  Conversely, the use of github a more transferrable skill, which may [help draw in younger developers](https://groups.google.com/g/sage-devel/c/ayOL8_bzOfk/m/Zj5W1T1gBwAJ) who may want to build a resume, or [donors to Sage](https://groups.google.com/d/msgid/sage-devel/173df162-58d0-4cad-b4c1-7be8e5d9133bn%40googlegroups.com).
* Github provides many features that trac doesn't (or that are superior to the corresponding trac feature). For example:
  - [Request reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/requesting-a-pull-request-review) from specific people or teams
  - Github's [pull request reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews) allow you to add in-line comments and [suggestions](https://egghead.io/lessons/github-add-suggestions-in-a-github-pr-review) to a PR, and generally offer a much smoother reviewing experience than trac's.
  - [Project planning](https://github.com/features/issues)
  - [Fine-grained notifications](https://docs.github.com/en/account-and-profile/managing-subscriptions-and-notifications-on-github/setting-up-notifications/about-notifications) about activities in issues, pull-requests or new releases
  - [Reactions](https://github.blog/2016-03-10-add-reactions-to-pull-requests-issues-and-comments/) on issues/pull-requests and comments, which help with prioritizing issues and reducing noise
  - [Navigating code in the web interface](https://docs.github.com/en/repositories/working-with-files/using-files/navigating-code-on-github)
  - [Link to and inline-display a code snippet](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-a-permanent-link-to-a-code-snippet), which makes it easier to clearly communicate with other developers.
  - Extensive API that allows to automate many aspects. We can pick from a wide variety of community-provided apps/bots that help with organizing routine task, e.g. [display test coverage](https://about.codecov.io/product/feature/pull-request-comments/) or [close stale issues](https://github.com/marketplace/stale).
* We've already added some [continuous integration checks](https://trac.sagemath.org/wiki/ReleaseTours/sage-9.6#BuildsandchecksofticketbranchesonGitHubActions) to [trac](https://trac.sagemath.org/ticket/33818); these will be [clearer](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks) when using Github.
* Github is actively developed with a very large user base, and new features are being [added regularly](https://github.blog/); trac is far less active (18 posts in 6 threads on their [mailing list](https://groups.google.com/g/trac-dev) since the beginning of 2022, all upcoming releases are [over a year overdue](https://trac.edgewall.org/roadmap) and mainly seem concerned with updating dependencies rather than implementing new features, their [list of users](https://trac.edgewall.org/wiki/TracUsers) includes many dead links and some that have migrated to other systems like gitlab).  With trac becoming less and less maintained we're likely to face further security issues and compatibility issues with other software going forward.
* It is possible in github to make small changes via the web interface, which lowers the barrier for fixing typos.
* Github supports two-factor authentication, reducing the chance of someone sneaking malicious code into Sage.
* Various Sage dependencies have migrated to github already, making automatic cross repository links helpful when reporting bugs upstream.
* Due to its popularity, many IDEs provide plugins for Github. For example, it is possible to do the complete fork-clone-branch-pr workflow and review PRs completely from within [VS Code](https://code.visualstudio.com/docs/editor/github) without using Github's web interface.

## In favor of trac

* While git and trac are open source, github is closed source.
* We don't have control of Github's policies, procedures and prices.  Github's prices for [providing hosting](https://docs.github.com/en/get-started/learning-about-github/faq-about-changes-to-githubs-plans) and [continuous integration](https://docs.github.com/en/actions/learn-github-actions/usage-limits-billing-and-administration) services may increase (they're currently free).  Copyright laws can have [unfortunate consequences](https://www.asmeurer.com/blog/posts/the-sympy-hackerrank-dmca-incident/) causing downtime and possible legal costs.  As a large company, Github has to be more cautious about [obeying US export control laws](https://docs.github.com/en/site-policy/other-site-policies/github-and-trade-controls) and has thus [blocked access](https://techcrunch.com/2019/07/29/github-ban-sanctioned-countries/) in various countries (though it has since [restored access in Iran](https://github.blog/2021-01-05-advancing-developer-freedom-github-is-fully-available-in-iran/)).
* [Backing up or migrating](https://rewind.com/blog/three-ways-to-backup-your-github-issues/) issues and wiki pages off of github takes some work, making it harder to switch away from github if they raise prices or make changes that we don't like.
* Various aspects of the github workflow will be different (the separation of tickets into Issues and PRs for example, switching from [git-trac](https://github.com/sagemath/git-trac-command) to [Github's CLI](https://cli.github.com/)), requiring current Sage developers to devote time and effort into learning new systems

# Github vs Gitlab

This section is still in progress.  Here are some links to help flesh it out:

* https://kinsta.com/blog/gitlab-vs-github/#gitlab-vs-github-key-differences
* https://www.zdnet.com/article/github-vs-gitlab-the-key-differences/
https://www.incredibuild.com/blog/gitlab-vs-github-comparison (Flow and CI sections)
https://radixweb.com/blog/github-vs-gitlab#difference
https://about.gitlab.com/devops-tools/github-vs-gitlab/
https://resources.github.com/devops/tools/compare/

## In favor of Github

* We are heavily invested in using Github Actions, having spent a lot of time incorporating them into our [current workflow](https://trac.sagemath.org/wiki/ReleaseTours/sage-9.6#BuildsandchecksofticketbranchesonGitHubActions).

## In favor of Gitlab

* Since Gitlab's core software is open source, it is easier to switch to self hosting if we become unhappy with gitlab.com.