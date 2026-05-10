"""50-user internal-beta load check for the PRD10 Mydow stack.

The script drives real HTTP endpoints against a running app. It does not mock
LLM, storage, auth, database, or background jobs. Use it before opening a
larger beta to catch regressions in auth isolation, capture persistence,
search, AI chat, uploads, and Skill job handling.

Examples:

    python scripts/prd10_beta_load_check.py --base-url http://localhost:8000
    python scripts/prd10_beta_load_check.py --users 50 --concurrency 10 --include-ai --include-skills
    python scripts/prd10_beta_load_check.py --users 10 --skip-ai --skip-skills
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


DEFAULT_OUTPUT = Path("tests/integration/api/prd10/beta_load_latest.json")


@dataclass
class RequestSample:
    name: str
    status: int
    ok: bool
    elapsed_ms: float
    detail: str | None = None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[idx]


def _extract_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


class ScenarioClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        samples: list[RequestSample],
        *,
        user_index: int,
    ) -> None:
        self.client = client
        self.samples = samples
        self.user_index = user_index
        self.headers: dict[str, str] = {}

    async def request(
        self,
        method: str,
        url: str,
        *,
        name: str,
        expected: set[int] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        expected = expected or {200, 201, 202, 204}
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.update(self.headers)
        start = time.perf_counter()
        detail: str | None = None
        try:
            response = await self.client.request(
                method,
                url,
                headers=headers,
                **kwargs,
            )
            ok = response.status_code in expected
            if not ok:
                detail = response.text[:300]
        except Exception as exc:  # pragma: no cover - real network failure path
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.samples.append(
                RequestSample(
                    name=name,
                    status=0,
                    ok=False,
                    elapsed_ms=elapsed_ms,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        self.samples.append(
            RequestSample(
                name=name,
                status=response.status_code,
                ok=ok,
                elapsed_ms=elapsed_ms,
                detail=detail,
            )
        )
        return response

    async def register(self) -> None:
        suffix = f"{int(time.time())}-{self.user_index}-{uuid.uuid4().hex[:8]}"
        email = f"beta-{suffix}@example.com"
        username = f"beta_{self.user_index}_{uuid.uuid4().hex[:8]}"
        response = await self.request(
            "POST",
            "/api/v1/auth/register",
            name="auth.register",
            json={
                "email": email,
                "username": username,
                "password": "Beta-load-12345",
            },
            expected={201},
        )
        token = response.json().get("access_token")
        if not token:
            raise RuntimeError(f"register did not return access_token: {response.text[:300]}")
        self.headers = {"Authorization": f"Bearer {token}"}

    async def run_core_flow(
        self,
        *,
        include_ai: bool,
        include_skills: bool,
        include_link: bool,
        skill_poll_seconds: float,
    ) -> None:
        await self.register()
        title = f"Beta load insight {self.user_index} {uuid.uuid4().hex[:6]}"
        content = (
            f"{title}: internal beta pressure record. "
            "The product must persist raw text, title, summary, tags, "
            "knowledge-base document assets, search index rows, and timestamps."
        )

        await self.request("GET", "/health", name="health", expected={200})
        await self.request("GET", "/api/v1/today", name="today.get")
        await self.request("GET", "/api/v1/kb/folders", name="kb.folders")

        capture = await self.request(
            "POST",
            "/api/v1/capture/text",
            name="capture.text",
            json={
                "content": content,
                "title": title,
                "tags": ["beta-load", "prd10"],
                "auto_process": True,
            },
        )
        capture_data = _extract_data(capture.json())
        document_id = capture_data.get("document_id") if isinstance(capture_data, dict) else None

        await self.request(
            "GET",
            "/api/v1/search",
            name="search.query",
            params={"q": title, "page_size": 5, "mine_only": "true"},
        )
        await self.request(
            "GET",
            "/api/v1/search/suggestions",
            name="search.suggestions",
            params={"q": "Beta", "limit": 5},
        )
        await self.request("GET", "/api/v1/feed", name="feed.get")
        await self.request("GET", "/api/v1/kb/documents", name="kb.documents")

        presign = await self.request(
            "POST",
            "/api/v1/uploads/presign",
            name="uploads.presign",
            json={
                "filename": f"beta-{self.user_index}.txt",
                "mime_type": "text/plain",
                "size_bytes": len(content.encode("utf-8")),
            },
        )
        presign_data = _extract_data(presign.json())
        upload_id = presign_data.get("upload_id") if isinstance(presign_data, dict) else None
        if upload_id:
            await self.request(
                "PUT",
                f"/api/v1/uploads/local/{upload_id}",
                name="uploads.put",
                content=content.encode("utf-8"),
                headers={"Content-Type": "text/plain", "X-Filename": f"beta-{self.user_index}.txt"},
            )
            await self.request(
                "POST",
                "/api/v1/capture/file/commit",
                name="capture.file.commit",
                json={
                    "upload_id": upload_id,
                    "filename": f"beta-{self.user_index}.txt",
                    "mime_type": "text/plain",
                    "size_bytes": len(content.encode("utf-8")),
                },
            )

        if include_link:
            await self.request(
                "POST",
                "/api/v1/capture/link",
                name="capture.link",
                json={
                    "url": "https://example.com/",
                    "note": f"beta load link user {self.user_index}",
                    "tags": ["beta-load", "web-clip"],
                },
            )

        if include_ai:
            conversation = await self.request(
                "POST",
                "/api/v1/ai/conversations",
                name="ai.conversation.create",
                json={
                    "title": f"Beta load chat {self.user_index}",
                    "context_scope": {
                        "document_ids": [document_id] if document_id else [],
                        "include_recent": True,
                    },
                },
                expected={201},
            )
            conversation_data = _extract_data(conversation.json())
            conversation_id = conversation_data.get("id") if isinstance(conversation_data, dict) else None
            if conversation_id:
                await self.request(
                    "POST",
                    f"/api/v1/ai/conversations/{conversation_id}/messages",
                    name="ai.message",
                    json={
                        "content": "请基于我的知识库资料，用三条要点总结刚刚保存的内测记录。",
                        "context_scope": {
                            "document_ids": [document_id] if document_id else [],
                            "include_recent": True,
                        },
                    },
                    expected={201},
                )

        if include_skills:
            skills = await self.request(
                "GET",
                "/api/v1/skills",
                name="skills.list",
                params={"page_size": 5},
            )
            skill_data = _extract_data(skills.json())
            items = []
            if isinstance(skill_data, dict):
                items = skill_data.get("items") or []
            if items:
                skill_id = items[0].get("id")
                if skill_id:
                    run = await self.request(
                        "POST",
                        f"/api/v1/skills/{skill_id}/run",
                        name="skills.run",
                        json={
                            "input": {
                                "text": content,
                                "document_ids": [document_id] if document_id else [],
                            },
                            "save_output": "kb",
                        },
                        expected={202},
                    )
                    run_data = _extract_data(run.json())
                    run_id = run_data.get("skill_run_id") if isinstance(run_data, dict) else None
                    if run_id:
                        await self.poll_skill_run(run_id, timeout_seconds=skill_poll_seconds)

    async def poll_skill_run(self, run_id: str, *, timeout_seconds: float) -> None:
        deadline = time.perf_counter() + timeout_seconds
        while True:
            response = await self.request(
                "GET",
                f"/api/v1/skills/runs/{run_id}",
                name="skills.run.detail",
            )
            payload = _extract_data(response.json())
            status = payload.get("status") if isinstance(payload, dict) else None
            if status in {"completed", "failed", "canceled"}:
                return
            if time.perf_counter() >= deadline:
                self.samples.append(
                    RequestSample(
                        name="skills.run.timeout",
                        status=0,
                        ok=False,
                        elapsed_ms=timeout_seconds * 1000,
                        detail=f"SkillRun {run_id} did not finish within {timeout_seconds}s",
                    )
                )
                return
            await asyncio.sleep(1.0)


async def run_load(args: argparse.Namespace) -> dict[str, Any]:
    samples: list[RequestSample] = []
    sem = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        timeout=httpx.Timeout(args.timeout),
        follow_redirects=True,
    ) as client:
        async def run_one(user_index: int) -> None:
            async with sem:
                scenario_started = time.perf_counter()
                scenario = ScenarioClient(client, samples, user_index=user_index)
                try:
                    await scenario.run_core_flow(
                        include_ai=args.include_ai,
                        include_skills=args.include_skills,
                        include_link=args.include_link,
                        skill_poll_seconds=args.skill_poll_seconds,
                    )
                finally:
                    scenario_elapsed = (time.perf_counter() - scenario_started) * 1000
                    samples.append(
                        RequestSample(
                            name="scenario.total",
                            status=200,
                            ok=(
                                scenario_elapsed
                                <= args.fail_scenario_p95_seconds * 1000
                            ),
                            elapsed_ms=scenario_elapsed,
                            detail=(
                                None
                                if scenario_elapsed
                                <= args.fail_scenario_p95_seconds * 1000
                                else (
                                    f"user flow exceeded "
                                    f"{args.fail_scenario_p95_seconds:.0f}s"
                                )
                            ),
                        )
                    )

        started = time.perf_counter()
        tasks = [asyncio.create_task(run_one(i + 1)) for i in range(args.users)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.perf_counter() - started

    for result in results:
        if isinstance(result, Exception):
            samples.append(
                RequestSample(
                    name="scenario.exception",
                    status=0,
                    ok=False,
                    elapsed_ms=0,
                    detail=f"{type(result).__name__}: {result}",
                )
            )

    by_name: dict[str, list[RequestSample]] = {}
    for sample in samples:
        by_name.setdefault(sample.name, []).append(sample)

    per_endpoint = {}
    for name, rows in sorted(by_name.items()):
        latencies = [row.elapsed_ms for row in rows if row.elapsed_ms >= 0]
        failures = [row for row in rows if not row.ok]
        per_endpoint[name] = {
            "count": len(rows),
            "ok": len(rows) - len(failures),
            "failed": len(failures),
            "p95_ms": round(_p95(latencies), 2),
            "max_ms": round(max(latencies), 2) if latencies else 0,
            "failure_samples": [row.detail for row in failures[:5] if row.detail],
        }

    total = len(samples)
    failed = len([sample for sample in samples if not sample.ok])
    latencies = [sample.elapsed_ms for sample in samples]
    error_rate = failed / total if total else 1.0
    p95_ms = _p95(latencies)
    scenario_latencies = [
        sample.elapsed_ms
        for sample in samples
        if sample.name == "scenario.total"
    ]
    scenario_p95_ms = _p95(scenario_latencies)

    passed = (
        error_rate <= args.fail_error_rate
        and p95_ms <= args.fail_p95_ms
        and scenario_p95_ms <= args.fail_scenario_p95_seconds * 1000
    )

    report = {
        "started_at": _now_iso(),
        "base_url": args.base_url,
        "users": args.users,
        "concurrency": args.concurrency,
        "include_ai": args.include_ai,
        "include_skills": args.include_skills,
        "include_link": args.include_link,
        "elapsed_seconds": round(elapsed, 2),
        "total_requests": total,
        "failed_requests": failed,
        "error_rate": round(error_rate, 4),
        "p95_ms": round(p95_ms, 2),
        "scenario_p95_ms": round(scenario_p95_ms, 2),
        "max_ms": round(max(latencies), 2) if latencies else 0,
        "thresholds": {
            "fail_p95_ms": args.fail_p95_ms,
            "fail_error_rate": args.fail_error_rate,
            "fail_scenario_p95_seconds": args.fail_scenario_p95_seconds,
        },
        "passed": passed,
        "per_endpoint": per_endpoint,
        "failures": [asdict(sample) for sample in samples if not sample.ok][:30],
    }
    return report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fail-p95-ms", type=float, default=30000.0)
    parser.add_argument("--fail-error-rate", type=float, default=0.02)
    parser.add_argument("--fail-scenario-p95-seconds", type=float, default=300.0)
    parser.add_argument("--skill-poll-seconds", type=float, default=90.0)
    parser.add_argument("--include-ai", dest="include_ai", action="store_true", default=True)
    parser.add_argument("--skip-ai", dest="include_ai", action="store_false")
    parser.add_argument("--include-skills", dest="include_skills", action="store_true", default=True)
    parser.add_argument("--skip-skills", dest="include_skills", action="store_false")
    parser.add_argument("--include-link", action="store_true", default=False)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.users < 1:
        raise SystemExit("--users must be >= 1")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be >= 1")

    report = asyncio.run(run_load(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    status = "PASS" if report["passed"] else "FAIL"
    print(
        f"{status} users={report['users']} requests={report['total_requests']} "
        f"failed={report['failed_requests']} p95={report['p95_ms']}ms "
        f"scenario_p95={report['scenario_p95_ms']}ms "
        f"elapsed={report['elapsed_seconds']}s output={args.output}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
