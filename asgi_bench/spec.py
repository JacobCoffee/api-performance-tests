import dataclasses
from collections import defaultdict
from pathlib import Path
from typing import cast

from .types import (
    BenchmarkMode,
    EndpointCategory,
    EndpointMode,
    Framework,
    FrameworkSpec,
    TestSpec,
)


@dataclasses.dataclass
class Endpoint:
    path: str
    name: str
    exclude: list[Framework] = dataclasses.field(default_factory=list)
    headers: list[tuple[str, str]] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class TestCategory:
    name: EndpointCategory
    endpoints: list[Endpoint]
    frameworks: tuple[Framework, ...] = ("starlite", "starlette", "fastapi", "sanic", "blacksheep")


TEST_CATEGORIES: list[TestCategory] = [
    TestCategory(
        name="plaintext",
        endpoints=[
            Endpoint(path="plaintext-100B", name="plaintext 100 bytes"),
            Endpoint(path="plaintext-1K", name="plaintext 1 kB"),
            Endpoint(path="plaintext-10K", name="plaintext 10 kB"),
            Endpoint(path="plaintext-100K", name="plaintext 100 kB"),
            Endpoint(path="plaintext-500K", name="plaintext 500 kB"),
            Endpoint(path="plaintext-1M", name="plaintext 1 MB"),
            Endpoint(path="plaintext-5M", name="plaintext 5 MB"),
        ],
    ),
    TestCategory(
        name="json",
        endpoints=[
            Endpoint(path="json-1K", name="json 1 kB"),
            Endpoint(path="json-10K", name="json 10 kB"),
            Endpoint(path="json-100K", name="json 100 kB"),
            Endpoint(path="json-500K", name="json 500 kB"),
            Endpoint(path="json-1M", name="json 1 MB"),
            Endpoint(path="json-5M", name="json 5 MB"),
        ],
    ),
    TestCategory(
        name="files",
        endpoints=[
            Endpoint(path="file-response-100B", name="file response 100 bytes"),
            Endpoint(path="file-response-1K", name="file response 1 kB"),
            Endpoint(path="file-response-10K", name="file response 10 kB"),
            Endpoint(path="file-response-100K", name="file response 100 kB"),
            Endpoint(path="file-response-500K", name="file response 500 kB"),
            Endpoint(path="file-response-1M", name="file response 1 MB"),
            Endpoint(path="file-response-5M", name="file response 5 MB"),
        ],
    ),
    TestCategory(
        name="params",
        endpoints=[
            Endpoint(path="no-params", name="no params"),
            Endpoint(path="path-params/42", name="path params"),
            Endpoint(path="query-param?first=42", name="query params"),
            Endpoint(path="mixed-params/42?first=21", name="mixed params"),
        ],
    ),
    TestCategory(
        name="dynamic-response",
        endpoints=[
            Endpoint(path="response-headers", name="response headers"),
            Endpoint(path="response-cookies", name="response cookies"),
        ],
    ),
    TestCategory(
        name="dependency-injection",
        frameworks=("starlite", "fastapi", "sanic", "blacksheep"),
        endpoints=[
            Endpoint(path="dependencies-sync", name="dependencies sync"),
            Endpoint(path="dependencies-async", name="dependencies async", exclude=["sanic", "blacksheep"]),
            Endpoint(path="dependencies-mixed", name="dependencies mixed", exclude=["sanic", "blacksheep"]),
        ],
    ),
    TestCategory(
        name="serialization",
        frameworks=("starlite", "fastapi"),
        endpoints=[
            Endpoint(path="serialize-pydantic-50", name="serialize pydantic, 50 objects"),
            Endpoint(path="serialize-pydantic-100", name="serialize pydantic, 100 objects"),
            Endpoint(path="serialize-pydantic-500", name="serialize pydantic, 500 objects"),
            Endpoint(path="serialize-dataclasses-50", name="serialize dataclasses, 50 objects"),
            Endpoint(path="serialize-dataclasses-100", name="serialize dataclasses, 100 objects"),
            Endpoint(path="serialize-dataclasses-500", name="serialize dataclasses, 500 objects"),
        ],
    ),
]

CATEGORIES_BY_NAME: dict[EndpointCategory, TestCategory] = {c.name: c for c in TEST_CATEGORIES}
ENDPOINT_CATEGORIES: tuple[EndpointCategory, ...] = tuple(CATEGORIES_BY_NAME.keys())


def make_spec(
    *,
    frameworks: tuple[str, ...],
    endpoint_modes: tuple[EndpointMode, ...] | EndpointMode,
    categories: tuple[EndpointCategory, ...] | EndpointCategory,
    warmup_time: int | None = None,
    time_limit: int | None = None,
    request_limit: int | None = None,
    rate_limit: int | None = None,
    benchmark_modes: tuple[BenchmarkMode, ...] | BenchmarkMode,
) -> list[FrameworkSpec]:
    if isinstance(endpoint_modes, str):
        endpoint_modes = (endpoint_modes,)
    if isinstance(categories, str):
        categories = (categories,)
    if isinstance(benchmark_modes, str):
        benchmark_modes = (benchmark_modes,)

    selected_categories = [c for c in TEST_CATEGORIES if c.name in categories]

    framework_specs = []
    requested_frameworks = defaultdict(list)
    for framework in frameworks:
        name, *parts = framework.split("@", 1)
        version = parts[0] if parts else None
        requested_frameworks[name].append(version)

    for path in (Path.cwd() / "frameworks").iterdir():
        if path.is_file() and path.name.endswith("_app.py"):
            framework_name = cast(Framework, path.name.removesuffix("_app.py"))
            if framework_name not in requested_frameworks:
                continue
            for requested_version in requested_frameworks.get(framework_name, []):
                test_specs = [
                    TestSpec(
                        path=f"/{endpoint_mode}-{endpoint.path}",
                        endpoint_mode=endpoint_mode,
                        benchmark_mode=benchmark_mode,
                        category=category.name,
                        name=endpoint.name,
                        headers=endpoint.headers,
                        warmup_time=warmup_time,
                        time_limit=time_limit or 15 if benchmark_mode == "rps" else None,
                        request_limit=request_limit or 1000 if benchmark_mode == "latency" else None,
                        rate_limit=rate_limit or 20 if benchmark_mode == "latency" else None,
                        slug_name=f"{endpoint_mode}-{endpoint.path.split('?')[0]}",
                        is_supported=framework_name in category.frameworks and framework_name not in endpoint.exclude,
                    )
                    for benchmark_mode in benchmark_modes
                    for endpoint_mode in endpoint_modes
                    for category in selected_categories
                    for endpoint in category.endpoints
                ]
                framework_specs.append(
                    FrameworkSpec(
                        name=framework_name,
                        version=requested_version,
                        path=path,
                        tests=test_specs,
                    )
                )

    return framework_specs


FRAMEWORK_REPOS: dict[Framework, str] = {
    "starlite": "https://github.com/starlite-api/starlite.git",
    "starlette": "https://github.com/encode/starlette.git",
    "fastapi": "https://github.com/tiangolo/fastapi.git",
    "sanic": "https://github.com/sanic-org/sanic.git",
    "blacksheep": "https://github.com/Neoteroi/BlackSheep.git",
}
FRAMEWORKS: tuple[Framework, ...] = tuple(FRAMEWORK_REPOS.keys())