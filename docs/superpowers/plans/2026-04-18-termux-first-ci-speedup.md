# Termux-First Manual Release Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 GitHub Actions 收敛为“仅手动触发、版本只由 `build.toml` 控制、运行成功后自动发布 GitHub Release”的发布流程，并固定使用 `patches/` 根目录下的 4 个 patch。

**Architecture:** `build.toml` 成为 Flutter 版本与 Release 版本号的唯一来源，workflow 不再接收版本输入，也不再监听 `push tag`。`build.py` 保留 preset 编排，但移除 `android-release-only`，并将 patch 解析逻辑从 `patches/<tag>/` 改成固定的 `patches/` 根目录。`patches/` 扁平化后只保留 4 个通用 patch 文件。测试层继续用 `unittest` 锁定 workflow 触发方式、preset 选项、发布 tag 规则和 patch 路径解析。

**Tech Stack:** Python 3.13、`unittest`、GitHub Actions、PyYAML、Flutter Engine/Ninja

---

## File Structure

- `.github/workflows/build.yml`
  - 改成仅 `workflow_dispatch`，移除 `push tag` 和版本输入，发布版本从 `build.toml` 读取。
- `build.py`
  - 删除 `android-release-only` preset，patch 根目录固定指向 `patches/`。
- `build.toml`
  - 继续作为 Flutter 版本唯一来源，补充 patch 配置注释以匹配新布局。
- `patches/engine.patch`
- `patches/dart.patch`
- `patches/skia.patch`
- `patches/flutter_sdk_arm64_default.patch`
  - 扁平化后的 4 个通用 patch 文件。
- `patches/3.35.0/`
- `patches/3.41.5/`
  - 旧版目录在实现时删除。
- `tests/test_build_presets.py`
  - 去掉 `android-release-only` 相关断言。
- `tests/test_build_flow.py`
  - 去掉 `android-release-only` 的编排测试。
- `tests/test_workflow_config.py`
  - 重新锁定 workflow 仅手动触发、无版本输入、tag 不加 `v`、不含 `android-release-only`。
- `README.md`
- `README_EN.md`
  - 更新为手动触发 + 版本由 `build.toml` 控制的说明。
- `AGENTS.md`
  - 同步当前 CI/patch 设计说明。

### Task 1: 收敛 preset，移除 `android-release-only`

**Files:**
- Modify: `build.py`
- Modify: `tests/test_build_presets.py`
- Modify: `tests/test_build_flow.py`
- Test: `tests/test_build_presets.py`
- Test: `tests/test_build_flow.py`

- [ ] **Step 1: 先写失败测试，声明 `android-release-only` 已不再是有效 preset**

```python
import unittest

from build import resolve_preset


class ResolvePresetTests(unittest.TestCase):
    def test_unknown_removed_android_release_only_preset_raises(self):
        with self.assertRaises(ValueError):
            resolve_preset("android-release-only")
```

- [ ] **Step 2: 再写失败测试，删掉 `build_selected()` 对旧 preset 的依赖**

```python
class BuildSelectedTests(unittest.TestCase):
    def test_full_preset_still_packages(self):
        runner = RecordingBuild()
        runner.build_selected(arch="arm64", preset="full", jobs=4)

        self.assertIn(("android", "release"), runner.events)
        self.assertTrue(any(event[0] == "package" for event in runner.events))
```

- [ ] **Step 3: 运行测试，确认旧 preset 相关断言先失败**

Run: `python -m unittest tests.test_build_presets tests.test_build_flow -v`

Expected: FAIL，至少有一处断言还在引用 `android-release-only`

- [ ] **Step 4: 在 `build.py` 中移除 `android-release-only` preset 定义**

```python
PRESETS = {
    "termux": ...,
    "termux-linux": ...,
    "full-no-profile": ...,
    "full": ...,
}
```

- [ ] **Step 5: 更新测试，移除旧 preset 测试并保留 `termux/full` 的覆盖**

```python
class ResolvePresetTests(unittest.TestCase):
    def test_termux_preset_keeps_web_and_android_release_only(self):
        ...

    def test_unknown_removed_android_release_only_preset_raises(self):
        with self.assertRaises(ValueError):
            resolve_preset("android-release-only")
```

- [ ] **Step 6: 重新运行相关测试**

Run: `python -m unittest tests.test_build_presets tests.test_build_flow -v`

Expected: PASS

- [ ] **Step 7: 提交这一小步**

```bash
git add build.py tests/test_build_presets.py tests/test_build_flow.py
git commit -m "refactor: remove android release only preset"
```

### Task 2: 固定 patch 根目录，去掉版本子目录选择

**Files:**
- Modify: `build.py`
- Modify: `build.toml`
- Create: `patches/engine.patch`
- Create: `patches/dart.patch`
- Create: `patches/skia.patch`
- Create: `patches/flutter_sdk_arm64_default.patch`
- Delete: `patches/3.35.0/engine.patch`
- Delete: `patches/3.35.0/dart.patch`
- Delete: `patches/3.35.0/dart.new.patch`
- Delete: `patches/3.35.0/skia.patch`
- Delete: `patches/3.35.0/flutter_sdk_arm64_default.patch`
- Delete: `patches/3.41.5/engine.patch`
- Delete: `patches/3.41.5/dart.patch`
- Delete: `patches/3.41.5/skia.patch`
- Delete: `patches/3.41.5/flutter_sdk_arm64_default.patch`
- Test: `build.py`

- [ ] **Step 1: 先写失败测试，锁定 patch 不再按 tag 拼目录**

```python
import unittest
from pathlib import Path

from build import Build


class PatchLayoutTests(unittest.TestCase):
    def test_patch_files_are_resolved_from_root_patches_dir(self):
        runner = Build()

        self.assertEqual(runner.patches["engine"]["file"].name, "engine.patch")
        self.assertEqual(runner.patches["engine"]["file"].parent.name, "patches")
        self.assertNotIn("3.41.5", str(runner.patches["engine"]["file"]))
```

- [ ] **Step 2: 运行测试，确认当前逻辑仍依赖版本子目录**

Run: `python -m unittest tests.test_build_presets -v`

Expected: FAIL 或当前断言无法满足

- [ ] **Step 3: 复制当前 `patches/3.41.5/` 下的 4 个 patch 到 `patches/` 根目录**

```bash
cp patches/3.41.5/engine.patch patches/engine.patch
cp patches/3.41.5/dart.patch patches/dart.patch
cp patches/3.41.5/skia.patch patches/skia.patch
cp patches/3.41.5/flutter_sdk_arm64_default.patch patches/flutter_sdk_arm64_default.patch
```

- [ ] **Step 4: 修改 `build.py`，固定 patch 根目录**

```python
patch_base = path / patches.get("dir", "./patches")
```

- [ ] **Step 5: 修改 `build.toml` 注释，去掉“按 tag 目录选择 patch”的描述**

```toml
# Patches are stored directly under patches/
[patch]
dir = './patches'
```

- [ ] **Step 6: 删除旧版 patch 子目录文件**

```bash
git rm patches/3.35.0/engine.patch patches/3.35.0/dart.patch patches/3.35.0/dart.new.patch patches/3.35.0/skia.patch patches/3.35.0/flutter_sdk_arm64_default.patch
git rm patches/3.41.5/engine.patch patches/3.41.5/dart.patch patches/3.41.5/skia.patch patches/3.41.5/flutter_sdk_arm64_default.patch
```

- [ ] **Step 7: 运行相关测试与最小导入检查**

Run: `python -m unittest tests.test_build_presets -v`

Expected: PASS

- [ ] **Step 8: 提交这一小步**

```bash
git add build.py build.toml patches
git commit -m "refactor: flatten patch directory layout"
```

### Task 3: 只保留手动触发，版本完全来自 `build.toml`

**Files:**
- Modify: `.github/workflows/build.yml`
- Modify: `tests/test_workflow_config.py`
- Test: `tests/test_workflow_config.py`

- [ ] **Step 1: 先写失败测试，锁定 workflow 不再监听 `push tag`**

```python
class WorkflowConfigTests(unittest.TestCase):
    def test_workflow_only_supports_manual_dispatch(self):
        self.assertIn("workflow_dispatch", self.workflow["on"])
        self.assertNotIn("push", self.workflow["on"])
```

- [ ] **Step 2: 再写失败测试，锁定 `android-release-only` 不再出现在输入选项里**

```python
    def test_workflow_input_options_do_not_include_removed_preset(self):
        inputs = self.workflow["on"]["workflow_dispatch"]["inputs"]
        self.assertNotIn("android-release-only", inputs["preset"]["options"])
```

- [ ] **Step 3: 再写失败测试，锁定 Release tag 直接来自 `build.toml`，不加 `v`**

```python
    def test_release_step_reads_plain_version_tag(self):
        steps = self.workflow["jobs"]["build"]["steps"]
        release = next(step for step in steps if step.get("name") == "建立 GitHub Release")
        self.assertEqual(release["with"]["tag_name"], "${{ steps.meta.outputs.version }}")
```

- [ ] **Step 4: 运行 workflow 配置测试，确认旧逻辑失败**

Run: `python -m unittest tests.test_workflow_config -v`

Expected: FAIL，至少命中 `push`、`android-release-only`、固定手动测试 tag 之一

- [ ] **Step 5: 在 workflow 中新增 metadata 步骤，从 `build.toml` 解析版本**

```yaml
      - name: 解析版本信息
        id: meta
        run: |
          python - <<'PY' >> "$GITHUB_OUTPUT"
          import tomllib
          with open("build.toml", "rb") as f:
              cfg = tomllib.load(f)
          version = cfg["flutter"]["tag"]
          print(f"version={version}")
          print(f"artifact_name=flutter-termux-{version}-${{ env.ARCH }}")
          PY
```

- [ ] **Step 6: 删除 `push` 触发器、删除固定测试 tag 逻辑，并改成每次用 `build.toml` 版本发布**

```yaml
on:
  workflow_dispatch:
    inputs:
      arch:
        ...
      preset:
        ...
        options:
          - termux
          - termux-linux
          - full-no-profile
          - full
```

```yaml
      - name: 更新发布标签
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git tag -f "${{ steps.meta.outputs.version }}" "$GITHUB_SHA"
          git push origin "refs/tags/${{ steps.meta.outputs.version }}" --force
```

```yaml
      - name: 建立 GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            *.deb
            release/*.deb
          tag_name: ${{ steps.meta.outputs.version }}
          name: ${{ steps.meta.outputs.artifact_name }}
          prerelease: false
          make_latest: true
```

- [ ] **Step 7: 重新运行 workflow 配置测试**

Run: `python -m unittest tests.test_workflow_config -v`

Expected: PASS

- [ ] **Step 8: 提交这一小步**

```bash
git add .github/workflows/build.yml tests/test_workflow_config.py
git commit -m "ci: use manual releases from build toml version"
```

### Task 4: 更新文档说明

**Files:**
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `AGENTS.md`
- Test: `README.md`
- Test: `README_EN.md`
- Test: `AGENTS.md`

- [ ] **Step 1: 更新 README，说明只保留手动触发**

```md
## GitHub Actions 发布方式

当前 GitHub Actions 只支持手动触发。

发布版本号来自仓库中的 `build.toml`：

```toml
[flutter]
tag = "3.41.5"
```

修改该值后手动运行 workflow，即会：

- clone 对应 Flutter tag
- 使用固定的 4 个 patch 打补丁
- 构建 `.deb`
- 自动发布同名 GitHub Release tag：`3.41.5`
```
```

- [ ] **Step 2: 同步更新英文 README**

```md
## GitHub Actions release flow

GitHub Actions now supports manual dispatch only.

The release version is read from `build.toml`:

```toml
[flutter]
tag = "3.41.5"
```

After editing that value and running the workflow manually, the pipeline will:

- clone the matching Flutter tag
- apply the fixed four patches from `patches/`
- build the `.deb`
- publish a GitHub Release using the same plain tag: `3.41.5`
```
```

- [ ] **Step 3: 更新 `AGENTS.md`，去掉版本目录 patch 描述**

```md
| `patches/` | Four shared patch files applied directly from the root patch directory. |
```

- [ ] **Step 4: 文本检查关键术语**

Run: `rg -n "workflow_dispatch|build.toml|patches/|3.41.5|android-release-only|push tag" README.md README_EN.md AGENTS.md`

Expected: 命中新的手动触发说明，且不再把 `android-release-only` 当作现行配置

- [ ] **Step 5: 提交这一小步**

```bash
git add README.md README_EN.md AGENTS.md
git commit -m "docs: describe manual release workflow"
```

### Task 5: 最终整体验证

**Files:**
- Modify: `build.py`
- Modify: `build.toml`
- Modify: `.github/workflows/build.yml`
- Modify: `tests/`
- Test: `tests/`

- [ ] **Step 1: 运行完整 Python 单测**

Run: `python -m unittest discover -s tests -v`

Expected: PASS，0 failures，0 errors

- [ ] **Step 2: 验证 CLI 仍暴露 `build_selected`**

Run: `python build.py build_selected --help`

Expected: 输出仍包含 `preset`

- [ ] **Step 3: 验证 workflow YAML 可解析**

Run: `python - <<'PY'\nimport yaml\nfrom pathlib import Path\nwith open(Path('.github/workflows/build.yml'), 'rb') as fh:\n    yaml.safe_load(fh)\nprint('workflow-yaml-ok')\nPY`

Expected: 输出 `workflow-yaml-ok`

- [ ] **Step 4: 检查工作区状态**

Run: `git status --short`

Expected: 只包含当前任务相关文件；无意外脏改动

- [ ] **Step 5: 提交最终整理**

```bash
git add build.py build.toml .github/workflows/build.yml patches tests README.md README_EN.md AGENTS.md
git commit -m "feat: switch CI to manual build toml releases"
```
