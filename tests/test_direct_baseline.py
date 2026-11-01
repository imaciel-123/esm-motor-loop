import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

import direct_baseline as b


class FakeFiles:
    def __init__(self):
        self.created = []
        self.deleted = []

    def create(self, file, purpose):
        assert purpose == "user_data"
        self.created.append(file.name)
        return SimpleNamespace(id=f"file-{len(self.created)}")

    def delete(self, file_id):
        self.deleted.append(file_id)
        return SimpleNamespace(deleted=True)


class FakeResponse:
    output_text = "Análise direta, sem gabarito."

    def model_dump(self, mode):
        assert mode == "json"
        return {"status": "completed", "id": "resp-fake", "usage": {"input_tokens": 100, "output_tokens": 50}}


class FakeResponses:
    def __init__(self, fails=False):
        self.calls = []
        self.fails = fails

    def create(self, **request):
        self.calls.append(request)
        if self.fails:
            raise TimeoutError("sem resposta")
        return FakeResponse()


class FakeClient:
    def __init__(self, fails=False):
        self.files = FakeFiles()
        self.responses = FakeResponses(fails)


class DirectBaselineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.src = root / "input"
        self.src.mkdir()
        self.out = root / "results"
        self.question = root / "question.md"
        self.question.write_text("Pergunta original?\n", encoding="utf-8")
        (self.src / "a.md").write_text("Uma fonte.\n", encoding="utf-8")
        (self.src / "b.json").write_text('{"x": 1}', encoding="utf-8")

    def test_preview_no_network(self):
        x = b.scan(self.src, self.question)
        self.assertEqual(x["file_count"], 2)
        self.assertEqual(x["question"], "Pergunta original?\n")
        self.assertEqual(len(x["files"][0]["sha256"]), 64)

    def test_direct_one_call_and_cleanup(self):
        fake = FakeClient()
        result = b.run(b.scan(self.src, self.question), self.src, self.out, fake)
        self.assertEqual(len(fake.files.created), 2)
        self.assertEqual(len(fake.responses.calls), 1)
        sent = fake.responses.calls[0]
        self.assertEqual(sent["model"], "gpt-6.1-sol")
        self.assertFalse(sent["store"])
        parts = sent["input"][0]["content"]
        self.assertEqual([p["type"] for p in parts], ["input_file", "input_file", "input_text"])
        self.assertEqual(parts[-1]["text"], "Pergunta original?\n")
        self.assertEqual(fake.files.deleted, ["file-1", "file-2"])
        self.assertEqual((result / "resposta.md").read_text(encoding="utf-8"), "Análise direta, sem gabarito.\n")
        self.assertEqual(json.loads((result / "execucao.json").read_text())["status"], "completed")

    def test_unsupported_blocks_without_calls(self):
        (self.src / "unknown.exe").write_bytes(b"bin")
        with self.assertRaisesRegex(ValueError, "Formato não previsto"):
            b.scan(self.src, self.question)

    def test_duplicate_blocks_without_calls(self):
        (self.src / "copy.md").write_text("Uma fonte.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Conteúdo idêntico"):
            b.scan(self.src, self.question)

    def test_size_limit(self):
        old = b.MAX_BYTES
        try:
            b.MAX_BYTES = 15
            with self.assertRaisesRegex(ValueError, "MENOS de 50 MB"):
                b.scan(self.src, self.question)
        finally:
            b.MAX_BYTES = old

    def test_timeout_does_not_auto_retry_and_cleanup(self):
        fake = FakeClient(fails=True)
        with self.assertRaises(TimeoutError):
            b.run(b.scan(self.src, self.question), self.src, self.out, fake)
        self.assertEqual(len(fake.responses.calls), 1)
        self.assertEqual(fake.files.deleted, ["file-1", "file-2"])
        target = next(self.out.iterdir())
        self.assertEqual(json.loads((target / "execucao.json").read_text())["status"], "error-possibly-charged")

    def test_bad_request_records_message_without_retry(self):
        fake = FakeClient()
        class FakeBadRequest(Exception):
            status_code = 400
            request_id = "req-test"
            body = {"message": "Example validation error", "code": "invalid_request_error", "param": "input"}
        def reject(**request):
            fake.responses.calls.append(request)
            raise FakeBadRequest("BadRequest")
        fake.responses.create = reject
        with self.assertRaises(FakeBadRequest):
            b.run(b.scan(self.src, self.question), self.src, self.out, fake)
        self.assertEqual(len(fake.responses.calls), 1)
        status = json.loads((next(self.out.iterdir()) / "execucao.json").read_text(encoding="utf-8"))
        self.assertEqual(status["api_error"]["http_status"], 400)
        self.assertEqual(status["api_error"]["param"], "input")
        self.assertEqual(status["api_error"]["message"], "Example validation error")

    def test_changed_file_blocks_before_upload(self):
        info = b.scan(self.src, self.question)
        (self.src / "a.md").write_text("Modificado.", encoding="utf-8")
        fake = FakeClient()
        with self.assertRaisesRegex(ValueError, "mudou desde preflight"):
            b.run(info, self.src, self.out, fake)
        self.assertEqual(fake.files.created, [])
        self.assertEqual(fake.responses.calls, [])

    def test_cleanup_recovery(self):
        fake = FakeClient()
        target = self.out / "prior"
        target.mkdir(parents=True)
        manifest = {"uploads": [
            {"name": "a.md", "file_id": "file-old", "delete_status": "pending"},
            {"name": "b.md", "file_id": "file-deleted", "delete_status": "deleted"}]}
        b.save_json(target / "manifest.json", manifest)
        b.cleanup(fake, manifest, target / "manifest.json")
        self.assertEqual(fake.files.deleted, ["file-old"])
        self.assertEqual(manifest["uploads"][0]["delete_status"], "deleted")


if __name__ == "__main__":
    unittest.main()
