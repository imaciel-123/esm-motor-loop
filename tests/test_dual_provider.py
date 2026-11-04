import hashlib
import importlib.util
import io
import zipfile
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "experiments" / "esm-121" / "dual_provider.py"
SPEC = importlib.util.spec_from_file_location("dual_provider", SCRIPT)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

class DualProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.entries = []
        paths = ([f"jira/item-{n}.json" for n in range(8)] +
                 [f"github/PR-{n}_{kind}.json" for n in range(9) for kind in ("PR", "commits", "files")] +
                 [f"github/PR-{n}_workflow_runs.json" for n in range(9)] +
                 [f"github/snapshots/{n}.txt" for n in range(6)] +
                 [f"reference/{n}.md" for n in range(3)])
        self.assertEqual(len(paths), 53)
        for n, path in enumerate(paths):
            data = f"corpus-{n}".encode()
            dest = self.folder / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            self.entries.append({"path": path, "file_id": f"file-id{n}", "sha256": m.digest(data)})
        m.save(self.folder / "selecao_53_sem_reupload.json",
               {"selecionados": 53, "excluidos": 45, "arquivos": self.entries})
        (self.folder / "observacoes_consolidadas_45.txt").write_text("45 excluídos; nenhum apagado.")
        self.text = "Pergunta teste"
        self.model = "claude-sonnet-5-5"
        self.output = 24000
        self.budget = 5.0

    def ready(self):
        def uploaded(name, raw):
            return "file_" + m.digest(raw)[:16]
        with patch.object(m, "upload_claude", side_effect=uploaded), patch("builtins.print"):
            return m.prepare(self.folder, self.entries)

    def test_51_source_slice_excludes_exactly_the_two_deleted_references_and_preserves_state(self):
        # Duas referências explicitamente removidas da seleção inicial.
        names = m.REMOVED_REFERENCE_PATHS
        for idx, name in [(0, names[0]), (1, names[1])]:
            self.entries[idx]["path"] = name
        old_id = m.identity(self.entries)
        chosen = m.active_selection(self.entries, True)
        self.assertEqual(len(chosen), 51)
        self.assertEqual(len(self.entries), 53)
        self.assertEqual(m.identity(self.entries), old_id)
        self.assertTrue(all(e["path"] not in names for e in chosen))
        self.assertEqual(len({e["file_id"] for e in chosen}), 51)
        state = {"files": {e["path"]: {"file_id": f"file_claude_{n}"}
                           for n, e in enumerate(self.entries)}, "master": {"file_id": "file_master"}}
        oai, claude = m.requests(chosen, state, self.text, self.model, 12000, with_master=True)
        openai_ids = [x["file_id"] for x in oai["input"][0]["content"] if x["type"] == "input_file"]
        claude_ids = [x["source"]["file_id"] for x in claude["messages"][0]["content"] if x["type"] == "document"]
        self.assertEqual(len(openai_ids), 51)
        self.assertEqual(len(claude_ids), 52)  # 51 fontes + Master
        for name in names:
            removed = next(e for e in self.entries if e["path"] == name)
            self.assertNotIn(removed["file_id"], openai_ids)
            self.assertNotIn(state["files"][name]["file_id"], claude_ids)
        self.assertIn("51 fontes", oai["instructions"])
        self.assertNotEqual(m.result_folder(self.folder, True, True),
                            m.result_folder(self.folder, True, False))

    def test_master_openai_id_matches_current_storage(self):
        # Identificador confirmado pelo operador na Vector Store 'master' em 04/11/2026.
        self.assertEqual(m.MASTER_OPENAI_FILE, "file-2J9CuGsQXaiuGG9Mn35ebu")

    def test_claude_50_no_references_or_master_and_no_openai_or_upload(self):
        # O teste muda apenas os nomes fictícios do corpus de teste.
        original = ("reference/0.md", "reference/1.md", "reference/2.md")
        for old, new in zip(original, m.ALL_REFERENCE_PATHS):
            rec = next(e for e in self.entries if e["path"] == old)
            p = self.folder / old
            q = self.folder / new
            q.parent.mkdir(parents=True, exist_ok=True)
            p.rename(q)
            rec["path"] = new
        m.save(self.folder / "selecao_53_sem_reupload.json",
               {"selecionados": 53, "excluidos": 45, "arquivos": self.entries})
        state = self.ready()
        active = m.active_selection(self.entries, claude_50_only=True)
        self.assertEqual(len(active), 50)
        self.assertEqual(len(self.entries), 53)
        self.assertTrue(all(not e["path"].startswith("reference/") for e in active))
        self.assertEqual(len(state["files"]), 53)

        question = self.folder / "questions.md"
        question.write_text("Investigar a Change ESM-121", encoding="utf-8")
        calls = []
        def fake_api(url, method, headers, body=None, raw=False, timeout=600):
            calls.append((url, body))
            if url.endswith("/messages"):
                docs = body["messages"][0]["content"][:-1]
                self.assertEqual(len(docs), 50)
                self.assertEqual(len(body["messages"][0]["content"]), 51)
                self.assertTrue(all(d["type"] == "document" for d in docs))
                self.assertTrue(all(not d["title"].startswith("reference/") for d in docs))
                self.assertTrue(all(d["source"]["file_id"] != state["master"]["file_id"]
                                    for d in docs) if "master" in state else True)
                self.assertNotIn("Master 1.5.1", body["system"])
                return {"id": "msg-50", "stop_reason": "end_turn",
                        "model": self.model, "content": [{"type": "text", "text": "Conclusão Claude"}]}
            raise AssertionError("API indevida: " + url)
        old_openai = m.result_folder(self.folder, True, True) / "openai_response.json"
        m.save(old_openai, {"id": "resp-ja-concluida"})
        with patch.object(m, "api", side_effect=fake_api), patch.object(m, "auth", return_value={}), \
             patch.object(m, "upload_claude") as upload, patch("builtins.print"):
            m.main(["claude", "--claude-50-only", "--folder", str(self.folder),
                    "--questions", str(question), "--max-output-tokens", "12000", "--execute"])
            upload.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, "repetir"):
                m.main(["claude", "--claude-50-only", "--folder", str(self.folder),
                        "--questions", str(question), "--max-output-tokens", "12000", "--execute"])
        self.assertEqual([url for url, _ in calls], [m.ANTHROPIC + "/messages"])
        self.assertEqual(m.read_json(old_openai)["id"], "resp-ja-concluida")
        self.assertTrue((m.result_folder(self.folder, False, claude_50_only=True) /
                         "claude_response.md").is_file())

    def test_claude_50_rejects_master_or_both(self):
        with self.assertRaises(SystemExit):
            m.main(["both", "--claude-50-only", "--max-output-tokens", "12000", "--execute",
                    "--folder", str(self.folder)])
        with self.assertRaises(SystemExit):
            m.main(["claude", "--claude-50-only", "--with-master",
                    "--max-output-tokens", "12000", "--execute", "--folder", str(self.folder)])

    def test_selection_validates_53_existing_ids(self):
        self.assertEqual(len(m.selection(self.folder)), 53)
        self.assertEqual(len({e["file_id"] for e in m.selection(self.folder)}), 53)

    def test_prepare_is_resumable_and_does_not_upload_to_openai(self):
        state = self.ready()
        with patch.object(m, "upload_claude") as upload, patch("builtins.print"):
            again = m.prepare(self.folder, self.entries)
        upload.assert_not_called()
        self.assertEqual(len(state["files"]), len(again["files"]))
        self.assertEqual(len(m.prepared(self.folder, self.entries)["files"]), 53)

    def test_preflight_optionally_requires_budget_but_inference_requires_only_limit(self):
        with self.assertRaises(SystemExit):
            m.main(["preflight", "--folder", str(self.folder)])
        with self.assertRaises(SystemExit):
            m.main(["openai", "--folder", str(self.folder), "--execute"])
        self.assertFalse((self.folder / "comparacao_h0_teste3/openai_response.json").exists())

    def test_direct_paid_inference_does_not_call_preflight_or_upload(self):
        state = self.ready()
        calls = []
        def fake_api(url, method, headers, body=None, raw=False, timeout=600):
            calls.append(url)
            if url.endswith("/responses"):
                return {"id": "resp-direct", "status": "completed", "model": m.MODEL_OPENAI,
                        "output": [{"content": [{"type": "output_text", "text": "Resultado direto"}]}]}
            raise AssertionError("Chamada extra proibida: " + url)
        self.assertFalse((self.folder / "comparacao_h0_teste3/preflight.json").exists())
        with patch.object(m, "api", side_effect=fake_api), patch.object(m, "auth", return_value={}), \
             patch.object(m, "upload_claude") as upload, patch("builtins.print"):
            m.run_one(self.folder, self.entries, state, self.text, self.model,
                      self.output, None, "openai")
            upload.assert_not_called()
        self.assertEqual(calls, [m.OPENAI + "/responses"])
        self.assertTrue((self.folder / "comparacao_h0_teste3/openai_response.json").exists())

    def test_preflight_counts_both_and_single_paid_call_each(self):
        state = self.ready()
        observed = []
        def fake_api(url, method, headers, body=None, raw=False, timeout=600):
            observed.append(url)
            if url.endswith("/input_tokens"):
                self.assertEqual(len(body["input"][0]["content"]), 54)
                return {"input_tokens": 180000}
            if url.endswith("/count_tokens"):
                self.assertEqual(len(body["messages"][0]["content"]), 54)
                self.assertEqual(body["messages"][0]["content"][0]["type"], "text")
                return {"input_tokens": 181000}
            if url.endswith("/responses"):
                self.assertEqual(len(body["input"][0]["content"]), 54)
                self.assertEqual(body["max_output_tokens"], self.output)
                return {"id": "resp-test", "status": "completed", "model": m.MODEL_OPENAI,
                        "usage": {"input_tokens": 180000, "output_tokens": 100},
                        "output": [{"content": [{"type": "output_text", "text": "Resultado OpenAI"}]}]}
            if url.endswith("/messages"):
                self.assertEqual(len(body["messages"][0]["content"]), 54)
                self.assertEqual(body["messages"][0]["content"][0]["source"]["type"], "file")
                self.assertEqual(body["max_tokens"], self.output)
                return {"id": "msg-test", "stop_reason": "end_turn", "model": self.model,
                        "usage": {"input_tokens": 181000, "output_tokens": 100},
                        "content": [{"type": "text", "text": "Resultado Claude"}]}
            raise AssertionError(url)
        with patch.object(m, "api", side_effect=fake_api), patch.object(m, "auth", return_value={}), patch("builtins.print"):
            m.preflight(self.folder, self.entries, state, self.text, self.model, self.output, self.budget)
            m.run_one(self.folder, self.entries, state, self.text, self.model, self.output, self.budget, "openai")
            m.run_one(self.folder, self.entries, state, self.text, self.model, self.output, self.budget, "claude")
            with self.assertRaisesRegex(RuntimeError, "repetir"):
                m.run_one(self.folder, self.entries, state, self.text, self.model, self.output, self.budget, "openai")
        self.assertEqual(observed.count(m.OPENAI + "/responses"), 1)
        self.assertEqual(observed.count(m.ANTHROPIC + "/messages"), 1)
        self.assertTrue((self.folder / "comparacao_h0_teste3/claude_response.md").exists())

    def test_docx_conversion_and_provenance(self):
        content = io.BytesIO()
        xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
               '<w:body><w:p><w:r><w:t>Contrato humano</w:t></w:r></w:p>'
               '<w:p><w:r><w:t>Evidence concreta</w:t></w:r></w:p>'
               '</w:body></w:document>')
        with zipfile.ZipFile(content, "w") as z:
            z.writestr("word/document.xml", xml)
        source = content.getvalue()
        converted = m.to_claude_text("reference/governanca.docx", source)
        self.assertIn("Contrato humano", converted.decode())
        self.assertIn("Evidence concreta", converted.decode())
        self.assertEqual(source, content.getvalue())
        self.assertNotEqual(m.digest(source), m.digest(converted))
        with self.assertRaises(RuntimeError):
            m.to_claude_text("reference/unknown.xlsx", b"binary")

    def test_bad_hash_blocks_before_external_upload(self):
        self.entries[0]["sha256"] = "0" * 64
        with patch.object(m, "upload_claude") as upload:
            with self.assertRaisesRegex(RuntimeError, "Fonte original indisponível"):
                m.prepare(self.folder, self.entries)
            upload.assert_not_called()

    def test_master_request_paths_and_isolation(self):
        state = self.ready()
        source = self.folder / "master.txt"
        sample = b"Master test content with concepts"
        source.write_bytes(sample)
        with patch.object(m, "MASTER_SHA256", m.digest(sample)):
            with patch.object(m, "upload_claude", return_value="file_claude_master"), patch("builtins.print"):
                m.stage_master(self.folder, state, source)
            state = m.prepared(self.folder, self.entries, with_master=True)
            oai, claude = m.requests(self.entries, state, self.text, self.model,
                                     self.output, with_master=True)
            self.assertEqual(len(oai["input"][0]["content"]), 54)  # 53 fontes + pergunta
            self.assertEqual(oai["tools"][0]["vector_store_ids"], [m.MASTER_STORE])
            self.assertEqual(oai["tool_choice"], "required")
            self.assertEqual(oai["include"], ["file_search_call.results"])
            self.assertEqual(len(claude["messages"][0]["content"]), 55)  # 53 + Master + pergunta
            self.assertEqual(claude["messages"][0]["content"][-2]["source"]["file_id"],
                             "file_claude_master")
            surrogate = m.claude_count_payload(self.folder, self.entries,
                                               self.text, self.model, True)
            self.assertEqual(len(surrogate["messages"][0]["content"]), 55)
            self.assertEqual(surrogate["messages"][0]["content"][-2]["type"], "text")
            self.assertEqual(m.result_folder(self.folder, True).name, "com_master")
            self.assertNotEqual(m.experiment_identity(self.entries, False),
                                m.experiment_identity(self.entries, True))

    def test_master_wrong_hash_blocks_upload(self):
        self.ready()
        source = self.folder / "bad-master.txt"
        source.write_bytes(b"not the approved Master")
        with patch.object(m, "upload_claude") as uploaded, patch("builtins.print"):
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                m.prepare(self.folder, self.entries, with_master=True, master_txt=source)
            uploaded.assert_not_called()

    def test_openai_master_verification_checks_metadata_without_content_download(self):
        observed = []
        def fake_api(url, method, headers, body=None, raw=False, timeout=600):
            observed.append(url)
            if url.endswith(m.MASTER_STORE):
                return {"status": "completed", "file_counts": {"failed": 0}}
            if url.endswith("/files?limit=100"):
                return {"data": [{"id": m.MASTER_OPENAI_FILE, "status": "completed"}]}
            if url.endswith("/files/" + m.MASTER_OPENAI_FILE):
                return {"filename": m.MASTER_NAME, "bytes": m.MASTER_BYTES}
            raise AssertionError("Download proibido ou URL inesperada: " + url)
        with patch.object(m, "api", side_effect=fake_api), patch.object(m, "auth", return_value={}):
            m.verify_openai_master()
        self.assertEqual(len(observed), 3)
        self.assertTrue(all(not url.endswith("/content") for url in observed))
        def bad_metadata(url, *args, **kwargs):
            result = fake_api(url, *args, **kwargs)
            if url.endswith("/files/" + m.MASTER_OPENAI_FILE):
                return {**result, "bytes": -1}
            return result
        with patch.object(m, "api", side_effect=bad_metadata), patch.object(m, "auth", return_value={}):
            with self.assertRaisesRegex(RuntimeError, "Metadados"):
                m.verify_openai_master()

    def test_original_sources_are_found_locally_without_openai_download(self):
        rec = self.entries[0]
        local_data = self.folder / "data" / "input" / rec["path"]
        local_data.parent.mkdir(parents=True, exist_ok=True)
        local_data.write_bytes(f"corpus-0".encode())
        direct = self.folder / rec["path"]
        direct.unlink()
        fake_file = str(self.folder / "experiments" / "esm-121" / "dual_provider.py")
        with patch.object(m, "__file__", fake_file), patch.object(m, "api") as api:
            text, cache = m.source_bytes(self.folder, rec)
            self.assertEqual(text, b"corpus-0")
            self.assertTrue(cache.is_file())
            api.assert_not_called()

    def test_missing_local_source_stops_without_api_download(self):
        rec = self.entries[0]
        (self.folder / rec["path"]).unlink()
        fake_file = str(self.folder / "experiments" / "esm-121" / "dual_provider.py")
        with patch.object(m, "__file__", fake_file), patch.object(m, "api") as api:
            with self.assertRaisesRegex(RuntimeError, "user_data"):
                m.source_bytes(self.folder, rec)
            api.assert_not_called()

    def test_prepare_checks_all_sources_before_uploading_to_claude(self):
        self.entries[-1]["sha256"] = "0" * 64
        with patch.object(m, "upload_claude") as upload:
            with self.assertRaisesRegex(RuntimeError, "Fonte original indisponível"):
                m.prepare(self.folder, self.entries)
            upload.assert_not_called()

    def test_claude_master_metadata_must_match_prepared_bytes(self):
        state = self.ready()
        sample = b"master sample"
        path = self.folder / "master.txt"
        path.write_bytes(sample)
        with patch.object(m, "MASTER_SHA256", m.digest(sample)):
            with patch.object(m, "upload_claude", return_value="file_master"), patch("builtins.print"):
                m.stage_master(self.folder, state, path)
            state = m.prepared(self.folder, self.entries, with_master=True)
            remote = {"id": "file_master", "filename": m.MASTER_NAME, "size_bytes": len(sample)}
            with patch.object(m, "api", return_value=remote), patch.object(m, "auth", return_value={}):
                m.verify_claude_master(state, self.folder)
            with patch.object(m, "api", return_value={**remote, "size_bytes": 0}), \
                 patch.object(m, "auth", return_value={}):
                with self.assertRaisesRegex(RuntimeError, "tamanho divergente"):
                    m.verify_claude_master(state, self.folder)

    def test_master_preflight_and_missing_retrieval_block_retry(self):
        state = self.ready()
        sample = b"Master reasoning sample"
        source = self.folder / "master.txt"
        source.write_bytes(sample)
        with patch.object(m, "MASTER_SHA256", m.digest(sample)):
            with patch.object(m, "upload_claude", return_value="file_master"), patch("builtins.print"):
                m.stage_master(self.folder, state, source)
            state = m.prepared(self.folder, self.entries, with_master=True)
            def fake_api(url, method, headers, body=None, raw=False, timeout=600):
                if url.endswith("/input_tokens"):
                    self.assertEqual(body["tools"][0]["vector_store_ids"], [m.MASTER_STORE])
                    return {"input_tokens": 180000}
                if url.endswith("/count_tokens"):
                    self.assertEqual(body["messages"][0]["content"][-2]["type"], "text")
                    return {"input_tokens": 360000}
                if url.endswith("/responses"):
                    return {"id": "resp-test", "status": "completed", "model": m.MODEL_OPENAI,
                            "output": [{"type": "message", "content": [
                                {"type": "output_text", "text": "Without retrieval"}]}]}
                raise AssertionError(url)
            with patch.object(m, "verify_openai_master"), \
                 patch.object(m, "verify_claude_master"), \
                 patch.object(m, "api", side_effect=fake_api), \
                 patch.object(m, "auth", return_value={}), patch("builtins.print"):
                m.preflight(self.folder, self.entries, state, self.text, self.model,
                            self.output, self.budget, with_master=True,
                            search_token_reserve=20000)
                self.assertTrue((m.result_folder(self.folder, True) / "preflight.json").exists())
                with self.assertRaisesRegex(RuntimeError, "sem resultado recuperado"):
                    m.run_one(self.folder, self.entries, state, self.text,
                              self.model, self.output, self.budget, "openai",
                              with_master=True, search_token_reserve=20000)
            self.assertTrue((m.result_folder(self.folder, True) / "openai.pending.json").exists())
            self.assertTrue((m.result_folder(self.folder, True) / "openai_response.json").exists())

if __name__ == "__main__":
    unittest.main()
