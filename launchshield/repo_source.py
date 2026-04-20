"""Fetch public GitHub repository trees and source file contents.

Provides a mock provider that is deterministic and useful for demos,
plus a real GitHub provider skeleton activated when `USE_REAL_GITHUB=true`.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Protocol, Tuple
from urllib.parse import urlparse

import httpx

from .config import AppConfig, get_config
from .models import ProviderMode, ProviderSource

ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".html",
    ".env.example",
}

PRIORITY_DIRS = (
    "src/",
    "app/",
    "server/",
    "api/",
    "lib/",
    "config/",
    ".github/workflows/",
)


@dataclass
class RepoFile:
    path: str
    language: str
    content: str


class RepoSource(Protocol):
    async def list_files(self, repo_url: str) -> List[str]: ...
    async def read_file(self, repo_url: str, path: str) -> RepoFile: ...
    async def list_manifests(self, repo_url: str) -> List[RepoFile]: ...


def _language_for(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".py"):
        return "python"
    if lower.endswith((".js", ".jsx")):
        return "javascript"
    if lower.endswith((".ts", ".tsx")):
        return "typescript"
    if lower.endswith(".json"):
        return "json"
    if lower.endswith((".yaml", ".yml")):
        return "yaml"
    if lower.endswith(".toml"):
        return "toml"
    if lower.endswith(".html"):
        return "html"
    return "text"


def _extension(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".env.example"):
        return ".env.example"
    dot = lower.rfind(".")
    if dot == -1:
        return ""
    return lower[dot:]


def is_allowed_path(path: str) -> bool:
    if _extension(path) not in ALLOWED_EXTENSIONS:
        return False
    return True


def priority_sort(paths: Iterable[str]) -> List[str]:
    def _key(path: str) -> Tuple[int, str]:
        for i, prefix in enumerate(PRIORITY_DIRS):
            if path.startswith(prefix):
                return (i, path)
        return (len(PRIORITY_DIRS), path)

    return sorted(paths, key=_key)


_GITHUB_URL = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


def parse_github_url(url: str) -> Tuple[str, str]:
    match = _GITHUB_URL.match(url.strip())
    if not match:
        raise ValueError(f"not a public GitHub repo URL: {url}")
    return match.group("owner"), match.group("repo")


MOCK_FILES: List[RepoFile] = [
    RepoFile(
        path="src/app/main.py",
        language="python",
        content=(
            "import os\n"
            "from flask import Flask, request\n\n"
            "app = Flask(__name__)\n"
            "app.config['DEBUG'] = True\n"
            "SECRET_KEY = 'sk-live-ABCDEFG1234567890HIJKLMN'\n\n"
            "@app.route('/run')\n"
            "def run_cmd():\n"
            "    cmd = request.args.get('cmd')\n"
            "    return eval(cmd)\n"
        ),
    ),
    RepoFile(
        path="src/app/shell_utils.py",
        language="python",
        content=(
            "import os\n"
            "def run(target):\n"
            "    os.system('ping ' + target)\n"
        ),
    ),
    RepoFile(
        path="src/app/settings.py",
        language="python",
        content=(
            "ALLOWED_ORIGINS = ['*']\n"
            "DEBUG = True\n"
            "DATABASE_URL = 'postgres://admin:hunter2@db/prod'\n"
        ),
    ),
    RepoFile(
        path="src/app/auth.py",
        language="python",
        content=(
            "import pickle\n"
            "def load_session(data):\n"
            "    return pickle.loads(data)\n"
        ),
    ),
    RepoFile(
        path="src/app/redirect.py",
        language="python",
        content=(
            "from flask import redirect, request\n"
            "def go():\n"
            "    return redirect(request.args.get('next'))\n"
        ),
    ),
    RepoFile(
        path="src/web/home.jsx",
        language="javascript",
        content=(
            "export function Home({html}){\n"
            "  const ref = useRef();\n"
            "  useEffect(()=>{ ref.current.innerHTML = html; }, [html]);\n"
            "  return <div ref={ref}/>;\n"
            "}\n"
        ),
    ),
    RepoFile(
        path="src/web/env.tsx",
        language="typescript",
        content=(
            "export default function Env(){\n"
            "  return <pre>{JSON.stringify(process.env)}</pre>;\n"
            "}\n"
        ),
    ),
    RepoFile(
        path="src/web/login.tsx",
        language="typescript",
        content=(
            "const API_KEY = 'sk-test-51LaunchShieldDemoVulnerableKey';\n"
            "export const endpoint = 'http://internal.demo/login';\n"
        ),
    ),
    RepoFile(
        path="app/server.js",
        language="javascript",
        content=(
            "const express = require('express');\n"
            "const app = express();\n"
            "app.use((req,res,next)=>{\n"
            "  res.header('Access-Control-Allow-Origin','*');\n"
            "  next();\n"
            "});\n"
            "app.get('/exec',(req,res)=>{ eval(req.query.code); });\n"
        ),
    ),
    RepoFile(
        path="app/routes/redirect.js",
        language="javascript",
        content=(
            "module.exports = (req,res)=> res.redirect(req.query.u);\n"
        ),
    ),
    RepoFile(
        path="api/payments.ts",
        language="typescript",
        content=(
            "export async function refund(user: any){\n"
            "  return eval('processor.'+user.method+'(user)');\n"
            "}\n"
        ),
    ),
    RepoFile(
        path="api/profile.ts",
        language="typescript",
        content=(
            "export function renderBio(el: HTMLElement, bio: string){\n"
            "  el.innerHTML = bio;\n"
            "}\n"
        ),
    ),
    RepoFile(
        path="lib/utils/logger.py",
        language="python",
        content=(
            "import logging\n"
            "logging.basicConfig(level=logging.DEBUG)\n"
        ),
    ),
    RepoFile(
        path="lib/net/client.py",
        language="python",
        content=(
            "import os\n"
            "def fetch(host):\n"
            "    os.system(f'curl -sS {host}')\n"
        ),
    ),
    RepoFile(
        path="lib/crypto/tokens.py",
        language="python",
        content=(
            "JWT_SECRET = 'super-secret-jwt-value-do-not-leak'\n"
        ),
    ),
    RepoFile(
        path="config/env.yaml",
        language="yaml",
        content=(
            "debug: true\n"
            "allow_origins: '*'\n"
            "aws_access_key_id: AKIAABCDEFGHIJKLMNOP\n"
        ),
    ),
    RepoFile(
        path="config/deploy.toml",
        language="toml",
        content=(
            "[app]\n"
            "debug = true\n"
            "\n"
            "[secrets]\n"
            "stripe = \"" + "sk" + "_live_" + "abcdefGHIJKLMNOP1234567890\"\n"
        ),
    ),
    RepoFile(
        path="config/cors.json",
        language="json",
        content=('{"allow_origins": ["*"], "allow_credentials": true}\n'),
    ),
    RepoFile(
        path=".github/workflows/deploy.yml",
        language="yaml",
        content=(
            "jobs:\n"
            "  deploy:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: echo \"DEPLOY_KEY=$DEPLOY_KEY\" > ~/.ssh/id_rsa\n"
        ),
    ),
    RepoFile(
        path=".github/workflows/ci.yml",
        language="yaml",
        content=(
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: npm test -- --reporter dot\n"
        ),
    ),
    RepoFile(
        path=".env.example",
        language="text",
        content=(
            "DATABASE_URL=postgres://admin:hunter2@db/prod\n"
            "SECRET_KEY=replace-me\n"
            "STRIPE_KEY=" + "sk" + "_test_" + "51LaunchShieldVulnerablePlayground\n"
        ),
    ),
    RepoFile(
        path="server/handlers/admin.ts",
        language="typescript",
        content=(
            "export function adminOnly(req,res,next){\n"
            "  if(req.headers['x-admin']==='yes') return next();\n"
            "  res.status(401).end();\n"
            "}\n"
        ),
    ),
    RepoFile(
        path="server/handlers/upload.py",
        language="python",
        content=(
            "import yaml\n"
            "def parse_config(body):\n"
            "    return yaml.load(body)\n"
        ),
    ),
    RepoFile(
        path="server/handlers/search.py",
        language="python",
        content=(
            "def search(db, q):\n"
            "    return db.query(f\"SELECT * FROM items WHERE name = '{q}'\")\n"
        ),
    ),
    RepoFile(
        path="src/app/helpers/xml.py",
        language="python",
        content=(
            "from xml.etree.ElementTree import fromstring\n"
            "def parse(body):\n"
            "    return fromstring(body)\n"
        ),
    ),
]

MOCK_MANIFESTS: List[RepoFile] = [
    RepoFile(
        path="requirements.txt",
        language="text",
        content=(
            "flask==1.1.4\n"
            "requests==2.19.1\n"
            "pyyaml==5.3\n"
            "jinja2==2.10\n"
            "pillow==8.1.1\n"
            "cryptography==3.2\n"
            "urllib3==1.24.1\n"
            "django==2.2.3\n"
            "numpy==1.19.5\n"
            "pandas==1.1.0\n"
        ),
    ),
    RepoFile(
        path="package.json",
        language="json",
        content=(
            '{\n'
            '  "name": "launchshield-demo",\n'
            '  "version": "0.1.0",\n'
            '  "dependencies": {\n'
            '    "lodash": "4.17.11",\n'
            '    "express": "4.16.0",\n'
            '    "minimist": "1.2.0",\n'
            '    "axios": "0.21.0",\n'
            '    "moment": "2.24.0",\n'
            '    "jquery": "3.3.1",\n'
            '    "handlebars": "4.0.11",\n'
            '    "serialize-javascript": "2.1.1"\n'
            '  }\n'
            '}\n'
        ),
    ),
    RepoFile(
        path="pyproject.toml",
        language="toml",
        content=(
            "[project]\n"
            "name = \"launchshield-demo\"\n"
            "version = \"0.1.0\"\n"
            "dependencies = []\n"
        ),
    ),
]


class MockRepoSource:
    def __init__(self, config: AppConfig):
        self._config = config

    async def list_files(self, repo_url: str) -> List[str]:
        await asyncio.sleep(self._config.demo_pace_seconds * 0.2)
        return priority_sort([f.path for f in MOCK_FILES if is_allowed_path(f.path)])

    async def read_file(self, repo_url: str, path: str) -> RepoFile:
        await asyncio.sleep(self._config.demo_pace_seconds * 0.15)
        for f in MOCK_FILES:
            if f.path == path:
                return f
        raise FileNotFoundError(path)

    async def list_manifests(self, repo_url: str) -> List[RepoFile]:
        await asyncio.sleep(self._config.demo_pace_seconds * 0.15)
        return list(MOCK_MANIFESTS)


class GithubRepoSource:
    """Real GitHub provider using the Tree + contents APIs.

    Lightweight: pulls the default branch tree once, then downloads individual
    files on demand via the raw content endpoint. Uses `GITHUB_TOKEN` when
    available to survive rate limits.
    """

    def __init__(self, config: AppConfig):
        self._config = config
        headers = {"Accept": "application/vnd.github+json"}
        if config.github_token:
            headers["Authorization"] = f"Bearer {config.github_token}"
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com", headers=headers, timeout=20.0
        )
        self._raw = httpx.AsyncClient(timeout=20.0)
        self._default_branch_cache: dict[str, str] = {}
        self._tree_cache: dict[str, List[str]] = {}

    async def _default_branch(self, owner: str, repo: str) -> str:
        key = f"{owner}/{repo}"
        if key in self._default_branch_cache:
            return self._default_branch_cache[key]
        resp = await self._client.get(f"/repos/{owner}/{repo}")
        resp.raise_for_status()
        branch = resp.json().get("default_branch", "main")
        self._default_branch_cache[key] = branch
        return branch

    async def _tree(self, owner: str, repo: str) -> List[str]:
        key = f"{owner}/{repo}"
        if key in self._tree_cache:
            return self._tree_cache[key]
        branch = await self._default_branch(owner, repo)
        resp = await self._client.get(
            f"/repos/{owner}/{repo}/git/trees/{branch}", params={"recursive": "1"}
        )
        resp.raise_for_status()
        data = resp.json()
        paths = [item["path"] for item in data.get("tree", []) if item.get("type") == "blob"]
        self._tree_cache[key] = paths
        return paths

    async def list_files(self, repo_url: str) -> List[str]:
        owner, repo = parse_github_url(repo_url)
        paths = await self._tree(owner, repo)
        return priority_sort([p for p in paths if is_allowed_path(p)])

    async def read_file(self, repo_url: str, path: str) -> RepoFile:
        owner, repo = parse_github_url(repo_url)
        branch = await self._default_branch(owner, repo)
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        resp = await self._raw.get(raw_url)
        resp.raise_for_status()
        return RepoFile(path=path, language=_language_for(path), content=resp.text)

    async def list_manifests(self, repo_url: str) -> List[RepoFile]:
        owner, repo = parse_github_url(repo_url)
        paths = await self._tree(owner, repo)
        manifest_names = {"requirements.txt", "pyproject.toml", "package.json", "package-lock.json"}
        wanted = [p for p in paths if p.split("/")[-1] in manifest_names]
        out: List[RepoFile] = []
        for p in wanted[:6]:
            try:
                out.append(await self.read_file(repo_url, p))
            except httpx.HTTPError:
                continue
        return out

    async def aclose(self) -> None:
        await self._client.aclose()
        await self._raw.aclose()


def build_provider(config: Optional[AppConfig] = None) -> RepoSource:
    cfg = config or get_config()
    if cfg.use_real_github:
        return GithubRepoSource(cfg)
    return MockRepoSource(cfg)


def describe_provider(config: Optional[AppConfig] = None) -> ProviderSource:
    cfg = config or get_config()
    requested_mode = ProviderMode.REAL if cfg.use_real_github else ProviderMode.MOCK
    if cfg.use_real_github:
        detail = "GitHub API"
        if cfg.github_token:
            detail += " with token"
        else:
            detail += " anonymous rate limit"
        return ProviderSource(
            requested_mode=requested_mode,
            effective_mode=ProviderMode.REAL,
            provider="github-api",
            detail=detail,
        )
    return ProviderSource(
        requested_mode=requested_mode,
        effective_mode=ProviderMode.MOCK,
        provider="mock-repo",
        detail="Bundled repository fixture",
    )
