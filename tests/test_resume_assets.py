import hashlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LATEST_RESUME_SHA256 = "c09aadc2be6364a4ca47c615f0f1c2f7e0b8c1c841c10f2faefdb90cb215cf4e"


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_online_resume_tracks_latest_verified_content():
    resume = _read("templates/resume.html")

    for expected in (
        "更新于 2026.08",
        "AI Agent 开发 / Agent 后端开发",
        "2025.12 - 至今",
        "AgentRunner",
        "Direct / ReAct / Plan-Execute",
        "Recall@5 由 80.56% 提升至 93.33%",
        "600+",
        "168 条 / 26 类 Gold Dataset",
        "79 个页级证据块",
        "Human-in-the-loop QA 闭环",
    ):
        assert expected in resume

    for stale in (
        "更新于 2026.07",
        "255 项自动化测试",
        "平均单查询延迟约 29.4s",
        "Direct / Agentic 两级路由",
    ):
        assert stale not in resume


def test_project_seed_matches_resume_positioning():
    seed = _read("scripts/seed_projects.py")

    for expected in (
        "个人开源项目作者 / 维护者",
        '"duration": "2025.12 — 至今"',
        "30 条检索、12 条生成和 62 条 Agent 回归",
        "RAG 评测与 QA 闭环负责人",
        '"duration": "2026.01 — 2026.08"',
        "168 条 / 26 类 Gold Dataset",
        "中日双语链路",
    ):
        assert expected in seed


def test_latest_resume_pdf_is_versioned_and_preserved():
    for relative_path in (
        "static/resume/zhuxu-resume-202608.pdf",
        "static/resume/朱旭_简历.pdf",
    ):
        resume_pdf = PROJECT_ROOT / relative_path
        content = resume_pdf.read_bytes()
        assert content.startswith(b"%PDF-")
        assert hashlib.sha256(content).hexdigest() == LATEST_RESUME_SHA256

    for template_path in ("templates/index.html", "templates/resume.html"):
        assert "/static/resume/zhuxu-resume-202608.pdf" in _read(template_path)
