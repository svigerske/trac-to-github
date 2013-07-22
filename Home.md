## Build instructions

1. Make sure you have a constant internet connection.
1. Clone the `build_system` branch from sagemath's sage repository:

        git clone git://github.com/sagemath/sage.git -b build_system

   The changes the `build_system` branch has over the `master` branch
   are exactly the changes that need review at [#14480](http://trac.sagemath.org/14480).

1. Go into the source directory and run `make`:

        cd sage
        make

## Using Git+Trac without the development scripts


### Pushing and pulling branches to Trac

1. In the preferences for your trac account, there is a SSH Keys tab. Add your public keys.

1. The trac server's ssh port is 2222 (rather than the standard 22), so
   the easiest way to deal with this is add an extra `Host` to your SSH config file (note
   that your username should be `git`). Then you can push and pull using

        git <push|pull> trac:sage.git [ARGS]

   An alternative is to add a remote repository to your local sage repository:

        git remote add trac ssh://git@trac.sagemath.org:2222/sage.git -t master

   Then you can push and pull using

        git <push|pull> trac [ARGS]

1. You have push permissions to branches of the form `u/TRAC_USERNAME/*`. So for
   example, I have permissions to do the following

        git push local_branch:u/ohanar/remote_branch

   since my trac username is `ohanar`. However, the following would give me an error

        git push local_branch
        git push local_branch:master
        ...

1. To attach a branch to a ticket, push your changes to the trac server and
   then fill the `Branch` field in the corresponding ticket with the remote branch
   name. For example, if I have a local branch named `local_branch` and I want to
   attach this branch to ticket #555, I would do

        git push local_branch:u/ohanar/remote_branch

   and then on trac, I would fill the `Branch` field with `u/ohanar/remote_branch`.

   The `Branch` field is color coded: red means there is an issue, green means it will
   merge cleanly into `master`. If it is red, the tooltip will tell you what is wrong.
   If it is green, then it will link to a diff of the changes against
   `u/ohanar/build_system`. (This is temporary until
   [#14480](http://trac.sagemath.org/14480) is merged into the `master` branch.)


### Applying mercurial patches

During the transition from mercurial to git, you may want or need to apply some patches produced by mercurial.  You can use the standard Unix tool `patch` for this, or you can use `git apply`.  The main thing to realize, for either approach, is that the sage directory structure has changed, and you will need to account for this.  The sage library is now in `SAGE_ROOT/src` instead of `SAGE_ROOT/devel/sage`.

If you are in the `SAGE_ROOT` directory, you can apply a patch with

    git --directory=src --ignore-space-change --whitespace=fix PATCHFILE

If you `cd` to `SAGE_ROOT/src`, then the `--directory` option is not necessary.


### Example usage

* Alice has made some changes for ticket 1234, and made them available on trac by uploading a branch named `u/alice/1234`.  Bob wants to review her changes, so he does

    git fetch trac u/alice/1234
    git checkout FETCH_HEAD

Then Bob can test Alice's changes as much as he likes.

* Bob has tested, and now wants to make a very minor change as a reviewer.  He does

    git checkout -b ticket/1234
    # make the change
    git commit -am 'helpful commit message'
    git push trac ticket/1234:u/bob/1234

Then Bob goes to the ticket page on Trac and makes some changes to tell Alice about his review, the minor change, and the branch he just uploaded: `u/bob/1234`.  Alice can merge that branch with her own if she wants to use Bob's suggestions.

* Later, Alice and Bob decide to collaborate on ticket 4321, where they'll both be making substantial changes.  Alice puts a branch on Trac for this at `u/alice/4321`.  The Bob does

    git remote set-branches trac --add u/alice/4321
    git remote update
    git checkout trac/u/alice/4321 -b ticket/4321

Then Bob does a bunch of work and makes a few commits to his local branch, `ticket/4321`.  Alice does the same to her local branch, and pushes them up to the Trach branch she started.  Bob wants to merge them in, so he does

    git remote update
    git merge trac/u/alice/4321

## Transition Status

### Done

- build system modifications (except as below)
- git friendly trac server
- development scripts (found at [dev_scripts](https://github.com/ohanar/sage/tree/dev_scripts))
    * git backend (pending no more needed functionality)
    * user interface api
- resolve [#14781](http://trac.sagemath.org/14781)

### Needs work

- development scripts (found at [dev_scripts](https://github.com/ohanar/sage/tree/dev_scripts))
    * trac backend
        + method to get display ticket, including all comments
        + method to edit whole ticket (easy to do once the previous one is implemented)
    * public interface (`SageDev` object)
        + doctests and docstrings
        + finish move of SavingDicts (these should be attached to `SageDev` as opposed to `GitInterface`, as they were previously)
        + finish revamp to be more pythonic (asking forgiveness, rather than a bunch of if..else blocks)
    * mecurial compatibility scripts
        + SPKG merge script (should be really easy to write using a truncated version of the script I use to manage the git repository)
        + branch -> mercurial patch (that works with whitespace)
        + make `download_patch` a bit smarter when it comes to urls
- finish cleanup of the mercurial export script (nearly done)
- documentation
    * `walk_through.rst` needs a major overhaul
    * `producing_spkgs.rst` and `patching_spkgs.rst` need updating
        + old style spkgs are deprecated
        + unified repository now
        + package_version.txt
        + checksums.ini (`sage-fix-pkg-checksums`)
    * `producing_patchs.rst` needs major overhaul
    * `trac.rst` probably needs updating
    * other smaller fixups will probably be needed throughout
- buildbot
- patchbot