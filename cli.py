"""JobFit CLI - 求职搜索 + 学习规划助手.

Commands:
  python cli.py sources --region SG     列出某地区的求职网站
  python cli.py search --keyword "AI engineer" [--intern]
                                       按地区默认网站搜索岗位
  python cli.py study --goal "..." [--skills "..." --roles "..." --hours 15]
                                       生成学习路径和周计划
  python cli.py ask --question "..."    对本地资料库提问（需先构建索引）
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_sources(args) -> None:
    from scripts import sources_config

    if args.region:
        codes = [args.region.upper()]
    else:
        codes = sources_config.regions()
    for code in codes:
        reg = sources_config.get_region(code)
        print(f"[{code}] {reg.get('label', '')}")
        for s in sources_config.list_sources(code):
            flag = "ON " if s.get("enabled") else "OFF"
            print(f"  {flag} {s['key']:<18} {s['name']}  {s.get('note', '')}")


def cmd_search(args) -> None:
    from scripts.daily_monitor import run_monitor

    print(f"搜索地区默认源（新加坡参考实现），关键词: {args.keyword}")
    n = run_monitor(keywords=[args.keyword] if args.keyword else None, include_intern=args.intern)
    print(f"找到 {n} 条新岗位，结果写入 data/new_jobs_history.jsonl")


def cmd_study(args) -> None:
    from agent.study_planner import plan_study

    plan = plan_study(
        goal=args.goal,
        current_skills=args.skills,
        target_roles=args.roles,
        hours_per_week=args.hours,
        deadline=args.deadline,
        notes=args.notes,
    )
    print(json.dumps(plan, ensure_ascii=False, indent=2))


def cmd_ask(args) -> None:
    try:
        from rag.pipeline import RagPipeline
    except Exception as e:
        print(f"无法加载检索管线: {e}")
        return
    if not os.path.exists("storage/chunks.json"):
        print(
            "尚未构建本地索引。请先准备自己的资料目录，再运行索引构建后重试。"
        )
        return
    pipe = RagPipeline()
    res = pipe.ask(args.question, hybrid=True)
    print(res["answer"])
    for s in res.get("sources", []):
        print(f"- 来源: {s.get('id', '')}")


def main() -> None:
    ap = argparse.ArgumentParser(description="JobFit - 求职搜索 + 学习规划助手")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sources", help="列出某地区的求职网站")
    p.add_argument("--region", default="", help="国家/地区代码，如 SG / CN / US")
    p.set_defaults(func=cmd_sources)

    p = sub.add_parser("search", help="按地区默认网站搜索岗位")
    p.add_argument("--keyword", default="", help="搜索关键词，默认用内置关键词")
    p.add_argument("--intern", action="store_true", help="包含实习岗位")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("study", help="生成学习路径和周计划")
    p.add_argument("--goal", required=True, help="求职/学习目标")
    p.add_argument("--skills", default="", help="当前技能")
    p.add_argument("--roles", default="", help="目标岗位方向")
    p.add_argument("--hours", type=int, default=15, help="每周学习小时数")
    p.add_argument("--deadline", default="", help="截止时间")
    p.add_argument("--notes", default="", help="补充说明")
    p.set_defaults(func=cmd_study)

    p = sub.add_parser("ask", help="对本地资料库提问")
    p.add_argument("--question", required=True)
    p.set_defaults(func=cmd_ask)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
