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


if __name__ == "__main__":
    unittest.main()
