# GitHub Actions Build Speed Design

## Summary

This design makes GitHub Actions a manual-release pipeline only.

The workflow must:

- trigger only by `workflow_dispatch`
- take the Flutter version only from `build.toml`
- publish a GitHub Release automatically after a successful manual run
- use the exact `build.toml` version string as the GitHub Release tag
- keep the default package focused on Termux-first behavior

The default package must support:

- `flutter doctor`
- `flutter create`
- `flutter pub get`
- `flutter run -d web-server`
- `flutter build apk --debug`
- `flutter build apk --release --target-platform android-arm64`

Linux desktop support and all `--profile` support remain opt-in presets.

## Problem

The previous CI design had too many moving parts:

- both tag-triggered and manual-triggered release behavior
- a special `android-release-only` preset that does not match the main packaging goal
- patch selection tied to `patches/<flutter-tag>/`
- duplicated version concepts between workflow release behavior and repository config

This adds maintenance overhead without helping the actual release flow you want:

- edit `build.toml`
- manually run the workflow
- get a `.deb`
- publish that exact version as a Release

## Goals

- Make `build.toml` the single source of truth for the Flutter version.
- Remove `push tag` release behavior entirely.
- Keep only manual workflow execution.
- Automatically publish a GitHub Release after a successful manual run.
- Use the exact `build.toml` version string as the Release tag, without adding `v`.
- Remove `android-release-only`.
- Stop selecting patches by Flutter tag directory.
- Flatten `patches/` so the four current patches always apply from one place.

## Non-Goals

- No workflow input for version selection.
- No patch directory selection by Flutter version.
- No self-hosted runner design.
- No extra CI-only preset that bypasses normal packaging.

## User-Facing Build Presets

The workflow and build entrypoint will use these presets:

### `termux`

Default preset for `workflow_dispatch`.

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
- GitHub Release

### `termux-linux`

Purpose:

- extend `termux` with Linux desktop support, without profile support

Build scope:

- everything from `termux`
- Linux desktop artifacts for supported non-profile modes

Produces:

- `.deb`
- logs
- GitHub Release

### `full-no-profile`

Purpose:

- build the non-profile superset for broader testing and packaging

Build scope:

- everything from `termux-linux`
- any remaining non-profile artifacts currently expected by packaging

Produces:

- `.deb`
- logs
- GitHub Release

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
- GitHub Release

### Removed preset

`android-release-only` is removed. It no longer matches the main release model and should not appear in workflow inputs or Python preset resolution.

## Workflow Design

Keep a single main workflow in `.github/workflows/build.yml`.

### Triggers

Only:

- `workflow_dispatch`

Remove:

- `push` on tags

### Workflow Inputs

Keep:

- `arch`
- `preset`

Do not add a version input. The workflow must read version information from `build.toml`.

### Version Source

The workflow must parse `build.toml` and derive:

- Flutter checkout version
- artifact naming
- GitHub Release tag
- GitHub Release name

If `build.toml` contains:

```toml
[flutter]
tag = "3.41.5"
```

Then:

- Flutter checkout uses `3.41.5`
- GitHub Release tag is `3.41.5`
- Release name also uses `3.41.5`

No automatic `v` prefix should be added.

### Release Rules

Every successful manual run for a package-producing preset should:

- upload artifacts
- force-update the Git tag matching the `build.toml` version to the current workflow commit
- publish or update the GitHub Release using that exact tag

This makes the manual workflow the only release mechanism.

## Build Script Design

### New Entry Point

Keep the unified build entrypoint in `build.py`:

`build_selected --arch=arm64 --preset=<preset> --jobs=<n>`

`build_all()` remains a compatibility wrapper and delegates to `build_selected(preset="full")`.

### Preset Resolution

Preset resolution belongs in Python, not in workflow YAML.

Keep:

- `termux`
- `termux-linux`
- `full-no-profile`
- `full`

Remove:

- `android-release-only`

### Flutter Version Source

`Build.__init__()` may continue reading `[flutter].tag` from `build.toml`.

That value is now the authoritative source for:

- clone tag
- package version
- release tag

The workflow must not try to override it with a separate user-provided version input.

## Patch Layout Design

Patch selection must no longer depend on the Flutter tag.

### Old layout

```text
patches/3.41.5/engine.patch
patches/3.41.5/dart.patch
patches/3.41.5/skia.patch
patches/3.41.5/flutter_sdk_arm64_default.patch
```

### New layout

```text
patches/engine.patch
patches/dart.patch
patches/skia.patch
patches/flutter_sdk_arm64_default.patch
```

### Implementation rule

In `build.py`, patch base resolution must change from:

- `patches/<self.tag>/...`

to:

- `patches/...`

The four current patch files are treated as version-agnostic until proven otherwise.

Remove old versioned patch directories from the repository once the root-level files are in place.

## Packaging Design

The default published `.deb` remains the `termux` package, not the full package.

The package system should continue grouping resources so `termux` includes:

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

The default package should still exclude Linux desktop and profile-only payloads.

## GitHub-Hosted Performance Design

The workflow should keep:

- dynamic Ninja job count
- pip cache from `actions/setup-python`

The workflow should not rely on:

- push-tag based release flow
- extra version inputs
- Android/sysroot cache restore logic if it provides little real benefit

The main speed win still comes from compiling fewer targets by default, not from large cache tricks.

## Explicit Trade-Offs

- Repeated manual runs for the same `build.toml` version will update the same Git tag and GitHub Release.
- Flattening `patches/` means patch compatibility is now enforced operationally, not by directory structure.
- This simplifies maintenance, but if a future Flutter version breaks patch compatibility, the break will surface during patch apply or build time.

## Files Expected To Change During Implementation

- `.github/workflows/build.yml`
- `build.py`
- `build.toml`
- `package.yaml` only if preset references or packaging metadata need cleanup
- `patches/engine.patch`
- `patches/dart.patch`
- `patches/skia.patch`
- `patches/flutter_sdk_arm64_default.patch`
- old versioned patch files under `patches/3.35.0/` and `patches/3.41.5/`
- tests covering workflow inputs, release behavior, and preset resolution
- docs that still describe tag-triggered release behavior

## Acceptance Criteria

The implementation is complete when all of the following are true:

- `.github/workflows/build.yml` only supports `workflow_dispatch`
- the workflow no longer supports `push` on tags
- the workflow input options no longer include `android-release-only`
- the workflow reads the release version from `build.toml`
- the workflow publishes GitHub Releases using the exact `build.toml` Flutter tag string, without adding `v`
- `build.py` no longer resolves patches through `patches/<flutter-tag>/`
- the repository stores the four active patch files directly under `patches/`
- old versioned patch directories are removed
- the default `termux` package is still aimed at:
  - `flutter doctor`
  - `flutter create`
  - `flutter pub get`
  - `flutter run -d web-server`
  - `flutter build apk --debug`
  - `flutter build apk --release --target-platform android-arm64`
