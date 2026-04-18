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

    def test_manual_dispatch_updates_fixed_release_tag(self):
        env = self.workflow["jobs"]["build"]["env"]
        self.assertEqual(env["MANUAL_RELEASE_TAG"], "termux-manual-test")

        steps = self.workflow["jobs"]["build"]["steps"]
        tag_step = next(step for step in steps if step.get("name") == "更新手动测试标签")
        self.assertIn("workflow_dispatch", tag_step["if"])
        self.assertIn("git tag -f", tag_step["run"])
        self.assertIn('--force', tag_step["run"])

    def test_release_step_supports_manual_dispatch_fixed_release(self):
        steps = self.workflow["jobs"]["build"]["steps"]
        release = next(step for step in steps if step.get("name") == "建立 GitHub Release")

        self.assertIn("workflow_dispatch", release["if"])
        self.assertIn("env.MANUAL_RELEASE_TAG", release["with"]["tag_name"])
        self.assertEqual(release["with"]["prerelease"], "${{ github.event_name == 'workflow_dispatch' && 'true' || 'false' }}")
        self.assertEqual(release["with"]["make_latest"], "${{ github.event_name == 'workflow_dispatch' && 'false' || 'true' }}")


if __name__ == "__main__":
    unittest.main()
