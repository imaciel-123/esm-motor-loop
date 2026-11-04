import base64
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

SCRIPT = Path(__file__).resolve().parents[1] / "experiments" / "esm-121" / "collect_esm121.py"
SPEC = importlib.util.spec_from_file_location("esm121_collector", SCRIPT)
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class FakeGithub:
    def __init__(self):
        self.reads = 0
        self.commits = {207:17,211:5,213:1,214:3,216:3,219:1,221:5,222:1,229:3}

    def get(self, endpoint, params=None, optional=False):
        self.reads += 1
        if "/contents/" in endpoint:
            return None
        if endpoint.startswith("/pulls/"):
            pr = int(endpoint.split("/")[2])
            return {"number":pr, "merged_at":"2026-10-18T12:00:00Z",
                    "html_url":f"https://github.com/imaciel-123/esm/pull/{pr}",
                    "head":{"sha":"head"+str(pr)},
                    "merge_commit_sha":"merge"+str(pr),
                    "body":"PR full description with original text"}
        if endpoint == "/actions/runs":
            pr = int(params["head_sha"].replace("head",""))
            return {"workflow_runs":[{"id":pr*10+i,"html_url":"https://github.com/imaciel-123/esm/actions"} for i in (1,2)]}
        if endpoint.startswith("/actions/runs/"):
            return {"jobs":[]}
        raise ValueError("endpoint unexpected "+endpoint)

    def page(self, path, params=None):
        if path.endswith("/commits"):
            pr = int(path.split("/")[2])
            return [{"sha":f"sha-{pr}-{i}","commit":{"message":"Commit de implementação"}} for i in range(self.commits[pr])]
        if path.endswith("/files"):
            return [{"filename":"src/example.tsx","patch":"@@ -1,1 +1,1 @@\n-old\n+new"}]
        return []


def make_seed(path, include_all=True):
    with ZipFile(path,"w") as z:
        names = collector.REQUIRED_JIRA if include_all else collector.REQUIRED_JIRA[:-1]
        for name in names:
            z.writestr(name, "Original recovered Jira source: "+name)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.zip = self.root/"jira.zip"
        make_seed(self.zip)

    def test_locked_original_prompt(self):
        q = (SCRIPT.parent/"pergunta_original.md").read_text(encoding="utf-8")
        self.assertIn("temos essa issue. https://esmodel.atlassian.net/browse/ESM-121", q)
        self.assertIn("todos os pr's, commits, reviews", q)
        self.assertIn("vc pode levar o tempo que for.", q)

    def test_build_prepares_9_pr_39_commits_18_runs_no_assessment(self):
        target = self.root/"candidate"
        target.mkdir()
        result = collector.build(target, self.zip, FakeGithub())
        self.assertEqual(result["github_pr_count"], 9)
        self.assertEqual(result["github_pr_commit_count"], 39)
        self.assertEqual(result["github_workflow_run_count"], 18)
        self.assertEqual(result["jira_comments"], 5)
        self.assertEqual(result["jira_changelog_entries"], 22)
        self.assertTrue((target/"github/PR-221_PR.json").is_file())
        empty_reviews = json.loads((target/"github/PR-221_reviews.json").read_text())
        self.assertEqual(empty_reviews["data"], [])
        self.assertFalse(any("auditoria" in item["file"].lower() for item in result["files"]))
        self.assertEqual(result["total_bytes"], sum(x["bytes"] for x in result["files"]))

    def test_missing_jira_input_rejected_before_gitHub(self):
        make_seed(self.zip,include_all=False)
        target=self.root/"candidate"
        target.mkdir()
        class UnusedGitHub:
            def get(self,*args,**kwargs):
                raise AssertionError("No GitHub API should be called")
        with self.assertRaisesRegex(ValueError,"ZIP Jira incompleto"):
            collector.build(target,self.zip,UnusedGitHub())

    def test_invalid_missing_merge_rejected(self):
        class InvalidGitHub(FakeGithub):
            def get(self,endpoint,params=None,optional=False):
                x=super().get(endpoint,params,optional)
                if endpoint=="/pulls/221":
                    x["merge_commit_sha"]=None
                return x
        target=self.root/"candidate"
        target.mkdir()
        with self.assertRaisesRegex(ValueError,"Sem SHA head/merge"):
            collector.build(target,self.zip,InvalidGitHub())


if __name__ == "__main__":
    unittest.main()
