#!/usr/bin/env python3
"""Prepara um corpus factual da ESM-121 para baseline direto, sem LLM e sem Jira/GitHub writes.

Entrada Jira: ZIP privado de fontes primárias recuperadas via conector Atlassian.
Entrada GitHub: API de leitura autenticada no GitHub privado imaciel-123/esm.
Saída: data/input somente se o gate for satisfeito e --activate for indicado.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from zipfile import ZipFile

REPO = "imaciel-123/esm"
PRS = [207, 211, 213, 214, 216, 219, 221, 222, 229]
REQUIRED_JIRA = [
    "jira/ESM-121_issue.md",
    *[f"jira/ESM-121_comment_{n}.md" for n in [10318,10326,10362,10384,10407]],
    "jira/ESM-121_changelog_22.md",
    "jira/ESM-121_attachments_meta.json",
]
ANCHOR_PATHS = [
    "src/components/change-materials-and-journey.test.ts",
    "src/components/change-materials-and-journey.tsx",
    "scripts/run-tests.mjs",
]
MAX_TOTAL = 49_000_000


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def gh_token():
    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.getenv(key):
            return os.environ[key].strip()
    if shutil.which("gh"):
        try:
            r = subprocess.run(["gh", "auth", "token"], check=True, capture_output=True,
                               text=True, timeout=15)
            if r.stdout.strip():
                return r.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            pass
    if shutil.which("git"):
        try:
            r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                               capture_output=True, text=True, timeout=15)
            for line in r.stdout.splitlines():
                if line.startswith("password="):
                    return line.partition("=")[2]
        except (subprocess.SubprocessError, OSError):
            pass
    raise RuntimeError(
        "Sem credencial GitHub. Faça 'gh auth login' (se tiver GitHub CLI) "
        "ou configure GH_TOKEN na sessão PowerShell. Não envie o token para o chat."
    )


class Github:
    def __init__(self, token):
        self.token = token
        self.reads = 0

    def get(self, endpoint, params=None, optional=False):
        url = "https://api.github.com/repos/" + REPO + endpoint
        if params:
            url += "?" + urlencode(params)
        req = Request(url, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "spike-llm-vF-source-collector"
        })
        try:
            with urlopen(req, timeout=45) as response:
                self.reads += 1
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if optional and exc.code == 404:
                return None
            raise RuntimeError(f"GitHub HTTP {exc.code}, endpoint {endpoint} (não repetir cegamente)") from exc

    def page(self, endpoint, params=None):
        found = []
        for page in range(1, 25):
            args = dict(params or {}, per_page=100, page=page)
            data = self.get(endpoint, args)
            if not isinstance(data, list):
                raise ValueError(f"Resposta não é lista: {endpoint}")
            found.extend(data)
            if len(data) < 100:
                break
        else:
            raise ValueError("Paginação GitHub excessiva: " + endpoint)
        return found


def save_source(folder, manifest, path, content, url, note=""):
    path = folder / path
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    if not data:
        raise ValueError("Fonte vazia: " + str(path))
    if path.exists():
        raise ValueError("Arquivo duplicado: " + str(path))
    path.write_bytes(data)
    manifest.append({
        "file": path.relative_to(folder).as_posix(),
        "sha256": sha256(data), "bytes": len(data),
        "source_url": url, "note": note,
    })


def record_json(folder, manifest, name, url, content):
    if content is None:
        # Ausência explicitada no ledger, não transformar ausência em fonte vazia.
        return
    wrapped = {"source_url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
               "source_kind": "github_api_read_only", "data": content}
    save_source(folder, manifest, "github/" + name, json.dumps(
        wrapped, ensure_ascii=False, indent=2) + "\n", url)


def build(folder, jira_zip, client):
    manifest = []
    with ZipFile(jira_zip) as archive:
        available = set(archive.namelist())
        missing = set(REQUIRED_JIRA) - available
        if missing:
            raise ValueError("ZIP Jira incompleto: " + ", ".join(sorted(missing)))
        for name in REQUIRED_JIRA:
            data = archive.read(name)
            save_source(folder, manifest, name, data,
                        "https://esmodel.atlassian.net/browse/ESM-121",
                        "Snapshot Jira recuperado via conector, sem anexos binários")
        # Referências conceituais consultadas na investigação original; são
        # documentos-fonte, não o relatório retrospectivo nem respostas da LLM.
        for name in sorted(n for n in available if n.startswith("reference/") and not n.endswith("/")):
            if ".." in Path(name).parts or Path(name).suffix.lower() not in {".docx", ".md", ".txt"}:
                raise ValueError("Referência inválida no ZIP: " + name)
            save_source(folder, manifest, name, archive.read(name),
                        "documento de referência fornecido pelo operador",
                        "Autoridade conceitual, não prova de eventos da ESM-121")

    count_commits = 0
    count_runs = 0
    for pr in PRS:
        prefix = f"PR-{pr}"
        endpoint = f"/pulls/{pr}"
        pr_data = client.get(endpoint)
        if pr_data.get("number") != pr or not pr_data.get("merged_at"):
            raise ValueError(f"PR {pr} ausente ou não integrada; nenhuma ativação")
        head = pr_data.get("head", {}).get("sha")
        merged = pr_data.get("merge_commit_sha")
        if not head or not merged:
            raise ValueError(f"Sem SHA head/merge na PR {pr}")
        record_json(folder, manifest, prefix+"_PR.json", pr_data["html_url"], pr_data)
        related = [
            ("commits", f"/pulls/{pr}/commits"),
            ("files", f"/pulls/{pr}/files"),
            ("reviews", f"/pulls/{pr}/reviews"),
            ("review_comments", f"/pulls/{pr}/comments"),
            ("issue_comments", f"/issues/{pr}/comments"),
        ]
        for kind, path in related:
            data = client.page(path)
            if kind == "commits":
                count_commits += len(data)
                if not data:
                    raise ValueError(f"PR {pr} sem commits")
            # Preservar listas vazias como observações da API no momento consultado.
            # Zero reviews nativos consultados não prova ausência de reviews externos.
            record_json(folder, manifest, prefix+"_"+kind+".json",
                        "https://api.github.com/repos/"+REPO+path, data)
        runs_data = client.get("/actions/runs",
                               {"head_sha": head, "per_page": 100, "event": "pull_request"})
        runs = runs_data.get("workflow_runs", [])
        count_runs += len(runs)
        record_json(folder, manifest, prefix+"_workflow_runs.json",
                    f"https://github.com/{REPO}/actions", {
                        "head_sha": head, "run_count": len(runs),
                        "workflow_runs": runs
                    })
        for run in runs:
            jobs = client.get(f"/actions/runs/{run['id']}/jobs", optional=True)
            if jobs is not None:
                record_json(folder, manifest, f"{prefix}_workflow_jobs_{run['id']}.json",
                            run.get("html_url", f"https://github.com/{REPO}/actions"),
                            jobs)
        print(f"PR #{pr}: commits, diff/arquivos, reviews e workflows recuperados", flush=True)

    # Duas fotografias históricas para testar o caso de regressão na PR #221,
    # usando o SHA do merge e não os arquivos atuais da main.
    for pr in [221, 229]:
        item = client.get(f"/pulls/{pr}")
        merge_sha = item["merge_commit_sha"]
        for path in ANCHOR_PATHS:
            try:
                response = client.get(f"/contents/{path}", {"ref": merge_sha}, optional=True)
                if not response:
                    continue
                if response.get("encoding") != "base64":
                    raise ValueError(f"GitHub não devolveu bytes de {path}@{merge_sha}")
                raw = base64.b64decode(response["content"])
                if not raw:
                    raise ValueError("Snapshot histórico vazio: " + path)
                # .txt reconhecido pela Responses API; conteúdo original preservado.
                name = f"github/snapshots/PR-{pr}__{path.replace('/', '__')}.txt"
                save_source(folder, manifest, name, raw,
                            f"https://github.com/{REPO}/blob/{merge_sha}/{path}",
                            f"Bytes do arquivo no SHA de merge da PR #{pr}")
            except RuntimeError as exc:
                raise RuntimeError(f"Erro recuperando snapshot {path} na PR {pr}") from exc

    paths = [x["file"] for x in manifest]
    total = sum(x["bytes"] for x in manifest)
    if len(paths) != len(set(paths)) or total >= MAX_TOTAL:
        raise ValueError("Duplicações ou limite próximo de 50 MB; nenhuma ativação.")
    return {
        "case":"ESM-121", "purpose":"same-case direct baseline",
        "source_repo":REPO, "pr_numbers":PRS,
        "jira_comments":5, "jira_changelog_entries":22, "jira_attachment_bytes":0,
        "github_pr_count":len(PRS), "github_pr_commit_count":count_commits,
        "github_workflow_run_count":count_runs, "github_api_reads":client.reads,
        "file_count":len(manifest), "total_bytes":total,
        "files":manifest,
        "limitations":[
            "Os cinco anexos Jira estão apenas listados por metadados, sem seus bytes.",
            "O registro histórico da edição de descrição da issue foi resumido no snapshot Jira.",
            "Reviews externos e logs íntegros dos workflows não foram recuperados.",
            "A descrição das PRs e outros campos mutáveis são snapshots atuais, não capturas retroativas de 31/10.",
            "O relatório anterior e a avaliação humana NÃO fazem parte do corpus.",
        ]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=Path, required=True, help="ZIP Jira privado ESM-121")
    parser.add_argument("--activate", action="store_true", help="Ativa este corpus em data/input")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if not args.seed.is_file():
        raise ValueError("Arquivo Jira privado não encontrado: " + str(args.seed))
    target = root / "data" / "esm121_candidate"
    if target.exists():
        raise ValueError("Corpus candidato já existe. Não sobrescrevo material existente: " + str(target))
    target.mkdir(parents=True)
    try:
        result = build(target, args.seed, Github(gh_token()))
        (root/"data"/"esm121_manifest.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print("ESM-121:",result["file_count"],"fontes,",
              result["github_pr_commit_count"],"commits,",
              result["github_workflow_run_count"],"workflow runs")
        if result["github_pr_commit_count"] != 39:
            raise ValueError("Contagem de commits difere de 39; investigar antes de ativar.")
        if result["github_workflow_run_count"] < 18:
            raise ValueError("Menos de 18 workflows recuperados; verificar filtro/tenancy.")
        if args.activate:
            active = root / "data" / "input"
            old = root / "data" / "archive" / (
                "input-before-esm121-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
            old.parent.mkdir(parents=True, exist_ok=True)
            if active.exists():
                active.rename(old)
            target.rename(active)
            print("CORPUS ATIVADO em data/input; material anterior preservado em",old)
        else:
            print("Material verificado, mas não ativado. Use --activate.")
        print("Pergunta original: experiments/esm-121/pergunta_original.md")
        print("Ainda NÃO houve chamada à OpenAI.",flush=True)
    except Exception:
        # Preserva o corpus parcial em caso de falha para diagnóstico local.
        print("NÃO ATIVADO: data/esm121_candidate preservado para inspeção.",file=sys.stderr)
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"BLOQUEADO: {exc}", file=sys.stderr)
        sys.exit(1)
