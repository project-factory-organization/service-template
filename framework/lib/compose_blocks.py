"""Shared helpers for compose block rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import textwrap
from typing import Any

import yaml  # type: ignore[import-untyped]

from framework.lib.env import get_repo_root
from framework.lib.service_scaffold import ServiceSpec

ROOT = get_repo_root()
REGISTRY_PATH = ROOT / "services.yml"
SERVICES_ROOT = ROOT / "services"
START_MARKER = "# >>> services (auto-generated from services.yml)"
END_MARKER = "# <<< services (auto-generated from services.yml)"


@dataclass
class ComposeTarget:
    """Represents a compose file managed via templates."""

    key: str
    path: Path
    indent: str = "  "


COMPOSE_TARGETS = [
    ComposeTarget(key="base", path=ROOT / "infra/compose.base.yml"),
    ComposeTarget(key="dev", path=ROOT / "infra/compose.dev.yml"),
    ComposeTarget(key="tests_unit", path=ROOT / "infra/compose.tests.unit.yml"),
]


@dataclass(frozen=True)
class ServiceComposeTemplate:
    """String templates for generating compose entries per service."""

    base: str | None = None
    dev: str | None = None
    tests_unit: str | None = None


IMAGE_SLUG_OVERRIDES = {
    "tg_bot": "tg",
}


DEFAULT_TEMPLATES: dict[str, ServiceComposeTemplate] = {
    "python-fastapi": ServiceComposeTemplate(
        base=textwrap.dedent(
            """\
            __SLUG__:
              image: ${__IMAGE_ENV__:-service-template-__IMAGE_SLUG__:latest}
              user: "${HOST_UID:-1000}:${HOST_GID:-1000}"
              build:
                context: ..
                dockerfile: services/__SLUG__/Dockerfile
                args:
                  INSTALL_DEV_DEPS: ${__INSTALL_DEV_ENV__:-false}
              env_file:
                - ../.env
              environment:
                <<: *backend-env
              command: ["services/__SLUG__/scripts/start.sh"]
              depends_on:
                db:
                  condition: service_healthy
              ports:
                - "8000:8000"
            """
        ),
        dev=textwrap.dedent(
            """\
            __SLUG__:
              extends:
                file: compose.base.yml
                service: __SLUG__
              build:
                context: ..
                dockerfile: services/__SLUG__/Dockerfile
                args:
                  INSTALL_DEV_DEPS: ${__INSTALL_DEV_ENV__:-false}
              command: >-
                bash -lc "./services/__SLUG__/scripts/migrate.sh &&
                uvicorn services.__SLUG__.src.main:app --host 0.0.0.0 --port 8000 --reload"
              volumes:
                - ../:/workspace:delegated
              working_dir: /workspace
              env_file:
                - ../.env
              environment:
                PYTHONPATH: /workspace
            """
        ),
        tests_unit=textwrap.dedent(
            """\
            __SLUG_DASH__-tests-unit:
              image: ${__IMAGE_ENV__:-service-template-__IMAGE_SLUG__:latest}
              user: "${HOST_UID:-1000}:${HOST_GID:-1000}"
              build:
                context: ..
                dockerfile: services/__SLUG__/Dockerfile
                args:
                  INSTALL_DEV_DEPS: "true"
              command: >-
                pytest -q --cov=__COV_SOURCE__
                --cov-report=term-missing --cov-fail-under=70
                __UNIT_TEST_TARGET__
              working_dir: /app
              env_file:
                - ../.env
              environment:
                PYTHONPATH: /app
                ENVIRONMENT: test
                APP_ENV: test
                DATABASE_URL: sqlite+pysqlite:////tmp/backend_tests/test.db
                REDIS_URL: redis://localhost:6379
            """
        ),
    ),
    "python-faststream": ServiceComposeTemplate(
        base=textwrap.dedent(
            """\
            __SLUG__:
              image: ${__IMAGE_ENV__:-service-template-__IMAGE_SLUG__:latest}
              user: "${HOST_UID:-1000}:${HOST_GID:-1000}"
              build:
                context: ..
                dockerfile: services/__SLUG__/Dockerfile
              env_file:
                - ../.env
            """
        ),
        dev=textwrap.dedent(
            """\
            __SLUG__:
              extends:
                file: compose.base.yml
                service: __SLUG__
              volumes:
                - ../:/workspace:delegated
              working_dir: /workspace
              env_file:
                - ../.env
              environment:
                PYTHONPATH: /workspace
            """
        ),
        tests_unit=textwrap.dedent(
            """\
            __SLUG_DASH__-tests-unit:
              image: ${__IMAGE_ENV__:-service-template-__IMAGE_SLUG__:latest}
              user: "${HOST_UID:-1000}:${HOST_GID:-1000}"
              build:
                context: ..
                dockerfile: services/__SLUG__/Dockerfile
                args:
                  INSTALL_DEV_DEPS: "true"
              command: >-
                pytest -q --cov=__COV_SOURCE__
                --cov-report=term-missing --cov-fail-under=70
                __UNIT_TEST_TARGET__
              working_dir: /app
              env_file:
                - ../.env
              environment:
                PYTHONPATH: /app
            """
        ),
    ),
    "node": ServiceComposeTemplate(
        base=textwrap.dedent(
            """\
            __SLUG__:
              image: ${__IMAGE_ENV__:-service-template-__IMAGE_SLUG__:latest}
              user: "${HOST_UID:-1000}:${HOST_GID:-1000}"
              build:
                context: ..
                dockerfile: services/__SLUG__/Dockerfile
              env_file:
                - ../.env
              ports:
                - "4321:4321"
            """
        ),
        dev=textwrap.dedent(
            """\
            __SLUG__:
              extends:
                file: compose.base.yml
                service: __SLUG__
              command: npm run dev -- --host 0.0.0.0 --port 4321
              volumes:
                - ../services/__SLUG__:/app:delegated
              env_file:
                - ../.env
            """
        ),
    ),
}


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"services registry not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("services.yml must start with a mapping")
    return data


def compose_template_for_spec(spec: ServiceSpec) -> ServiceComposeTemplate | None:
    return DEFAULT_TEMPLATES.get(spec.service_type)


def _unit_test_target(spec: ServiceSpec) -> str:
    service_root = SERVICES_ROOT / spec.slug
    unit_tests_dir = service_root / "tests" / "unit"
    if unit_tests_dir.exists():
        return f"services/{spec.slug}/tests/unit"
    tests_dir = service_root / "tests"
    if tests_dir.exists():
        return f"services/{spec.slug}/tests"
    return f"services/{spec.slug}/tests/unit"


def _cov_source(spec: ServiceSpec) -> str:
    """Return coverage source path for a service."""
    return f"services/{spec.slug}/src"


def _render_depends_on(spec: ServiceSpec) -> str:
    """Render depends_on block from spec if present."""
    if not spec.depends_on:
        return ""
    lines = ["depends_on:"]
    for service, condition in spec.depends_on.items():
        lines.append(f"  {service}:")
        lines.append(f"    condition: {condition}")
    return "\n".join(f"  {line}" for line in lines) + "\n"


def _apply_placeholders(template: str, spec: ServiceSpec, key: str = "base") -> str:
    image_slug = IMAGE_SLUG_OVERRIDES.get(spec.slug, spec.slug.replace("_", "-"))
    replacements = {
        "__SLUG__": spec.slug,
        "__SLUG_DASH__": spec.slug.replace("_", "-"),
        "__IMAGE_ENV__": f"{spec.slug.upper()}_IMAGE",
        "__INSTALL_DEV_ENV__": f"{spec.slug.upper()}_INSTALL_DEV_DEPS",
        "__IMAGE_SLUG__": image_slug,
        "__UNIT_TEST_TARGET__": _unit_test_target(spec),
        "__COV_SOURCE__": _cov_source(spec),
    }
    rendered = template
    for key_placeholder, value in replacements.items():
        rendered = rendered.replace(key_placeholder, value)

    # Insert depends_on from spec (for base template only)
    if key == "base" and spec.depends_on:
        lines = rendered.splitlines()
        insert_idx = len(lines)
        for i, line in enumerate(lines):
            if line.strip().startswith("ports:"):
                insert_idx = i
                break
        extra_lines: list[str] = []
        extra_lines.append("  depends_on:")
        for service, condition in spec.depends_on.items():
            extra_lines.append(f"    {service}:")
            extra_lines.append(f"      condition: {condition}")
        lines = lines[:insert_idx] + extra_lines + lines[insert_idx:]
        rendered = "\n".join(lines)

    # Insert profiles from spec (for dev template only)
    if key == "dev" and spec.profiles:
        lines = rendered.splitlines()
        # Insert after the service name line (first line)
        profiles_str = ", ".join(f'"{p}"' for p in spec.profiles)
        lines.insert(1, f"  profiles: [{profiles_str}]")
        rendered = "\n".join(lines)

    return rendered.rstrip("\n") + "\n"


def render_service_templates(specs: list[ServiceSpec], key: str) -> list[str]:
    templates: list[str] = []
    for spec in specs:
        template = compose_template_for_spec(spec)
        if not template:
            continue
        if key == "dev" and not spec.create_dev_template:
            continue
        snippet = getattr(template, key, None)
        if not snippet:
            continue
        templates.append(_apply_placeholders(snippet, spec, key))
    return templates


def indent_template(text: str, indent: str) -> str:
    stripped = text.rstrip()
    if not stripped:
        return ""
    return textwrap.indent(stripped, indent, lambda _line: True)


def build_service_block(templates: list[str], indent: str) -> list[str]:
    if not templates:
        return [f"{indent}# (no managed services)"]

    block_lines: list[str] = []
    for template in templates:
        indented = indent_template(template, indent)
        if indented:
            block_lines.extend(indented.splitlines())
            block_lines.append("")
    if block_lines and block_lines[-1] == "":
        block_lines.pop()
    return block_lines


def replace_block(lines: list[str], new_block: list[str]) -> list[str]:
    start_idx = next((i for i, line in enumerate(lines) if line.strip() == START_MARKER), None)
    end_idx = next((i for i, line in enumerate(lines) if line.strip() == END_MARKER), None)
    if start_idx is None or end_idx is None or start_idx >= end_idx:
        raise RuntimeError("Could not locate compose service markers in file")
    return lines[: start_idx + 1] + new_block + lines[end_idx:]
