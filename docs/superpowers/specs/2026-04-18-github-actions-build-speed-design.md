# GitHub Actions Build Speed Design

## Summary

This design changes the default CI release target from "build everything" to "publish the smallest package that is directly usable inside Termux". The default package must support:

- `flutter doctor`
- `flutter create`
- `flutter pub get`
- `flutter run -d web-server`
- `flutter build apk --debug`
- `flutter build apk --release --target-platform android-arm64`

Linux desktop support and all `--profile` support move to opt-in presets.

## Problem

The current GitHub Actions workflow is slow because it runs a cold-start, single-job, full release build every time:

- installs dependencies on a fresh `ubuntu-latest` runner
- downloads and unpacks Android NDK
- clones Flutter and runs `gclient sync`
- assembles the Termux sysroot
- builds Linux `debug`, `release`, and `profile`
- builds Android `release` and `profile`
- packages a full `.deb`

This is expensive on GitHub-hosted runners because there is no persistent machine-local checkout or build cache. The biggest improvement available is to compile fewer targets by default, then add limited caching for smaller reusable directories.

## Goals

- Make the default GitHub release build target the Termux-first package.
- Keep all work on GitHub-hosted runners only.
- Allow manual workflow runs to choose larger build scopes.
- Keep one main workflow entrypoint.
- Avoid changing package semantics accidentally for the default release.
- Keep packaging behavior explicit and predictable.

## Non-Goals

- No self-hosted runners.
- No artifact handoff pipeline that moves full engine source trees or full build outputs between jobs.
- No attempt to cache the full Flutter checkout or full `out/` tree on GitHub-hosted runners.
- No default Linux desktop or `--profile` support in the release package.

## User-Facing Build Presets

The workflow and build entrypoint will use these presets:

### `termux`

Default preset for `workflow_dispatch`.

Also the fixed preset for `push` on `v*` tags.

Purpose:

- publish the smallest package that satisfies the Termux-first requirements

Build scope:

- Linux debug host build needed for Flutter CLI artifacts
- `dart`
- `dartaotruntime`
- `frontend_server_aot`
- web runtime/cache artifacts needed by `flutter run -d web-server`
- VM snapshots required for `flutter build apk --debug`
- `impellerc`
- `const_finder`
- Android `release` `gen_snapshot`

Does not include:

- Linux desktop embedder artifacts
- Linux `release`
- Linux `profile`
- Android `profile`

Produces:

- `.deb`
- logs

### `termux-linux`

Purpose:

- extend `termux` with Linux desktop support, without profile support

Build scope:

- everything from `termux`
- Linux desktop artifacts for supported non-profile modes

Does not include:

- any `profile` targets

Produces:

- `.deb`
- logs

### `full-no-profile`

Purpose:

- build the non-profile superset for broader testing and packaging

Build scope:

- everything from `termux-linux`
- any remaining non-profile artifacts currently expected by packaging

Does not include:

- Linux `profile`
- Android `profile`

Produces:

- `.deb`
- logs

### `full`

Purpose:

- preserve the current all-target build as an explicit opt-in mode

Build scope:

- Linux `debug`
- Linux `release`
- Linux `profile`
- Android `release`
- Android `profile`
- all current CLI helper tools and packaging resources

Produces:

- `.deb`
- logs

## Workflow Design

Keep a single main workflow in `.github/workflows/build.yml`.

### Triggers

- `push` on `v*` tags:
  - fixed preset: `termux`
  - create GitHub Release
- `workflow_dispatch`:
  - selectable `preset`
  - default `preset`: `termux`

### Workflow Inputs

Keep `arch`, with `arm64` as the only current option.

Add `preset` with these values:

- `termux`
- `termux-linux`
- `full-no-profile`
- `full`
- `android-release-only`

`android-release-only` is a manual diagnostics/build-validation preset. It does not package a `.deb`.

### Release Rules

- Only tag-triggered `termux` builds publish a GitHub Release by default.
- Manual runs upload artifacts and logs.
- Manual runs for package-producing presets may upload the `.deb` as an artifact, but should not publish a GitHub Release automatically.

## Build Script Design

### New Entry Point

Add a new unified build entrypoint in `build.py`:

`build_selected --arch=arm64 --preset=<preset> --jobs=<n>`

`build_all()` remains as a compatibility wrapper and delegates to `build_selected(preset="full")`.

### Preset Resolution

Preset resolution belongs in Python, not in workflow YAML. The workflow passes the preset string; `build.py` maps it to a concrete list of targets and packaging behavior.

### Build Target Model

The selected build logic should reason in terms of independent target switches:

- Linux debug GN configure
- Linux release GN configure
- Linux profile GN configure
- core host build for Flutter CLI artifacts
- web runtime/cache artifact preparation
- Linux desktop embedder build
- `build_dart`
- `build_impellerc`
- `build_const_finder`
- Android release `configure_android`
- Android release `build_android_gen_snapshot`
- Android profile `configure_android`
- Android profile `build_android_gen_snapshot`
- package `.deb`

### Split Core Host Build From Linux Desktop Build

Current `build()` always builds both:

- `flutter`
- `flutter/shell/platform/linux:flutter_gtk`

This forces Linux desktop compilation even when the goal is only a Termux-first package.

Refactor this into two build steps:

- `build_flutter_core()`
  - builds only the host-side `flutter` target and any artifacts needed by CLI packaging
- `build_linux_desktop()`
  - builds `flutter_gtk`

`termux` skips `build_linux_desktop()` entirely.

## Packaging Design

### Default Packaging Direction

The package system should stop assuming that every preset has every resource.

The default published `.deb` is the `termux` package, not the full package.

### Resource Grouping

Restructure packaging resources in `package.yaml` into logical groups that map to presets:

- core Termux CLI resources
- web resources
- Android release resources
- Linux desktop resources
- profile resources

The implementation may express this either as explicit named sections or as resource lists built in `build.py`, but the grouping must be clear and stable.

### `termux` Package Must Include

- Flutter SDK files
- Dart SDK files
- `dart`
- `dartaotruntime`
- Dart snapshots needed by Flutter CLI
- `frontend_server_aot`
- web runtime/cache artifacts needed for `flutter run -d web-server`
- VM snapshots needed for `flutter build apk --debug`
- `impellerc`
- `const_finder`
- Android release `gen_snapshot`
- stamp files needed to suppress unwanted downloads
- `post_install.sh`

### `termux` Package Must Exclude

- Linux desktop runtime artifacts
- Linux `flutter_gtk`
- Linux desktop `gen_snapshot`
- Android profile `gen_snapshot`
- Linux profile resources

### Package Production Rules

- `termux`, `termux-linux`, `full-no-profile`, and `full` may produce `.deb` files.
- `android-release-only` must not call package creation.

## GitHub-Hosted Performance Design

### Dynamic Ninja Parallelism

Do not use the static `jobs = 24` default from `build.toml` on GitHub-hosted runners.

The workflow should compute a runner-appropriate job count from `nproc` and pass it explicitly to `build_selected`.

The goal is stable throughput, not maximum theoretical parallelism.

### Cache Only Smaller, Reusable Directories

Cache these:

- pip cache
- Dart/pub cache if used during dependency repair
- workspace-local Android NDK directory
- assembled `sysroot/`

Do not cache these:

- full `flutter/` checkout
- full `flutter/engine/src/out/` tree

Reason:

- on GitHub-hosted runners, those large caches are too expensive to upload/download reliably
- compile-less-by-default gives a better payoff than trying to persist the entire source/build graph

### NDK Path Strategy

The build system should prefer an environment-provided NDK path when present, then fall back to `build.toml`.

This allows the workflow to place the NDK in a cacheable workspace path instead of always unpacking to `/opt`.

### Sysroot Idempotence

Sysroot assembly should become skip-safe.

Add a manifest or stamp that captures:

- target arch
- sysroot package list from `build.toml`
- sysroot assembly code signature/version

If the restored `sysroot/` cache matches the manifest, `build.py sysroot` should skip download/extract work.

## Explicit Trade-Offs

- `gclient sync` remains expensive on GitHub-hosted runners and will still dominate cold builds.
- The main speed gain comes from not compiling Linux desktop and profile targets by default.
- The chosen design optimizes default release time first and preserves full builds as opt-in presets.
- This design favors predictable package behavior over maximum configurability in the first iteration.

## Files Expected To Change During Implementation

- `.github/workflows/build.yml`
- `.github/workflows/android-gen-snapshot.yml` or its responsibilities folded into `build.yml`
- `build.py`
- `package.yaml`
- optionally `package.py` if section selection needs minor support changes
- `build.toml`
- `sysroot.py`
- documentation files that describe default build/release behavior

## Acceptance Criteria

The implementation is complete when all of the following are true:

- tag-triggered releases build the `termux` preset by default
- manual runs can choose all approved presets
- the `termux` preset produces a `.deb`
- the published `termux` package is intended to support:
  - `flutter doctor`
  - `flutter create`
  - `flutter pub get`
  - `flutter run -d web-server`
  - `flutter build apk --debug`
  - `flutter build apk --release --target-platform android-arm64`
- Linux desktop and all profile support are opt-in only
- Linux desktop compilation is not part of the default `termux` preset
- GitHub workflow parallelism is computed dynamically instead of using the local-machine default
- small reusable caches are enabled
- sysroot work can be skipped on a valid cache hit
