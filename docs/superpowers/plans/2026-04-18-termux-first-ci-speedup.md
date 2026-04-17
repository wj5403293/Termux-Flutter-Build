# Termux-First CI Speedup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 GitHub Actions 默认发布改成面向 Termux 的最小可用 `.deb`，默认支持 `flutter doctor`、`flutter create`、`flutter pub get`、`flutter run -d web-server`、`flutter build apk --debug`、`flutter build apk --release --target-platform android-arm64`，并把 Linux/profile 变成可选 preset。

**Architecture:** 在 `build.py` 中新增可测试的 preset 解析与构建编排入口，把当前“硬编码全量构建”拆成“core host build / linux desktop build / android release/profile build / package sections”几个开关。`package.yaml` 保持扁平资源表，但通过新增资源和 `build.py` 中的 section 列表实现不同 preset 的打包。`build.yml` 只负责收集输入、恢复小型缓存、计算 jobs、调用 `build_selected`，不再自己持有复杂构建逻辑。

**Tech Stack:** Python 3.11、`unittest`、GitHub Actions、PyYAML、Flutter Engine/Ninja

---

## File Structure

- `.github/workflows/build.yml`
  - 主 workflow，新增 `preset` 输入、动态 `jobs`、缓存和条件发布。
- `.github/workflows/android-gen-snapshot.yml`
  - 旧专项 workflow；本次实现后删除，避免双份逻辑漂移。
- `build.py`
  - 新增 `BuildPreset` 数据模型、`resolve_preset()`、`build_selected()`、`prepare_web_sdk()`、`build_flutter_core()`、`build_linux_desktop()`，并让 `build_all()` 退化成 `full` 包装器。
- `package.yaml`
  - 拆分 `artifacts`，新增 `flutter_web_sdk`，让 `termux` 预设能只打入必须资源。
- `sysroot.py`
  - 新增 manifest/stamp 机制，命中缓存时跳过下载解包。
- `build.toml`
  - 保留默认 NDK 路径，但实现上允许 `ANDROID_NDK` 覆盖，并补充注释说明 GitHub Actions 会通过环境变量覆盖。
- `tests/test_build_presets.py`
  - 测 preset 解析和 package section 集合。
- `tests/test_build_flow.py`
  - 测 core build / linux desktop build 命令拆分，以及 `build_selected()` 的调用顺序。
- `tests/test_package_manifest.py`
  - 测 `package.yaml` 中新增资源与拆分后的资源名。
- `tests/test_sysroot_cache.py`
  - 测 sysroot manifest 生成和缓存命中跳过逻辑。
- `tests/test_workflow_config.py`
  - 解析 YAML，测 workflow 默认 preset、preset 选项和缓存/发布行为的关键字段。
- `README.md`
  - 更新默认发布行为为 `termux`，保留 Linux/profile 说明为可选能力。
- `README_EN.md`
  - 同步英文说明。

### Task 1: 建立可测试的 preset 模型

**Files:**
- Create: `tests/test_build_presets.py`
- Modify: `build.py`
- Test: `tests/test_build_presets.py`

- [ ] **Step 1: 先写失败测试，锁定 preset 解析的公开接口**

```python
import unittest

from build import BuildPreset, resolve_preset


class ResolvePresetTests(unittest.TestCase):
    def test_termux_preset_keeps_web_and_android_release_only(self):
        plan = resolve_preset("termux")

        self.assertIsInstance(plan, BuildPreset)
        self.assertTrue(plan.prepare_web_sdk)
        self.assertTrue(plan.build_android_release)
        self.assertTrue(plan.package_deb)
        self.assertFalse(plan.build_linux_desktop)
        self.assertFalse(plan.build_linux_profile)
        self.assertFalse(plan.build_android_profile)
        self.assertIn("flutter_web_sdk", plan.package_sections)
        self.assertNotIn("flutter_linux_gtk_profile", plan.package_sections)

    def test_android_release_only_skips_packaging(self):
        plan = resolve_preset("android-release-only")

        self.assertTrue(plan.build_android_release)
        self.assertFalse(plan.package_deb)
        self.assertEqual(plan.package_sections, [])

    def test_unknown_preset_raises_value_error(self):
        with self.assertRaises(ValueError):
            resolve_preset("nope")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认它因为接口缺失而失败**

Run: `python -m unittest tests.test_build_presets -v`

Expected: FAIL，报错包含 `cannot import name 'BuildPreset'` 或 `cannot import name 'resolve_preset'`

- [ ] **Step 3: 在 `build.py` 中加入最小实现，让 preset 逻辑从 workflow YAML 下沉到 Python**

```python
from dataclasses import dataclass


TERMUX_PACKAGE_SECTIONS = [
    "flutter",
    "flutter_gpu",
    "sky_engine",
    "dart_sdk",
    "dart_bin",
    "dart_snapshots",
    "dartaotruntime",
    "dartdev_aot",
    "frontend_server_aot",
    "flutter_web_sdk",
    "engine_common_artifacts",
    "flutter_patched_sdk",
    "flutter_patched_sdk_product",
    "executable",
    "profile",
    "stamps",
    "android_gen_snapshot_arm64",
    "vm_snapshots",
    "post_install",
]

TERMUX_LINUX_EXTRA = [
    "linux_gen_snapshot",
    "flutter_linux_gtk",
    "flutter_linux_gtk_release",
]

FULL_PROFILE_EXTRA = [
    "flutter_linux_gtk_profile",
    "android_gen_snapshot_arm64_profile",
]


@dataclass(frozen=True)
class BuildPreset:
    name: str
    package_sections: list[str]
    package_deb: bool
    prepare_web_sdk: bool
    configure_linux_debug: bool
    build_flutter_core: bool
    build_dart: bool
    build_impellerc: bool
    build_const_finder: bool
    build_linux_desktop: bool
    build_linux_release: bool
    build_linux_profile: bool
    build_android_release: bool
    build_android_profile: bool


PRESETS = {
    "termux": BuildPreset(
        name="termux",
        package_sections=TERMUX_PACKAGE_SECTIONS,
        package_deb=True,
        prepare_web_sdk=True,
        configure_linux_debug=True,
        build_flutter_core=True,
        build_dart=True,
        build_impellerc=True,
        build_const_finder=True,
        build_linux_desktop=False,
        build_linux_release=False,
        build_linux_profile=False,
        build_android_release=True,
        build_android_profile=False,
    ),
    "termux-linux": BuildPreset(
        name="termux-linux",
        package_sections=TERMUX_PACKAGE_SECTIONS + TERMUX_LINUX_EXTRA,
        package_deb=True,
        prepare_web_sdk=True,
        configure_linux_debug=True,
        build_flutter_core=True,
        build_dart=True,
        build_impellerc=True,
        build_const_finder=True,
        build_linux_desktop=True,
        build_linux_release=True,
        build_linux_profile=False,
        build_android_release=True,
        build_android_profile=False,
    ),
    "full-no-profile": BuildPreset(
        name="full-no-profile",
        package_sections=TERMUX_PACKAGE_SECTIONS + TERMUX_LINUX_EXTRA,
        package_deb=True,
        prepare_web_sdk=True,
        configure_linux_debug=True,
        build_flutter_core=True,
        build_dart=True,
        build_impellerc=True,
        build_const_finder=True,
        build_linux_desktop=True,
        build_linux_release=True,
        build_linux_profile=False,
        build_android_release=True,
        build_android_profile=False,
    ),
    "full": BuildPreset(
        name="full",
        package_sections=TERMUX_PACKAGE_SECTIONS + TERMUX_LINUX_EXTRA + FULL_PROFILE_EXTRA,
        package_deb=True,
        prepare_web_sdk=True,
        configure_linux_debug=True,
        build_flutter_core=True,
        build_dart=True,
        build_impellerc=True,
        build_const_finder=True,
        build_linux_desktop=True,
        build_linux_release=True,
        build_linux_profile=True,
        build_android_release=True,
        build_android_profile=True,
    ),
    "android-release-only": BuildPreset(
        name="android-release-only",
        package_sections=[],
        package_deb=False,
        prepare_web_sdk=False,
        configure_linux_debug=False,
        build_flutter_core=False,
        build_dart=False,
        build_impellerc=False,
        build_const_finder=False,
        build_linux_desktop=False,
        build_linux_release=False,
        build_linux_profile=False,
        build_android_release=True,
        build_android_profile=False,
    ),
}


def resolve_preset(name: str) -> BuildPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"unknown preset: {name}") from exc
```

- [ ] **Step 4: 重新运行测试，确认 preset 解析通过**

Run: `python -m unittest tests.test_build_presets -v`

Expected: PASS，输出 `Ran 3 tests`

- [ ] **Step 5: 提交这一小步**

```bash
git add build.py tests/test_build_presets.py
git commit -m "test: add preset resolution model"
```

### Task 2: 拆开 core host build / Linux desktop build，并引入 `build_selected()`

**Files:**
- Create: `tests/test_build_flow.py`
- Modify: `build.py`
- Test: `tests/test_build_flow.py`

- [ ] **Step 1: 先写失败测试，锁定命令拆分和编排顺序**

```python
import unittest
from pathlib import Path
from unittest.mock import patch

import build


class CommandBuilderTests(unittest.TestCase):
    def test_build_flutter_core_omits_flutter_gtk_target(self):
        runner = build.Build.__new__(build.Build)
        runner.jobs = 8

        with patch("build.subprocess.run") as run:
            runner.build_flutter_core("arm64", "debug", root="/tmp/flutter", jobs=8)

        cmd = run.call_args.args[0]
        self.assertIn("flutter", cmd)
        self.assertNotIn("flutter/shell/platform/linux:flutter_gtk", cmd)

    def test_build_linux_desktop_only_builds_flutter_gtk(self):
        runner = build.Build.__new__(build.Build)
        runner.jobs = 8

        with patch("build.subprocess.run") as run:
            runner.build_linux_desktop("arm64", "debug", root="/tmp/flutter", jobs=8)

        cmd = run.call_args.args[0]
        self.assertIn("flutter/shell/platform/linux:flutter_gtk", cmd)
        self.assertNotIn("dartaotruntime_product", cmd)


class RecordingBuild(build.Build):
    def __init__(self):
        self.events = []
        self.release = Path(".")
        self.tag = "3.41.5"

    def configure(self, arch, mode, **kwargs):
        self.events.append(("configure", mode))

    def build_flutter_core(self, arch, mode, **kwargs):
        self.events.append(("core", mode))

    def build_linux_desktop(self, arch, mode, **kwargs):
        self.events.append(("linux", mode))

    def build_dart(self, arch, mode, **kwargs):
        self.events.append(("dart", mode))

    def build_impellerc(self, arch, mode, **kwargs):
        self.events.append(("impellerc", mode))

    def build_const_finder(self, arch, mode, **kwargs):
        self.events.append(("const_finder", mode))

    def prepare_web_sdk(self, **kwargs):
        self.events.append(("web", "prepare"))

    def configure_android(self, arch="arm64", mode="release", **kwargs):
        self.events.append(("configure_android", mode))

    def build_android_gen_snapshot(self, arch="arm64", mode="release", **kwargs):
        self.events.append(("android", mode))

    def debuild(self, arch, output=None, root=None, section=None, **kwargs):
        self.events.append(("package", tuple(section or [])))

    def output(self, arch):
        return Path("release/flutter_test.deb")


class BuildSelectedTests(unittest.TestCase):
    def test_termux_build_selected_skips_linux_desktop_and_profile(self):
        runner = RecordingBuild()
        runner.build_selected(arch="arm64", preset="termux", jobs=4)

        self.assertIn(("web", "prepare"), runner.events)
        self.assertIn(("core", "debug"), runner.events)
        self.assertIn(("android", "release"), runner.events)
        self.assertNotIn(("linux", "debug"), runner.events)
        self.assertNotIn(("configure_android", "profile"), runner.events)
        self.assertTrue(any(event[0] == "package" for event in runner.events))

    def test_android_release_only_skips_packaging(self):
        runner = RecordingBuild()
        runner.build_selected(arch="arm64", preset="android-release-only", jobs=4)

        self.assertIn(("android", "release"), runner.events)
        self.assertFalse(any(event[0] == "package" for event in runner.events))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认因为新接口还不存在而失败**

Run: `python -m unittest tests.test_build_flow -v`

Expected: FAIL，报错包含 `Build` 没有 `build_flutter_core`、`build_linux_desktop` 或 `build_selected`

- [ ] **Step 3: 在 `build.py` 中做最小实现，保持旧接口可兼容**

```python
def build_flutter_core(self, arch: str, mode: str, root: str = None, jobs: int = None):
    root = root or self.root
    jobs = jobs or self.jobs
    cmd = ["ninja", "-C", utils.target_output(root, arch, mode), "flutter"]
    if jobs:
        cmd.append(f"-j{jobs}")
    subprocess.run(cmd, check=True)


def build_linux_desktop(self, arch: str, mode: str, root: str = None, jobs: int = None):
    root = root or self.root
    jobs = jobs or self.jobs
    cmd = [
        "ninja",
        "-C",
        utils.target_output(root, arch, mode),
        "flutter/shell/platform/linux:flutter_gtk",
    ]
    if jobs:
        cmd.append(f"-j{jobs}")
    subprocess.run(cmd, check=True)


def prepare_web_sdk(self, root: str = None):
    root = Path(root or self.root)
    flutter_bin = root / "bin" / "flutter"
    subprocess.run(
        [str(flutter_bin), "--suppress-analytics", "precache", "--web"],
        cwd=root,
        check=True,
    )


def build_selected(self, arch: str = "arm64", preset: str = "termux", jobs: int = None):
    plan = resolve_preset(preset)
    jobs = jobs or self.jobs

    if plan.configure_linux_debug:
        self.configure(arch=arch, mode="debug")
    if plan.build_flutter_core:
        self.build_flutter_core(arch=arch, mode="debug", jobs=jobs)
    if plan.build_dart:
        self.build_dart(arch=arch, mode="debug", jobs=jobs)
    if plan.build_impellerc:
        self.build_impellerc(arch=arch, mode="debug", jobs=jobs)
    if plan.build_const_finder:
        self.build_const_finder(arch=arch, mode="debug", jobs=jobs)
    if plan.prepare_web_sdk:
        self.prepare_web_sdk()

    if plan.build_linux_release:
        self.configure(arch=arch, mode="release")
        self.build_linux_desktop(arch=arch, mode="release", jobs=jobs)
    if plan.build_linux_desktop:
        self.build_linux_desktop(arch=arch, mode="debug", jobs=jobs)
    if plan.build_linux_profile:
        self.configure(arch=arch, mode="profile")
        self.build_linux_desktop(arch=arch, mode="profile", jobs=jobs)

    if plan.build_android_release:
        self.configure_android(arch="arm64", mode="release")
        self.build_android_gen_snapshot(arch="arm64", mode="release", jobs=jobs)
    if plan.build_android_profile:
        self.configure_android(arch="arm64", mode="profile")
        self.build_android_gen_snapshot(arch="arm64", mode="profile", jobs=jobs)

    if plan.package_deb:
        self.debuild(arch=arch, output=self.output(arch), section=plan.package_sections)


def build_all(self, arch: str = "arm64", jobs: int = None):
    self.build_selected(arch=arch, preset="full", jobs=jobs)
```

- [ ] **Step 4: 调整 `debuild()`，让它真正把 `section` 传给 `Package.debuild()`**

```python
def debuild(self, arch: str, output: str = None, root: str = None, section=None, **conf):
    self.sync_windows_to_wsl()

    conf = conf or self.package
    root = root or self.root
    output = output or self.output(arch)

    pkg = Package(root=root, arch=arch, **conf)
    pkg.debuild(output=output, section=section)
```

- [ ] **Step 5: 重新运行测试，确认命令拆分和编排都通过**

Run: `python -m unittest tests.test_build_flow -v`

Expected: PASS，输出 `Ran 4 tests`

- [ ] **Step 6: 提交这一小步**

```bash
git add build.py tests/test_build_flow.py
git commit -m "feat: add preset-driven build orchestration"
```

### Task 3: 拆分打包资源，加入 Web SDK，并让 `termux` 包真正变瘦

**Files:**
- Create: `tests/test_package_manifest.py`
- Modify: `package.yaml`
- Test: `tests/test_package_manifest.py`

- [ ] **Step 1: 先写失败测试，锁定新的资源名和 `termux` 资源边界**

```python
import unittest

import yaml

from build import resolve_preset


class PackageManifestTests(unittest.TestCase):
    def test_package_yaml_defines_web_and_split_artifact_resources(self):
        with open("package.yaml", "rb") as fh:
            data = yaml.safe_load(fh)

        resources = data["resource"]
        self.assertIn("flutter_web_sdk", resources)
        self.assertIn("engine_common_artifacts", resources)
        self.assertIn("linux_gen_snapshot", resources)
        self.assertNotIn("artifacts", resolve_preset("termux").package_sections)

    def test_termux_sections_exclude_linux_profile_payloads(self):
        sections = resolve_preset("termux").package_sections

        self.assertNotIn("flutter_linux_gtk_profile", sections)
        self.assertNotIn("android_gen_snapshot_arm64_profile", sections)
        self.assertIn("android_gen_snapshot_arm64", sections)
        self.assertIn("flutter_web_sdk", sections)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认它因为资源名不存在而失败**

Run: `python -m unittest tests.test_package_manifest -v`

Expected: FAIL，提示缺少 `flutter_web_sdk`、`engine_common_artifacts` 或 `linux_gen_snapshot`

- [ ] **Step 3: 在 `package.yaml` 中拆掉旧的 `artifacts`，加入 Web SDK 资源**

```yaml
  engine_common_artifacts:
    source:
      - $root/engine/src/flutter/impeller/compiler/shader_lib
      - $any/font-subset
      - $any/icudtl.dat
      - $any/impellerc
      - $any/libpath_ops.so
      - $any/libtessellator.so
      - $any/gen/const_finder.dart.snapshot
    output:
      - $eng/linux-$arch
    define:
      any: *any
      eng: &eng f'{distro}/bin/cache/artifacts/engine'

  linux_gen_snapshot:
    source:
      - $any/gen_snapshot
    output:
      - $eng/linux-$arch
    define:
      any: *any
      eng: *eng
    mode: 0o755

  flutter_web_sdk:
    source: $root/bin/cache/flutter_web_sdk
    output: $out/flutter_web_sdk
    define:
      out: &cache f'{distro}/bin/cache'
    mode: 0o755
```

- [ ] **Step 4: 重新运行包定义测试**

Run: `python -m unittest tests.test_package_manifest -v`

Expected: PASS，输出 `Ran 2 tests`

- [ ] **Step 5: 跑一次更宽的单测集合，确认 Task 1/2 没被打坏**

Run: `python -m unittest tests.test_build_presets tests.test_build_flow tests.test_package_manifest -v`

Expected: PASS，所有测试通过

- [ ] **Step 6: 提交这一小步**

```bash
git add package.yaml tests/test_package_manifest.py
git commit -m "feat: split package resources for termux preset"
```

### Task 4: 让 sysroot 和 NDK 变成 GitHub-hosted 可缓存的行为

**Files:**
- Create: `tests/test_sysroot_cache.py`
- Modify: `sysroot.py`
- Modify: `build.py`
- Test: `tests/test_sysroot_cache.py`

- [ ] **Step 1: 先写失败测试，锁定 sysroot manifest 和 NDK 环境变量覆盖**

```python
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sysroot


class SysrootManifestTests(unittest.TestCase):
    def test_manifest_round_trip_skips_download_when_inputs_match(self):
        with tempfile.TemporaryDirectory() as td:
            root = sysroot.Sysroot(
                path=td,
                termux_main={
                    "repo": "https://packages-cf.termux.dev/apt/termux-main/",
                    "dist": "stable",
                    "pkgs": ["glib"],
                },
            )

            with patch("sysroot.asyncio.run") as run:
                root("arm64")
                self.assertEqual(run.call_count, 1)

            with patch("sysroot.asyncio.run") as run:
                root("arm64")
                self.assertEqual(run.call_count, 0)

            manifest = Path(td, ".termux-sysroot-manifest.json")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["arch"], "aarch64")
            self.assertEqual(payload["schema"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认当前 sysroot 每次都会重新跑**

Run: `python -m unittest tests.test_sysroot_cache -v`

Expected: FAIL，第二次调用仍会触发 `asyncio.run`

- [ ] **Step 3: 在 `sysroot.py` 中实现 manifest 命中跳过**

```python
import hashlib
import json


class Sysroot:
    ...

    def _manifest_path(self):
        return self.path / ".termux-sysroot-manifest.json"

    def _manifest_payload(self, arch: str):
        normalized = {
            name: {
                "repo": item["repo"],
                "dist": item["dist"],
                "pkgs": list(item["pkgs"]),
            }
            for name, item in sorted(self.data.items())
        }
        return {
            "schema": 1,
            "arch": arch,
            "sources": normalized,
            "fingerprint": hashlib.sha256(
                json.dumps(normalized, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        }

    def _manifest_matches(self, arch: str):
        path = self._manifest_path()
        if not path.exists():
            return False
        current = self._manifest_payload(arch)
        cached = json.loads(path.read_text(encoding="utf-8"))
        return cached == current

    def _write_manifest(self, arch: str):
        self._manifest_path().write_text(
            json.dumps(self._manifest_payload(arch), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def __call__(self, arch: str):
        arch = utils.termux_arch(arch)
        if self.data and self._manifest_matches(arch):
            logger.info("sysroot manifest hit, skipping download")
            return
        if self.data:
            asyncio.run(_work(self.path, arch, *self.data.values()))
            self._write_manifest(arch)
        else:
            logger.info("no work to do.")
```

- [ ] **Step 4: 让 `build.py` 优先吃环境变量里的 NDK 路径**

```python
def resolve_ndk_path(configured_ndk: str | None) -> str | None:
    return os.environ.get("ANDROID_NDK") or configured_ndk


class Build:
    @utils.recordm
    def __init__(self, conf="build.toml"):
        ...
        ndk = resolve_ndk_path(cfg["ndk"].get("path"))
        ...
```

- [ ] **Step 5: 重新运行 sysroot 测试**

Run: `python -m unittest tests.test_sysroot_cache -v`

Expected: PASS，输出 `Ran 1 test`

- [ ] **Step 6: 跑一遍已有的 Python 单测，确认没有回归**

Run: `python -m unittest tests.test_build_presets tests.test_build_flow tests.test_package_manifest tests.test_sysroot_cache -v`

Expected: PASS

- [ ] **Step 7: 提交这一小步**

```bash
git add build.py sysroot.py tests/test_sysroot_cache.py
git commit -m "feat: make sysroot and ndk cache friendly"
```

### Task 5: 重写主 workflow，并删除重复的 Android 专项 workflow

**Files:**
- Create: `tests/test_workflow_config.py`
- Modify: `.github/workflows/build.yml`
- Delete: `.github/workflows/android-gen-snapshot.yml`
- Test: `tests/test_workflow_config.py`

- [ ] **Step 1: 先写失败测试，锁定 workflow 的输入和默认行为**

```python
import unittest

import yaml


class WorkflowConfigTests(unittest.TestCase):
    def setUp(self):
        with open(".github/workflows/build.yml", "rb") as fh:
            self.workflow = yaml.load(fh, Loader=yaml.BaseLoader)

    def test_workflow_dispatch_defaults_to_termux(self):
        inputs = self.workflow["on"]["workflow_dispatch"]["inputs"]
        self.assertEqual(inputs["preset"]["default"], "termux")
        self.assertIn("termux", inputs["preset"]["options"])
        self.assertIn("full", inputs["preset"]["options"])

    def test_release_still_listens_to_tag_pushes(self):
        self.assertIn("v*", self.workflow["on"]["push"]["tags"])

    def test_upload_artifact_disables_extra_compression(self):
        steps = self.workflow["jobs"]["build"]["steps"]
        upload = next(step for step in steps if step.get("uses") == "actions/upload-artifact@v4")
        self.assertEqual(upload["with"]["compression-level"], 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认新输入和上传行为尚未存在**

Run: `python -m unittest tests.test_workflow_config -v`

Expected: FAIL，提示 `preset` 或 `compression-level` 不存在

- [ ] **Step 3: 在主 workflow 中加入 preset、jobs、缓存和条件发布**

```yaml
on:
  workflow_dispatch:
    inputs:
      arch:
        description: 目标架构
        required: true
        default: arm64
        type: choice
        options: [arm64]
      preset:
        description: 构建预设
        required: true
        default: termux
        type: choice
        options:
          - termux
          - termux-linux
          - full-no-profile
          - full
          - android-release-only
  push:
    tags:
      - "v*"

jobs:
  build:
    runs-on: ubuntu-latest
    env:
      EFFECTIVE_PRESET: ${{ github.event_name == 'push' && 'termux' || inputs.preset }}
      ANDROID_NDK: ${{ github.workspace }}/.cache/android-ndk-r28c
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
      - uses: actions/cache@v4
        with:
          path: |
            .cache/android-ndk-r28c
            sysroot
            ~/.pub-cache
          key: ${{ runner.os }}-${{ inputs.arch || 'arm64' }}-${{ hashFiles('build.toml', 'sysroot.py') }}
      - name: 计算 Ninja 并行度
        id: jobs
        run: |
          CPUS=$(nproc)
          JOBS=$((CPUS > 2 ? CPUS - 1 : 2))
          echo "value=$JOBS" >> "$GITHUB_OUTPUT"
      - name: 安装 Android NDK r28c
        run: |
          mkdir -p "$(dirname "$ANDROID_NDK")"
          if [ ! -d "$ANDROID_NDK" ]; then
            curl -L --retry 3 https://dl.google.com/android/repository/android-ndk-r28c-linux.zip -o /tmp/android-ndk-r28c-linux.zip
            unzip -q /tmp/android-ndk-r28c-linux.zip -d "$(dirname "$ANDROID_NDK")"
            mv "$(dirname "$ANDROID_NDK")/android-ndk-r28c" "$ANDROID_NDK"
          fi
      - name: 执行预设构建
        run: |
          mkdir -p logs
          set -o pipefail
          python build.py build_selected \
            --arch=${{ inputs.arch || 'arm64' }} \
            --preset="$EFFECTIVE_PRESET" \
            --jobs=${{ steps.jobs.outputs.value }} \
            2>&1 | tee logs/build.log
      - uses: actions/upload-artifact@v4
        with:
          name: ${{ env.EFFECTIVE_PRESET }}-${{ inputs.arch || 'arm64' }}
          path: |
            release/*.deb
            logs/*.log
          if-no-files-found: ignore
          retention-days: 30
          compression-level: 0
```

- [ ] **Step 4: 给 Release 增加条件，只在 tag 触发且 `termux` 包存在时发布**

```yaml
      - name: 建立 GitHub Release
        if: startsWith(github.ref, 'refs/tags/v')
        uses: softprops/action-gh-release@v2
        with:
          files: release/*.deb
          tag_name: ${{ github.ref_name }}
```

- [ ] **Step 5: 删除旧的 Android 专项 workflow**

Run: `git rm .github/workflows/android-gen-snapshot.yml`

Expected: staged deletion，避免双份逻辑

- [ ] **Step 6: 重新运行 workflow 配置测试**

Run: `python -m unittest tests.test_workflow_config -v`

Expected: PASS，输出 `Ran 3 tests`

- [ ] **Step 7: 跑完整 Python 单测**

Run: `python -m unittest discover -s tests -v`

Expected: PASS，所有测试通过

- [ ] **Step 8: 提交这一小步**

```bash
git add .github/workflows/build.yml tests/test_workflow_config.py
git commit -m "ci: switch GitHub Actions to termux-first presets"
```

- [ ] **Step 9: 单独提交旧 workflow 删除**

```bash
git add .github/workflows/android-gen-snapshot.yml
git commit -m "ci: remove redundant android snapshot workflow"
```

### Task 6: 更新面向用户的文档

**Files:**
- Modify: `README.md`
- Modify: `README_EN.md`
- Test: `README.md`
- Test: `README_EN.md`

- [ ] **Step 1: 先更新中文 README，把默认发布说明改成 `termux`**

```md
## GitHub Actions 默认发布内容

从现在开始，GitHub Release 默认发布 `termux` 预设构建的 `.deb`，目标能力是：

- `flutter doctor`
- `flutter create`
- `flutter pub get`
- `flutter run -d web-server`
- `flutter build apk --debug`
- `flutter build apk --release --target-platform android-arm64`

Linux desktop 与 `--profile` 不再属于默认发布内容，如需这些能力，请手动运行 Actions 并选择 `termux-linux`、`full-no-profile` 或 `full`。
```

- [ ] **Step 2: 同步更新英文 README**

```md
## Default GitHub Actions release

GitHub Releases now publish the `termux` preset by default. That package is intended to support:

- `flutter doctor`
- `flutter create`
- `flutter pub get`
- `flutter run -d web-server`
- `flutter build apk --debug`
- `flutter build apk --release --target-platform android-arm64`

Linux desktop support and all `--profile` support are opt-in presets exposed through manual workflow runs.
```

- [ ] **Step 3: 用文本检查确认关键术语已经写入文档**

Run: `rg -n "termux-linux|full-no-profile|flutter run -d web-server|android-arm64" README.md README_EN.md`

Expected: 输出同时命中中文和英文文档

- [ ] **Step 4: 提交这一小步**

```bash
git add README.md README_EN.md
git commit -m "docs: describe termux-first release presets"
```

### Task 7: 最终整体验证

**Files:**
- Modify: `build.py`
- Modify: `package.yaml`
- Modify: `sysroot.py`
- Modify: `.github/workflows/build.yml`
- Modify: `README.md`
- Modify: `README_EN.md`
- Test: `tests/`

- [ ] **Step 1: 运行完整 Python 单测套件**

Run: `python -m unittest discover -s tests -v`

Expected: PASS，0 failures，0 errors

- [ ] **Step 2: 运行一次 CLI 冒烟验证，确认 `build_selected` 暴露在 Fire CLI 中**

Run: `python build.py build_selected --help`

Expected: 输出包含 `preset` 和 `jobs`

- [ ] **Step 3: 解析 workflow YAML，确认文件格式合法**

Run: `python - <<'PY'\nimport yaml\nfrom pathlib import Path\nfor path in [Path('.github/workflows/build.yml')]:\n    with open(path, 'rb') as fh:\n        yaml.safe_load(fh)\nprint('workflow-yaml-ok')\nPY`

Expected: 输出 `workflow-yaml-ok`

- [ ] **Step 4: 查看最终变更，确认没有把用户现有的脏改动误加入提交**

Run: `git status --short`

Expected: 只剩下当前任务涉及文件；没有意外回滚或删除用户已有改动

- [ ] **Step 5: 提交最终整理**

```bash
git add build.py package.yaml sysroot.py .github/workflows/build.yml README.md README_EN.md tests
git commit -m "feat: add termux-first CI presets"
```
