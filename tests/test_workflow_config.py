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
        self.assertNotIn("android-release-only", inputs["preset"]["options"])

    def test_workflow_uses_python_313(self):
        steps = self.workflow["jobs"]["build"]["steps"]
        setup = next(step for step in steps if step.get("uses") == "actions/setup-python@v5")
        self.assertEqual(setup["with"]["python-version"], "3.13")

    def test_workflow_only_supports_manual_dispatch(self):
        self.assertIn("workflow_dispatch", self.workflow["on"])
        self.assertNotIn("push", self.workflow["on"])

    def test_upload_artifact_disables_extra_compression(self):
        steps = self.workflow["jobs"]["build"]["steps"]
        upload = next(step for step in steps if step.get("uses") == "actions/upload-artifact@v4")
        self.assertEqual(upload["with"]["compression-level"], "0")

    def test_upload_artifact_includes_root_deb_files(self):
        steps = self.workflow["jobs"]["build"]["steps"]
        upload = next(step for step in steps if step.get("uses") == "actions/upload-artifact@v4")
        path_spec = upload["with"]["path"]
        lines = [line.strip() for line in path_spec.splitlines() if line.strip()]

        self.assertIn("*.deb", lines)

    def test_ndk_install_step_uses_temp_extract_dir(self):
        steps = self.workflow["jobs"]["build"]["steps"]
        install = next(step for step in steps if step.get("name") == "安装 Android NDK r28c")
        script = install["run"]

        self.assertIn("mktemp -d", script)
        self.assertIn('mv "$TMP_NDK_DIR/android-ndk-r28c" "$ANDROID_NDK"', script)
        self.assertNotIn('mv "$(dirname "$ANDROID_NDK")/android-ndk-r28c" "$ANDROID_NDK"', script)

    def test_workflow_does_not_add_extra_vpython_wrapper(self):
        steps = self.workflow["jobs"]["build"]["steps"]
        names = [step.get("name") for step in steps]

        self.assertNotIn("提供 vpython 支持", names)

        verify = next(step for step in steps if step.get("name") == "验证工具链")
        self.assertNotIn("command -v vpython", verify["run"])

    def test_workflow_does_not_cache_sysroot_or_ndk(self):
        steps = self.workflow["jobs"]["build"]["steps"]
        uses = [step.get("uses") for step in steps]
        names = [step.get("name") for step in steps]

        self.assertNotIn("actions/cache@v4", uses)
        self.assertNotIn("恢复 sysroot 和 NDK 缓存", names)

    def test_manual_dispatch_updates_release_tag_from_build_toml(self):
        steps = self.workflow["jobs"]["build"]["steps"]
        meta = next(step for step in steps if step.get("name") == "解析版本信息")
        tag_step = next(step for step in steps if step.get("name") == "更新发布标签")
        self.assertIn('cfg["flutter"]["tag"]', meta["run"])
        self.assertIn("git tag -f", tag_step["run"])
        self.assertIn('${{ steps.meta.outputs.version }}', tag_step["run"])
        self.assertIn('--force', tag_step["run"])

    def test_release_step_uses_plain_build_toml_version_tag(self):
        steps = self.workflow["jobs"]["build"]["steps"]
        release = next(step for step in steps if step.get("name") == "建立 GitHub Release")

        self.assertNotIn("workflow_dispatch", release.get("if", ""))
        self.assertEqual(release["with"]["tag_name"], "${{ steps.meta.outputs.version }}")
        self.assertEqual(release["with"]["name"], "${{ steps.meta.outputs.artifact_name }}")
        self.assertEqual(release["with"]["prerelease"], "false")
        self.assertEqual(release["with"]["make_latest"], "true")


if __name__ == "__main__":
    unittest.main()
