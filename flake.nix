{
  # Keep this line accurate and one line long: `nix flake metadata` prints it,
  # and it is the first thing a cold agent learns about the repo.
  description = "TwitchToREST -- Quart web service that subscribes to Twitch EventSub and chat and forwards follows, subs, gift subs, resubs, cheers, raids and channel-point redeems to a REST endpoint. Run `nix flake show` for the command map.";

  # nixpkgs is the only input: flake.lock holds exactly one node besides `root`,
  # pinned at rev 0e251e24a4f24e036a084b6b4b2d2491af4167f4. flake-utils is not
  # here because the only thing this flake would call it for -- eachDefaultSystem
  # -- is the `forAllSystems` genAttrs in the canonical machinery below, over a
  # system list this repo can actually read.
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    # `...` rather than a closed { self, nixpkgs }: with the pattern closed,
    # adding any second input fails at eval. Measured on a throwaway flake that
    # declared `inputs.second` and kept `{ self, nixpkgs }:` --
    # `error: function 'outputs' called with unexpected argument 'second'`.
    #
    # `self` is mandatory, not decorative -- the machinery below anchors every
    # verb on it (see rootPreamble).
    { self, nixpkgs, ... }:
    let
      lib = nixpkgs.lib;

      # ======================================================================
      # PER-REPO BLOCK 1 -- the toolchain
      # ======================================================================
      # Everything the commands below need on PATH. `checks.toolchain` realises
      # this closure, so a typo'd attr name fails at the flake gate instead of
      # surfacing as "command not found" halfway through a task.
      #
      # Explicit `pkgs.foo`, never `with pkgs; [ ... ]`: when an attr disappears
      # in a nixpkgs bump, `with` reports a bare undefined identifier with no
      # hint of which set it came from, and the name is not greppable.
      #
      # Pin the interpreter by MAJOR (python313), never by the rolling alias
      # (python3). Measured against this lock: `python3` is 3.14.7 while
      # `python313` is 3.13.15, so the alias already points somewhere other than
      # what this flake builds -- and it will move again.
      #
      # This repo ships NO manifest: `git ls-files` lists no requirements.txt,
      # no pyproject.toml, no setup.py, no Dockerfile and no .github/. The
      # dependency set below was derived by reading every `import` line in all
      # nine tracked .py files, and the third-party ones are exactly four:
      # requests, quart, passlib, twitchAPI.
      #
      # hypercorn is the fifth entry and is imported nowhere in this repo. It is
      # what serves `app.run()` at main.py:870: quart's own metadata requires
      # `hypercorn>=0.11.2`, and quart/app.py line 31 is
      # `from hypercorn.asyncio import serve`. Listed explicitly so the thing
      # that opens the socket is visible here rather than merely implied.
      #
      # All five resolve in this lock -- requests 2.34.2, quart 0.21.0, passlib
      # 1.9.3, twitchapi 4.5.0, hypercorn 0.18.0 -- so the environment is built
      # from store paths: no uv, no pip, no .venv, and hence no `setup` verb.
      pythonEnv =
        pkgs:
        pkgs.python313.withPackages (ps: [
          ps.requests
          ps.quart
          ps.passlib
          ps.twitchapi # PyPI name is twitchAPI; the nixpkgs attr is lowercase
          ps.hypercorn
        ]);

      toolchain = pkgs: [
        # ---- this repo's ecosystem ----
        (pythonEnv pkgs)
        pkgs.ruff

        # ---- present in every repo in the fleet ----
        pkgs.git
        pkgs.jq
        pkgs.gnumake
      ];

      # ======================================================================
      # PER-REPO BLOCK 2 -- libraries that get dlopened, not linked
      # ======================================================================
      # Empty, and measured rather than assumed: none of the five packages above
      # ships a single `.so` -- an rglob for `*.so` under each package directory
      # in the built environment returns zero files for all five -- so there is
      # nothing for a loader to fail to find.
      #
      # This list exists for manylinux wheels and node prebuilds, whose shared
      # objects are dlopened at runtime and therefore never seen by patchelf or
      # the nix linker. Nothing here is installed that way. While the list is
      # empty the machinery below emits no LD_LIBRARY_PATH preamble at all, so
      # the ambient value is left untouched.
      nativeLibs = _: [ ];

      # ======================================================================
      # PER-REPO BLOCK 3 -- constant environment variables
      # ======================================================================
      # Constants only, applied identically to the dev shell and to every
      # wrapper, so a verb cannot behave differently depending on how it was
      # invoked. Anything that must READ an existing value (LD_LIBRARY_PATH),
      # UNSET something (SOURCE_DATE_EPOCH) or touch the work tree belongs in
      # the machinery's preambles instead.
      envVars = _: {
        # The interpreter lives in the store and cannot cache there, so every
        # __pycache__ python would write lands in the work tree instead. Not
        # writing it at all is cheaper than ignoring it.
        PYTHONDONTWRITEBYTECODE = "1";
        # Unbuffered stdout/stderr. main.py:865 starts the bot on a background
        # thread and main.py:870 then hands the main thread to Quart's
        # `app.run()`, so under the default block buffering an agent capturing
        # output through a pipe sees nothing until the process dies -- which
        # reads as a hang.
        PYTHONUNBUFFERED = "1";
      };

      # ======================================================================
      # PER-REPO BLOCK 4 -- the command map
      # ======================================================================
      # THE single source of truth: it generates `apps` (so `nix run .#lint`
      # works), the `dev-*` wrappers on PATH inside the shell, and `dev-help`.
      # Nothing is written twice, so `nix flake show` cannot disagree with what
      # `dev-lint` actually runs.
      #
      # Each entry is { description, text }. Mutation is not declared with a
      # flag: a verb that writes calls `need_writable_checkout` as the first
      # line of its own text, which is where a reader looking at the writing
      # code will see it.
      #
      # House vocabulary is setup / build / test / lint / fmt / run, and a verb
      # this repo has no meaning for is OMITTED, because absence is information
      # and a stub that echoes "not applicable" turns the command map into a
      # liar. There is no README in this repo either (`git ls-files` shows
      # none), so this map plus `nix flake show` is the whole documented
      # surface. For this repo:
      #
      #   no `setup`  every dependency is a store path; nothing to bootstrap
      #   no `build`  it is a service run from source; there is no artifact
      #   no `test`   there is no test suite. POST_test.py and REST_test.py are
      #               named like tests and are not: POST_test.py fires a live
      #               HTTP POST at http://localhost:5001 from module level, and
      #               REST_test.py is a throwaway Quart listener on port 5001
      #               that answers it. `grep -nE 'assert|pytest|unittest' *.py`
      #               matches nothing anywhere in the repo.
      commands = _: {
        run = {
          # main.py pulls its configuration in by star-import at lines 10 and 11
          # (`from some_secrets import *`, `from config import *`). Both files
          # are named in .gitignore, so a fresh clone cannot start. Measured, in
          # this checkout, with `python main.py`:
          #
          #   File ".../main.py", line 10, in <module>
          #       from some_secrets import *
          #   ModuleNotFoundError: No module named 'some_secrets'
          #
          # Check for them up front so the failure names the actual problem
          # instead of that stack trace.
          #
          # NEEDS STDIN, and no flag turns that off: main.py:611 prompts for an
          # initial password whenever no password is stored yet (the fresh-clone
          # case), and startup ends at main.py:661 in `await self.cli()`, whose
          # loop body is the `input()` at main.py:666. Under `nix run` with
          # stdin closed that looks like an unkillable hang, so an agent must
          # pipe answers in (`nix run .#run < answers.txt`) or leave this verb
          # to a human. Fixing it means adding a non-interactive path to
          # main.py; do not paper over it here.
          description = "start the bot and auth server -- INTERACTIVE, prompts on stdin; needs the gitignored config.py + some_secrets.py";
          text = ''
            need_writable_checkout
            # The cd is load-bearing, not tidiness: main.py hardcodes relative
            # state paths -- `os.makedirs('data')` at main.py:607 and
            # `open('data/pws.json')` at main.py:229 -- so started from anywhere
            # else it silently forks a second state directory under the caller's
            # cwd. That write is why need_writable_checkout runs first.
            cd "$REPO_ROOT"

            missing=""
            for f in some_secrets.py config.py; do
              [ -f "$REPO_ROOT/$f" ] || missing="$missing $f"
            done
            if [ -n "$missing" ]; then
              echo "cannot start: missing$missing in $REPO_ROOT" >&2
              echo "both are gitignored and must be written by hand. Between them main.py needs:" >&2
              echo "  APP_ID APP_SECRET USER_NAME SERVER_NAME REST_URI REST_PORT" >&2
              echo "  AUTH_URL AUTH_PORT WEBHOOK_URL WEBHOOK_PORT TEST" >&2
              exit 1
            fi
            exec python main.py "$@"
          '';
        };
        lint = {
          # There is no ruff configuration in this repo or above it --
          # `ruff check --show-settings` names no configuration file -- so this
          # is ruff's own default rule selection. Measured with the ruff this
          # lock pins (0.16.2): 104 findings across the nine tracked .py files,
          # 12 of them F401, so the verb exits 1. That is the code, not the
          # flake. Do not add --exit-zero or a permissive config to make it
          # green; either fix the findings or leave the signal honest.
          #
          # `cd "$REPO_ROOT"`, and never a bare `"$@"`: ruff with no path
          # argument means `.`, and left as the CALLER's directory that is how
          # `nix run /path/to/repo#lint` prints "All checks passed!" having
          # inspected zero files. The cd does a second job no path argument can
          # -- ruff resolves isort's first-party `src` root from the PROCESS's
          # cwd, so the very same absolute target scores differently depending
          # on where you stand. Measured: 104 findings with cwd at the repo
          # root, 103 with cwd in a foreign directory, the missing one being
          # exactly `vote.py:3:1 I001`. The price is that a RELATIVE argument
          # now resolves against the repo root; an absolute one still means
          # what it says.
          #
          # --no-cache is not a micro-optimisation. $REPO_ROOT is the read-only
          # store snapshot whenever the caller is outside a checkout, and ruff
          # puts `.ruff_cache` in its cwd rather than beside the files it was
          # handed, so with caching left on it dies there. Measured, with cwd
          # set to that snapshot:
          #
          #   ruff failed
          #     Cause: Failed to create temporary file
          #     Cause: No such file or directory (os error 2) at path
          #     "/nix/store/<hash>-source/.ruff_cache/0.16.2/.tmpXXXXXX"
          #
          # Nine files re-parse in 0.01s wall here, so there is nothing to save
          # by caching anyway.
          description = "ruff check (read-only; exits non-zero on this repo's existing findings)";
          text = ''
            cd "$REPO_ROOT"
            ruff check --no-cache "''${@:-.}"
          '';
        };
        fmt = {
          # MUTATING, and the verb with the most to lose from a wrong anchor:
          # unguarded, `nix run <url>#fmt` would rewrite whatever Python happens
          # to be sitting in the caller's directory. need_writable_checkout is
          # the first thing it does, so outside a checkout it refuses instead --
          # `checks.verbAnchoring` drives exactly that case and diffs the decoy
          # afterwards. Everything after the guard is identical to lint, the cd
          # and --no-cache included, for the same reasons.
          description = "ruff format -- rewrites this repo's Python in place";
          text = ''
            need_writable_checkout
            cd "$REPO_ROOT"
            ruff format --no-cache "''${@:-.}"
          '';
        };
      };

      # ======================================================================
      # PER-REPO BLOCK 5 -- the name
      # ======================================================================
      # Cosmetic: it appears in the interactive dev-shell banner and nowhere
      # else. Still has to be right, because it is how a human tells two open
      # shells apart.
      repoName = "TwitchToREST";

      # ======================================================================
      # PER-REPO BLOCK 6 -- checks beyond the canonical two
      # ======================================================================
      extraChecks = pkgs: {
        # Not a tautology: it imports every third-party name the tracked source
        # imports, spelled the way the source spells it. The quart line is the
        # union of main.py:17 and REST_test.py:1; the twitchAPI lines are
        # main.py:16 and 19-24 verbatim. hypercorn is here although nothing in
        # this repo imports it, because it is what `app.run()` ends up calling.
        # If a nixpkgs bump renames an attr or twitchAPI moves a submodule,
        # `nix flake check` fails here rather than main.py failing on a stream
        # day.
        imports = pkgs.runCommand "import-check" { nativeBuildInputs = [ (pythonEnv pkgs) ]; } ''
          python - <<'PY'
          import requests, passlib.hash, hypercorn
          from passlib.hash import pbkdf2_sha256
          from quart import Quart, abort, redirect, render_template, request, jsonify
          from twitchAPI.helper import first
          from twitchAPI.oauth import UserAuthenticator
          from twitchAPI.twitch import Twitch, TwitchUser
          from twitchAPI.eventsub.webhook import EventSubWebhook
          from twitchAPI.object.eventsub import (
              ChannelFollowEvent, ChannelSubscribeEvent, ChannelSubscriptionGiftEvent,
              ChannelSubscriptionMessageEvent, ChannelCheerEvent, ChannelRaidEvent,
              ChannelPointsCustomRewardRedemptionAddEvent,
          )
          from twitchAPI.type import (
              AuthScope, ChatEvent, TwitchAPIException, EventSubSubscriptionConflict,
              EventSubSubscriptionError, EventSubSubscriptionTimeout, TwitchBackendException,
          )
          from twitchAPI.chat import (
              Chat, EventData, ChatMessage, JoinEvent, JoinedEvent, ChatCommand, ChatUser,
          )
          PY
          touch "$out"
        '';

        # The canonical `anchoring` check proves rootPreamble and guardPreamble
        # behave. It does not prove that THIS repo's verbs call them, so this
        # one drives the real wrappers against a decoy carrying the marker files
        # a naive python anchor would accept, plus one filename this repo does
        # not contain.
        verbAnchoring =
          pkgs.runCommand "verb-anchoring-check" { nativeBuildInputs = lib.attrValues (wrappers pkgs); }
            ''
              set -euo pipefail
              mkdir decoy
              cd decoy
              printf 'import os\nx  =1\n' > bot.py
              printf 'import json\ny  =2\n' > sibling_only.py
              printf 'requests\n' > requirements.txt
              printf '{ description = "x"; outputs = _: { }; }\n' > flake.nix
              cp -r . ../decoy.orig

              # `--show-files` rather than a plain run: it prints the absolute
              # path of every file the verb would read, which is exactly the
              # anchoring question, and unlike a findings count it does not
              # change the day somebody fixes an F401. dev-lint cd's to
              # $REPO_ROOT and passes no path of its own once an argument is
              # given, so the listing is still whatever the anchor resolved to.
              dev-lint --show-files > files.log
              # Grep by NAME, not by directory. --show-files prints absolute
              # paths today, so a grep for "decoy" would work too -- but only for
              # as long as that stays true, and a verb that printed repo-relative
              # paths while standing in the decoy would sail straight through it.
              # sibling_only.py is the name that cannot be spelled both ways.
              if grep -q sibling_only files.log; then
                echo "dev-lint would have read the decoy" >&2
                cat files.log >&2
                exit 1
              fi
              # ...and it must have read SOMETHING: an empty listing also passes
              # the test above.
              if ! grep -qF -- ${lib.escapeShellArg "${self}"} files.log; then
                echo "dev-lint would have read neither the decoy nor this repo" >&2
                cat files.log >&2
                exit 1
              fi

              # Refusal, not silence, from both mutating verbs.
              if dev-fmt > fmt.log 2>&1; then
                echo "dev-fmt succeeded in a foreign tree; it must refuse" >&2
                exit 1
              fi
              if dev-run > run.log 2>&1; then
                echo "dev-run succeeded in a foreign tree; it must refuse" >&2
                exit 1
              fi

              # `*.log`, and every log file must match it -- a file named plainly
              # `log` is not excluded by `--exclude='*.log'` and fails this diff.
              diff -r --exclude='*.log' . ../decoy.orig
              touch "$out"
            '';
      };

      # >>>>> BEGIN CANONICAL MACHINERY v1 <<<<<
      # ======================================================================
      # Everything from the BEGIN sentinel above to the END sentinel on the last
      # line of this file is fleet-canonical text: the same bytes in every repo
      # that carries this flake style. That is a checkable claim, not a boast --
      #
      #   sed -n '/BEGIN CANONICAL MACHINERY v1/,$p' flake.nix | sha256sum
      #
      # prints the same digest in every repo, or one of them has been edited.
      # (`,$p`, not a range ending on the END sentinel: a range whose closing
      # pattern were spelled out here would terminate on this very comment.)
      # Nothing here names a repository, a language, a tool or a project file.
      # If you find such a name below, it is contamination: the fix is to move
      # it into the per-repo section above, never to special-case it here.
      #
      # This region READS exactly these names from the per-repo section:
      #   nixpkgs  self  lib  repoName  toolchain  nativeLibs  envVars
      #   commands  extraChecks
      # and DEFINES exactly these:
      #   systems  forAllSystems  ldPreamble  rootPreamble  guardPreamble
      #   wrappers  helpFor  anchorCheck
      # plus the four flake outputs apps / devShells / checks / formatter.
      # Anything else in scope is invisible to it. The types of those eight
      # inputs, and the shell variables this region exports into command texts,
      # are specified in INTERFACE.md, which travels with this block.
      #
      # To change behaviour here you change it in every repo at once and bump
      # the version in both sentinels. A local edit is a bug by construction:
      # the digest above stops matching, and -- because rootPreamble anchors on
      # flake.nix byte-identity -- an edited working tree also stops being
      # recognised by wrappers built from the previous revision.
      # ======================================================================

      # ---- systems policy: decided once for the whole fleet ----
      #
      # Read this list as "evaluated on three, built on one". That is what was
      # measured, and it is all it means:
      #   * `nix flake check --all-systems` passes, so every output attribute
      #     below EVALUATES on all three systems.
      #   * only x86_64-linux has ever been BUILT. The machine this was verified
      #     on has no aarch64 emulation -- no binfmt handler, and `extra-
      #     platforms` is x86-only -- so aarch64 cannot be built there at all.
      # It is not a statement that anything works on aarch64. Do not upgrade it
      # into one in a README.
      #
      # Evaluating all three is still worth its seconds, because the failure it
      # catches is an eval-time failure: a `pkgs.<attr>` that exists on Linux
      # and not on darwin (`stdenv.cc.cc.lib` is the usual one) throws during
      # evaluation, and `nix flake check` without --all-systems checks only the
      # current system and sails straight past it.
      #
      # x86_64-darwin is deliberately absent. nixpkgs 26.11 replaced that whole
      # attribute set with a `throw`. genAttrs is lazy, so plain `nix develop`
      # on Linux would not notice -- it detonates later, on the --all-systems
      # run this policy requires. Add it back only against a separate
      # nixpkgs-26.05-darwin input.
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      # Stand-in for flake-utils.lib.eachDefaultSystem. Passes `pkgs` rather
      # than a system string, because that is what every call site wants, and
      # keeps the system list in this file rather than in a second input's
      # hardcoded copy of it.
      forAllSystems = f: lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      # Prepend, never assign: a host LD_LIBRARY_PATH may be carrying something
      # the user needs, and clobbering it breaks binaries they launch from here.
      # Linux only -- on darwin the loader variable is DYLD_*, and exporting a
      # Linux-shaped value there is at best useless.
      #
      # `&&` short-circuits in Nix, so on darwin `nativeLibs pkgs` is never
      # forced. That is load-bearing for the systems policy above: it is what
      # lets a repo list Linux-only attrs in nativeLibs and still evaluate on
      # aarch64-darwin. Do not reorder the two operands.
      ldPreamble =
        pkgs:
        lib.optionalString (pkgs.stdenv.hostPlatform.isLinux && nativeLibs pkgs != [ ]) ''
          export LD_LIBRARY_PATH="${lib.makeLibraryPath (nativeLibs pkgs)}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        '';

      # Every command gets $SRC_ROOT and $REPO_ROOT. `nix run` and `nix develop`
      # both start in whatever directory they were invoked from, and no verb may
      # act on that directory -- these two are what it acts on instead.
      #
      # $SRC_ROOT is this flake's own source, snapshotted into the store when
      # the flake was evaluated. It is the one anchor that is always available:
      # `nix run /path/to/repo#lint` tells the running program nothing whatever
      # about /path/to/repo (flake refs are location-independent by design, and
      # there is no $FLAKE_DIR to read), so without `self` a wrapper invoked
      # that way has literally no way to name the repo it belongs to. Two
      # limitations worth knowing: it is read-only, being a store path, and in a
      # git checkout it contains only TRACKED files.
      #
      # $REPO_ROOT is the writable checkout when the caller is standing in one,
      # and $SRC_ROOT when they are not. Three things this deliberately is NOT:
      #
      #   * NOT `pwd`. A fallback to the caller's directory is how `fmt`
      #     rewrites a stranger's source tree and how `lint` prints "all checks
      #     passed" having read none of this repo.
      #   * NOT `git rev-parse --show-toplevel`. Run from inside some OTHER git
      #     repo it cheerfully answers with THAT repo's top level. It also needs
      #     git on PATH and a .git directory, so it fails on an export and in
      #     any wrapper whose toolchain omits git.
      #   * NOT an inherited $REPO_ROOT from the environment. The dev shell
      #     EXPORTS this variable, so honouring it would mean that running
      #     `nix run /path/to/B#fmt` from inside repo A's dev shell points B's
      #     formatter at A. An explicit path argument is how a caller overrides
      #     a verb's target; an ambient variable is how they do it by accident.
      #
      # Instead: walk up from $PWD and take the first ancestor that IS this
      # repo, proved by carrying a byte-identical flake.nix. A single tracked
      # filename, a marker directory, or a set of them is not proof -- sibling
      # repos in a fleet share those, and a decoy can be built to carry any list
      # of names you care to publish. The whole flake.nix is what distinguishes
      # repos, because description, toolchain and command map all differ, so the
      # whole flake.nix is what gets compared. Compared with bash's own
      # `$(<file)` rather than cmp or sha256sum, so the check depends on no
      # package at all -- pure builtins, correct even in a wrapper whose PATH
      # carries nothing but the repo's own toolchain.
      #
      # Consequence worth knowing: edit flake.nix and the dev-* wrappers in an
      # already-open `nix develop` stop recognising the tree, because they were
      # built from the previous flake.nix. That is a stale shell telling you so
      # -- re-enter it. `nix run` re-evaluates every time and never sees this.
      rootPreamble = ''
        SRC_ROOT=${lib.escapeShellArg "${self}"}
        export SRC_ROOT

        _dev_find_root() {
          local dir ref
          ref=$(<"$SRC_ROOT/flake.nix") || return 1
          dir=$(
            unset CDPATH
            cd -P -- "''${1:-.}" 2>/dev/null && pwd
          ) || return 1
          while [ -n "$dir" ]; do
            if [ -f "$dir/flake.nix" ] && [ "$(<"$dir/flake.nix")" = "$ref" ]; then
              printf '%s\n' "$dir"
              return 0
            fi
            dir=''${dir%/*}
          done
          return 1
        }

        REPO_ROOT="$(_dev_find_root "$PWD" || printf '%s\n' "$SRC_ROOT")"
        export REPO_ROOT
      '';

      # Wrappers only, not the shellHook -- an interactive shell has no business
      # carrying this function around. Any command text that writes files calls
      # it first, and it is the reason a mutating verb can fail loudly instead
      # of falling back to "well, the cwd then".
      #
      # The test is $REPO_ROOT != $SRC_ROOT, i.e. "rootPreamble found a real
      # checkout", not a permission or a store-path-prefix test. Both of those
      # answer a narrower question: a checkout may be read-only for unrelated
      # reasons, and a store path is not the only tree we must refuse to write.
      guardPreamble = ''
        need_writable_checkout() {
          if [ "$REPO_ROOT" != "$SRC_ROOT" ]; then
            return 0
          fi
          echo "''${0##*/}: this command rewrites files, so it needs a writable" >&2
          echo "checkout of this repo -- and standing in $PWD there is none: no" >&2
          echo "parent directory carries this flake's flake.nix. The only tree in" >&2
          echo "reach is the read-only store snapshot $SRC_ROOT, and rewriting" >&2
          echo "$PWD instead is exactly the bug this guard exists to prevent." >&2
          echo "cd into the repo (or \`nix develop\` it), or pass an explicit path." >&2
          exit 1
        }
      '';

      # One derivation per command, reused by both `apps` and the dev shell, so
      # the two can never diverge. `dev-` prefixed because a bare `test` binary
      # earlier on PATH would shadow the POSIX shell builtin and quietly break
      # every script in the repo that uses it.
      #
      # writeShellApplication, not writeShellScriptBin: it runs shellcheck at
      # BUILD time and sets `set -euo pipefail`, so an unquoted $@ or a silently
      # ignored failure is a `nix flake check` failure rather than a surprise in
      # front of an agent.
      wrappers =
        pkgs:
        lib.mapAttrs (
          name: cmd:
          pkgs.writeShellApplication {
            name = "dev-${name}";
            runtimeInputs = toolchain pkgs;
            runtimeEnv = envVars pkgs;
            meta.description = cmd.description;
            text = ''
              ${rootPreamble}
              ${guardPreamble}
              ${ldPreamble pkgs}
              ${cmd.text}
            '';
          }
        ) (commands pkgs);

      # `dev-help` is generated from the same attrset as everything else, so it
      # cannot describe a verb that does not exist or miss one that does. No
      # runtimeInputs: printing the map must work with nothing installed.
      helpFor =
        pkgs:
        let
          cmds = commands pkgs;
          names = lib.attrNames cmds;
          width = lib.foldl' (a: n: lib.max a (builtins.stringLength n)) 0 names;
          pad = n: n + lib.concatStrings (lib.genList (_: " ") (width - builtins.stringLength n));
          line = n: c: "  dev-${pad n}  ${c.description}";
        in
        pkgs.writeShellApplication {
          name = "dev-help";
          meta.description = "print this repo's command map (works offline)";
          text = ''
            cat <<'EOF'
            ${lib.concatStringsSep "\n" (lib.mapAttrsToList line cmds)}
            EOF
          '';
        };

      # The regression gate for rootPreamble and guardPreamble, which are the
      # two pieces of this flake that can silently damage a tree that is not
      # this repo. It tests the MECHANISM, not any verb, which is precisely what
      # makes it fleet-generic: it needs to know nothing about what this repo
      # does, only that the anchor resolves and the guard refuses.
      #
      # The decoy is a real directory carrying a real flake.nix that differs.
      # Marker-file anchors pass a decoy like this -- that is the whole point of
      # the probe -- and so does any anchor that trusts `pwd`. Probe 2 is the
      # other half, and without it a guard that refused everything would score a
      # perfect pass: a tree that IS byte-identical must still be adopted, or
      # every mutating verb in the repo is dead. Probe 3 pins the subdirectory
      # case, which is the normal one for an agent working inside a repo.
      #
      # A per-repo probe that drives the actual verbs is strictly better and
      # cannot live here -- it has to know which verb writes and which needs a
      # network. INTERFACE.md shows how to add one via `extraChecks`.
      anchorCheck =
        pkgs:
        pkgs.runCommand "anchor-check" { } ''
          set -euo pipefail

          # The two preambles under test, verbatim, in a file the probes source.
          # A quoted heredoc, so every $ below is the bash the wrappers see.
          cat > preamble.sh <<'CANONICAL_PREAMBLE_EOF'
          ${rootPreamble}
          ${guardPreamble}
          CANONICAL_PREAMBLE_EOF

          mkdir decoy
          printf '{\n  description = "a different repo";\n  outputs = _: { };\n}\n' > decoy/flake.nix
          printf 'do not touch me\n' > decoy/victim.txt
          cp -r decoy decoy.orig

          # ---- probe 1: a foreign tree must not be adopted ----
          if ! ( cd decoy && . ../preamble.sh && [ "$REPO_ROOT" = "$SRC_ROOT" ] ); then
            echo "anchor adopted a directory that is not this repo" >&2
            exit 1
          fi
          # In a subshell: need_writable_checkout ends in `exit`, which would
          # otherwise take this whole build down instead of failing a condition.
          if ( cd decoy && . ../preamble.sh && need_writable_checkout ) > guard.log 2>&1; then
            echo "need_writable_checkout accepted a tree that is not this repo" >&2
            exit 1
          fi
          if ! diff -r decoy decoy.orig; then
            echo "the probes modified the foreign tree" >&2
            exit 1
          fi

          # ---- probe 2: a byte-identical checkout must be adopted ----
          cp -r ${lib.escapeShellArg "${self}"} checkout
          chmod -R u+w checkout
          if ! ( cd checkout && . ../preamble.sh &&
                 [ "$REPO_ROOT" = "$(pwd -P)" ] && need_writable_checkout ); then
            echo "anchor refused a byte-identical checkout of this repo" >&2
            exit 1
          fi

          # ---- probe 3: from a subdirectory, still the checkout root ----
          mkdir -p checkout/probe3/deeper
          if ! ( cd checkout/probe3/deeper && . ../../../preamble.sh &&
                 [ "$REPO_ROOT" = "$(cd -P ../.. && pwd)" ] ); then
            echo "anchor did not walk up to the checkout root from a subdirectory" >&2
            exit 1
          fi

          touch "$out"
        '';
    in
    {
      # `nix flake show` -- the discovery entrypoint, and deliberately the whole
      # machine-facing contract: every app carries a meta.description, which
      # `nix flake show` prints inline and `nix flake show --json` exposes at
      # .apps.<system>.<name>.description. Pure evaluation, so an agent gets the
      # entire command map in one cheap call without reading a README.
      #
      # Do NOT invent a top-level output for this (`agentManifest`, `probeThing`
      # ...). Nix answers with `warning: unknown flake output '<name>'` on every
      # single `nix flake check`, forever.
      apps = forAllSystems (
        pkgs:
        lib.mapAttrs (name: cmd: {
          type = "app";
          program = "${(wrappers pkgs).${name}}/bin/dev-${name}";
          meta.description = cmd.description;
        }) (commands pkgs)
      );

      # `nix develop` -- the toolchain, plus a dev-<verb> for every app.
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = toolchain pkgs ++ lib.attrValues (wrappers pkgs) ++ [ (helpFor pkgs) ];

          env = envVars pkgs;

          # Natively-compiled extension modules are routinely built at -O0,
          # where glibc's _FORTIFY_SOURCE stops being a warning and becomes a
          # hard error.
          hardeningDisable = [ "fortify" ];

          shellHook = ''
            # mkShell inherits SOURCE_DATE_EPOCH=315532800 (1980-01-01) from
            # stdenv, and any wheel or zip built in here then dies with "ZIP does
            # not support timestamps before 1980".
            unset SOURCE_DATE_EPOCH

            # $REPO_ROOT and $SRC_ROOT are exported here as a convenience for
            # the human at the prompt. Every wrapper re-resolves them from
            # scratch and none of them reads these, on purpose: a stale value
            # exported by one repo's shell must never steer another repo's verb.
            ${rootPreamble}
            ${ldPreamble pkgs}

            # Nothing networked, nothing stateful and nothing interactive above
            # this line, and nothing below it either. No environment
            # bootstrapping, no dependency installation, no `read`, no
            # `exec $SHELL`. Bootstrapping in the hook makes a cold
            # `nix develop -c <anything>` start downloading before it runs
            # anything, on EVERY invocation -- the exact failure an unattended
            # agent cannot diagnose. That is what a `setup` verb is for.

            # The banner is interactive-only, and this guard is load-bearing:
            # shellHook output lands on the STDOUT of `nix develop -c <cmd>`, so
            # an unguarded echo corrupts anything parsing it
            # (`nix develop -c cat x.json | jq` fails to parse). $- is the only
            # reliable discriminator here -- it lacks `i` for `nix develop -c`
            # and has it at an interactive prompt. Do not test $PS1 (unset in
            # both) or $IN_NIX_SHELL (set in both). >&2 is the second layer, for
            # the case where a caller runs us on a pty.
            case $- in
              *i*) echo "${repoName} dev shell -- 'dev-help' for the command map" >&2 ;;
            esac
          '';
        };
      });

      # `nix flake check` -- honest by construction, and the only gate this
      # style has. `toolchain` realises the whole toolchain closure (so a typo'd
      # or currently-broken attr fails here, not halfway through a task) and
      # builds every wrapper, which runs shellcheck over every command text.
      # `anchoring` is the regression test described above.
      #
      # Repo-specific checks go in `extraChecks`, never here. They may not
      # shadow either canonical name: silently replacing `anchoring` with
      # something weaker is the exact failure this whole file exists to make
      # impossible, so a collision is an eval error with both names in it.
      #
      # NEVER add a check that always passes. An agent reads "all checks
      # passed!" as a signal, and a fake check makes `nix flake check` a liar.
      checks = forAllSystems (
        pkgs:
        let
          canonical = {
            toolchain =
              pkgs.runCommand "toolchain-check"
                {
                  nativeBuildInputs = toolchain pkgs ++ lib.attrValues (wrappers pkgs) ++ [ (helpFor pkgs) ];
                }
                ''
                  set -euo pipefail
                  dev-help > help.txt

                  # A while-read over a heredoc rather than `for x in <list>`,
                  # which is a bash syntax error when the list is empty -- and a
                  # repo with no verbs yet is a legitimate state.
                  while IFS= read -r verb; do
                    [ -n "$verb" ] || continue
                    command -v "dev-$verb" > /dev/null || {
                      echo "dev-$verb is not on PATH" >&2
                      exit 1
                    }
                    grep -q -- "dev-$verb" help.txt || {
                      echo "dev-$verb is missing from the dev-help map" >&2
                      exit 1
                    }
                  done <<'CANONICAL_VERBS_EOF'
                  ${lib.concatStringsSep "\n" (lib.attrNames (commands pkgs))}
                  CANONICAL_VERBS_EOF

                  touch "$out"
                '';
            anchoring = anchorCheck pkgs;
          };
          extra = extraChecks pkgs;
          clash = lib.intersectLists (lib.attrNames canonical) (lib.attrNames extra);
        in
        if clash != [ ] then
          throw "extraChecks must not redefine canonical checks: ${lib.concatStringsSep ", " clash}"
        else
          canonical // extra
      );

      # `nix fmt` -- formats the *Nix* in this repo; project code gets a `fmt`
      # verb. nixfmt-tree (the treefmt wrapper) rather than bare nixfmt, because
      # bare nixfmt tries to parse every path handed to it and fails on non-Nix
      # files. This file ships already formatted, so `nix fmt` is a no-op rather
      # than a diff across the fleet.
      #
      # This is the one verb here NOT anchored to $REPO_ROOT, and it cannot be:
      # `nix fmt` is nix's own verb, and nix -- not this flake -- decides which
      # paths the formatter receives, passing the cwd when the user names none.
      # A wrapper that overrode them would break `nix fmt path/to/one/file.nix`,
      # and it cannot tell that "." apart from the default. So `nix fmt` formats
      # where you stand, by design; the `fmt` verb is the anchored one.
      formatter = forAllSystems (pkgs: pkgs.nixfmt-tree);
    };
}
# >>>>> END CANONICAL MACHINERY v1 <<<<<
