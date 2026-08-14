{
  # Keep this line accurate and one line long: `nix flake metadata` prints it,
  # and it is the first thing a cold agent learns about the repo.
  description = "TwitchToREST -- Quart web service that subscribes to Twitch EventSub/chat and forwards redeems, subs, follows, cheers and raids to a REST endpoint. Run `nix flake show` for the command map.";

  # nixpkgs is the only input, on purpose.
  #
  # flake-utils would buy exactly one thing here -- eachDefaultSystem -- which is
  # the three-line genAttrs below. In exchange it costs a second lock node in
  # every repo (flake-utils transitively pulls `systems`, so really two), a
  # second upstream that can break one repo and not the other forty, and a
  # hardcoded system list this repo cannot edit. That list is currently broken:
  # it still contains x86_64-darwin, which now throws (see `systems` below).
  #
  # nixos-unstable is the same channel the author's own NixOS config tracks, so
  # `nix develop` here and `nixos-rebuild` there resolve the same store paths and
  # share one cache.
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    # `...` rather than a closed { self, nixpkgs }: adding a second input later
    # would otherwise fail with "called with unexpected argument 'self'".
    { nixpkgs, ... }:
    let
      lib = nixpkgs.lib;

      # x86_64-darwin is deliberately absent. nixpkgs 26.11 replaced that whole
      # attribute set with `throw "Nixpkgs 26.11 has dropped support for
      # x86_64-darwin"`. genAttrs is lazy, so plain `nix develop` on Linux would
      # not notice -- it detonates later, on `nix flake check --all-systems`.
      # Add it back only against a separate nixpkgs-26.05-darwin input.
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      # Stand-in for flake-utils.lib.eachDefaultSystem. Passes `pkgs` rather than
      # a system string, because that is what every call site below wants.
      forAllSystems = f: lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      # ======================================================================
      # PER-REPO BLOCK 1 -- the toolchain
      # ======================================================================
      # Everything the commands below need. `nix flake check` realises this
      # closure, so a typo'd attr name fails at the flake gate instead of
      # surfacing as "command not found" halfway through a task.
      #
      # Explicit `pkgs.foo`, never `with pkgs; [ ... ]`: when an attr disappears
      # in a nixpkgs bump, `with` reports a bare undefined identifier with no
      # hint of which set it came from, and the name is not greppable.
      #
      # Pin language runtimes by MAJOR (python313), never by rolling alias
      # (python3). An alias that moves under you invalidates every environment
      # in the fleet on the same afternoon -- and the current default is already
      # 3.14 territory, where several of the deps below have no wheels.
      #
      # This repo ships NO manifest: no requirements.txt, no pyproject.toml, no
      # setup.py, no Dockerfile, no CI workflow. The dependency set below was
      # derived by reading every `import` in every tracked .py file. The
      # third-party ones are exactly: requests, quart, passlib, twitchAPI (plus
      # hypercorn, which is the ASGI server quart's `app.run()` drives). If you
      # add an import to the source, add it here too -- there is no other place
      # in this repo that records it.
      #
      # All five exist in nixpkgs, so they come from the store via
      # `withPackages` and there is deliberately NO uv, NO pip and NO `setup`
      # verb: `nix develop` here works with the network unplugged. Do not "fix"
      # this by adding uv and a requirements.txt -- that reintroduces two
      # Pythons (store vs .venv) with no way to tell which one is live.
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
      # Empty, and that is the honest answer for this repo. This list exists for
      # manylinux wheels and node prebuilds, whose .so files are dlopened at
      # runtime so neither patchelf nor the nix linker ever sees them. Every
      # dependency here comes from nixpkgs instead, already correctly linked,
      # and all five are pure Python anyway.
      #
      # Keep it empty unless you actually hit a `cannot open shared object file`
      # -- LD_LIBRARY_PATH is a blunt instrument, and while it is empty the
      # generic machinery below leaves the ambient value untouched.
      nativeLibs = pkgs: [ ];

      # ======================================================================
      # PER-REPO BLOCK 3 -- constant environment variables
      # ======================================================================
      # Only values that are constants belong here. Anything that must READ an
      # existing value (LD_LIBRARY_PATH), UNSET something (SOURCE_DATE_EPOCH) or
      # touch the work tree goes in the shellHook further down.
      #
      # This attrset is applied to BOTH surfaces -- the dev shell and every
      # `nix run` wrapper -- so a command cannot behave differently depending on
      # how it was invoked.
      envVars = pkgs: {
        # The interpreter is read-only in the store, so every __pycache__ this
        # repo would produce lands in the work tree instead. The modules here are
        # small and re-parsing them costs nothing; not writing them keeps `git
        # status` clean, which matters more when an agent is deciding what to
        # commit.
        PYTHONDONTWRITEBYTECODE = "1";
        # Unbuffered stdout/stderr. main.py logs from a background thread while
        # the Quart server holds the main loop; with the default block buffering
        # an agent capturing output through a pipe sees nothing until the process
        # dies, which reads as a hang.
        PYTHONUNBUFFERED = "1";
      };

      # ======================================================================
      # PER-REPO BLOCK 4 -- the command map
      # ======================================================================
      # THE single source of truth. It generates `apps` (so `nix run .#run`
      # works), the `dev-*` wrappers on PATH inside the shell, and `dev-help`.
      # Nothing is written twice, so `nix flake show` can never disagree with
      # what `dev-lint` actually runs.
      #
      # Fixed house vocabulary -- setup, build, test, lint, fmt, run -- and a
      # verb the repo has no meaning for is OMITTED, because absence is
      # information and a stub that echoes "not applicable" turns the command
      # map into a liar. So, for this repo:
      #
      #   no `setup`  every dependency comes from nixpkgs; nothing to bootstrap
      #   no `build`  it is a service run from source, there is no artifact
      #   no `test`   there is no test suite. POST_test.py and REST_test.py are
      #               named like tests but are neither: POST_test.py fires a live
      #               HTTP POST at localhost:5001 from module level, and
      #               REST_test.py is a throwaway listener that answers it. No
      #               pytest, no unittest, no assertions, nothing to collect.
      commands = pkgs: {
        run = {
          # main.py's first statements are `from some_secrets import *` and
          # `from config import *`. Both files are in .gitignore, so a fresh
          # clone cannot start -- it dies on ModuleNotFoundError before any of
          # this flake's work is visible. Check for them up front so the failure
          # names the actual problem instead of a stack trace.
          #
          # NEEDS STDIN, and no flag can turn that off: main.py:611 blocks on
          # `input('Please input a inital password')` during startup, and
          # main.py:666 then sits in an `input()` command loop. Under `nix run`
          # with stdin closed that is an unkillable-looking hang, so an agent
          # must either pipe answers in (`nix run .#run < answers.txt`) or leave
          # this verb to a human. Fixing it means adding a non-interactive path
          # to main.py -- do not paper over it here.
          description = "start the bot + auth server -- INTERACTIVE, prompts on stdin; needs the gitignored config.py + some_secrets.py";
          text = ''
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
            # cd, unlike every other command in this map, because main.py hardcodes
            # relative paths -- `os.makedirs('data')`, `open('data/pws.json')`. Run
            # it from anywhere else and it silently forks a second state directory
            # under the caller's cwd.
            cd "$REPO_ROOT"
            exec python main.py "$@"
          '';
        };
        lint = {
          # There is no ruff config in the repo, so this runs ruff's default
          # rule selection. It reports 104 pre-existing findings today (12 of
          # them F401 unused-import) and therefore exits 1 -- that is the code,
          # not the flake. Do not add --exit-zero or a permissive config to make
          # it green; either fix the findings or leave the signal honest.
          description = "ruff check";
          text = ''ruff check "$@"'';
        };
        fmt = {
          description = "ruff format (rewrites files)";
          text = ''ruff format "$@"'';
        };
      };

      # ======================================================================
      # GENERIC MACHINERY -- byte-identical in all 41 repos, do not edit
      # ======================================================================

      # Prepend, never assign: a host LD_LIBRARY_PATH may be carrying something
      # the user needs, and clobbering it breaks binaries they launch from here.
      # Linux only -- on darwin the loader variable is DYLD_*, and exporting a
      # Linux-shaped value there is at best useless.
      ldPreamble =
        pkgs:
        lib.optionalString (pkgs.stdenv.hostPlatform.isLinux && nativeLibs pkgs != [ ]) ''
          export LD_LIBRARY_PATH="${lib.makeLibraryPath (nativeLibs pkgs)}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        '';

      # Every command gets $REPO_ROOT. `nix run` and `nix develop` both start in
      # whatever directory they were invoked from, so a bare `data/` silently
      # forks a second environment as soon as an agent works from a subdirectory.
      # Note we do NOT cd there: commands act on the caller's cwd on purpose.
      rootPreamble = ''
        REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
        export REPO_ROOT
      '';

      # One derivation per command, reused by both `apps` and the dev shell, so
      # the two can never diverge. `dev-` prefixed because a bare `test` binary
      # earlier on PATH would shadow the POSIX shell builtin and quietly break
      # every script in the repo that uses it.
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
              ${ldPreamble pkgs}
              ${cmd.text}
            '';
          }
        ) (commands pkgs);

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
    in
    {
      # `nix flake show` -- the discovery entrypoint, and deliberately the whole
      # machine-facing contract: every app carries a meta.description, which
      # `nix flake show` prints inline and `nix flake show --json` exposes at
      # .apps.<system>.<name>.description. Pure evaluation, so an agent gets the
      # entire command map in one cheap call without reading a README -- which
      # matters here, because this repo has no README at all.
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

          # Some C extensions and node-gyp addons compile at -O0, where glibc's
          # _FORTIFY_SOURCE becomes a hard error instead of a warning.
          hardeningDisable = [ "fortify" ];

          shellHook = ''
            # mkShell inherits SOURCE_DATE_EPOCH=315532800 (1980-01-01) from
            # stdenv, and any wheel or zip built in here then dies with "ZIP does
            # not support timestamps before 1980".
            unset SOURCE_DATE_EPOCH

            ${rootPreamble}
            ${ldPreamble pkgs}

            # Nothing networked, nothing stateful and nothing interactive above
            # this line, and nothing below it either. No venv creation, no
            # `pip install`, no `read`, no `exec $SHELL`. Bootstrapping in the
            # hook makes a cold `nix develop -c python main.py` start
            # downloading before it runs anything, on EVERY invocation -- the
            # exact failure an unattended agent cannot diagnose.

            # The banner is interactive-only, and this guard is load-bearing:
            # shellHook output lands on the STDOUT of `nix develop -c <cmd>`, so
            # an unguarded echo corrupts anything parsing it
            # (`nix develop -c cat x.json | jq` fails to parse). $- is the only
            # reliable discriminator here -- it lacks `i` for `nix develop -c`
            # and has it at an interactive prompt. Do not test $PS1 (unset in
            # both) or $IN_NIX_SHELL (set in both). >&2 is the second layer, for
            # the case where a caller runs us on a pty.
            case $- in
              *i*) echo "TwitchToREST dev shell -- 'dev-help' for the command map" >&2 ;;
            esac
          '';
        };
      });

      # `nix flake check` -- honest by construction. It realises the toolchain
      # closure (so a typo'd or currently-broken attr fails here) and builds
      # every wrapper, which runs shellcheck over every command text. Add real
      # test derivations beside it. NEVER add a check that always passes: an
      # agent reads "all checks passed!" as a signal, and a fake check makes
      # `nix flake check` a liar.
      checks = forAllSystems (pkgs: {
        toolchain =
          pkgs.runCommand "toolchain-check"
            {
              nativeBuildInputs = toolchain pkgs ++ lib.attrValues (wrappers pkgs);
            }
            ''
              for verb in ${lib.escapeShellArgs (lib.attrNames (commands pkgs))}; do
                command -v "dev-$verb" > /dev/null || {
                  echo "dev-$verb is not on PATH" >&2
                  exit 1
                }
              done
              touch "$out"
            '';

        # A real check, not a tautology: it imports every third-party module the
        # tracked source imports. If a nixpkgs bump renames an attr or twitchAPI
        # moves a submodule again (the 3.x -> 4.x reshuffle is why the import
        # paths below look the way they do), `nix flake check` fails here rather
        # than main.py failing on a stream day.
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
      });

      # `nix fmt` -- formats the *Nix* in this repo; project code is `dev-fmt`.
      # nixfmt-tree (the treefmt wrapper) rather than bare nixfmt, because bare
      # nixfmt tries to parse every path handed to it and fails on non-Nix files.
      # This file ships already formatted, so `nix fmt` is a no-op rather than a
      # diff in 41 repos.
      formatter = forAllSystems (pkgs: pkgs.nixfmt-tree);
    };
}
