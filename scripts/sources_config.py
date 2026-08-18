"""Job-source registry by country/region.

JobFit lets the user pick a country/region, then searches the local job sites
that are enabled there. 新加坡 (SG) ships as the reference implementation;
other regions are registered here with their adapter marked as TODO, so anyone
can add their local sites by implementing one adapter function and enabling it.

Adapter interface (for a site named ``foo``):
    def fetch_foo(keyword: str) -> list[dict]:
        return [{"title": str, "url": str, "company": str,
                 "salary": {"minimum": float|None, "maximum": float|None},
                 "deadline": str}]
Then register it under the region and set ``enabled: True``.
"""

from __future__ import annotations

REGIONS = {
    "SG": {
        "label": "新加坡 Singapore",
        "sources": [
            {
                "key": "jobstreet",
                "name": "JobStreet Singapore",
                "enabled": True,
                "type": "jobstreet",
                "note": "参考实现，默认启用",
            },
            {
                "key": "mycareersfuture",
                "name": "MyCareersFuture",
                "enabled": True,
                "type": "mycareersfuture",
                "note": "参考实现，默认启用",
            },
            {
                "key": "internsg",
                "name": "InternSG",
                "enabled": True,
                "type": "internsg",
                "note": "参考实现，默认启用",
            },
            {
                "key": "gradconnection",
                "name": "GradConnection Singapore",
                "enabled": True,
                "type": "gradconnection",
                "note": "参考实现，默认启用",
            },
        ],
    },
    "CN": {
        "label": "中国 China",
        "sources": [
            {
                "key": "liepin",
                "name": "猎聘",
                "enabled": False,
                "type": "liepin",
                "note": "待实现 adapter",
            },
            {
                "key": "yingjiesheng",
                "name": "应届生求职网",
                "enabled": False,
                "type": "yingjiesheng",
                "note": "待实现 adapter",
            },
        ],
    },
    "US": {
        "label": "美国 United States",
        "sources": [
            {
                "key": "indeed",
                "name": "Indeed",
                "enabled": False,
                "type": "indeed",
                "note": "待实现 adapter",
            },
            {
                "key": "linkedin",
                "name": "LinkedIn Jobs",
                "enabled": False,
                "type": "linkedin",
                "note": "待实现 adapter",
            },
        ],
    },
}


def regions() -> list[str]:
    return sorted(REGIONS)


def get_region(code: str) -> dict:
    return REGIONS.get(str(code).upper(), {})


def enabled_sources(code: str) -> list[dict]:
    return [s for s in get_region(code).get("sources", []) if s.get("enabled")]


def list_sources(code: str) -> list[dict]:
    return get_region(code).get("sources", [])
