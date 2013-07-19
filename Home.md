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

1. In the preferences for your trac account, there is a SSH Keys tab. Add your public keys.

1. The trac server's ssh port is 2222 (rather than the standard 22), so
   the easiest way to deal with this is add an extra `Host` to your SSH config file (note
   that your username should be `git`). Then you can push and pull using

        git <push|pull> trac:sage.git [ARGS]

   An alternative is to add a remote repository to your local sage repository:

        git remote add trac ssh://git@trac.sagemath.org:2222/sage.git

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