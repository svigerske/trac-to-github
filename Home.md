## Build instructions

    git clone git://github.com/sagemath/sage.git
    cd sage
    make

See http://trac.sagemath.org/wiki/QuickStartSageGit for more details.



## Development

* You can either use the [development scripts](http://sagemath.github.io/git-developer-guide/walk_through.html),
* or you can use [git directly](http://sagemath.github.io/git-developer-guide/manual_git.html) to work on the Sage source code.


## Transition Status

### Done

- build system modifications (except as below)
- git friendly trac server
- development scripts (found at [dev_scripts](https://github.com/ohanar/sage/tree/dev_scripts))
    * git backend (pending no more needed functionality)
    * user interface api
- resolve [#14781](http://trac.sagemath.org/14781)

### Needs work

- development scripts (found at http://trac.sagemath.org/ticket/14482)
    * mecurial compatibility scripts
        + SPKG merge script (should be really easy to write using a truncated version of the script I use to manage the git repository)
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