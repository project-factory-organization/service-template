"""Controller stub generator.

Generates controller stubs only if they don't exist.
Uses OperationContextBuilder for unified context building.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from framework.generators.base import BaseGenerator
from framework.generators.context import OperationContextBuilder


class ControllersGenerator(BaseGenerator):
    """Generate controller stubs for services."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize generator."""
        super().__init__(*args, **kwargs)
        self.context_builder = OperationContextBuilder()

    def generate(self) -> list[Path]:
        """Generate controller stubs (only if not existing)."""
        generated = []

        for domain_key, domain in sorted(self.specs.domains.items()):
            service_name, module_name = domain_key.split("/")
            output_file = (
                self.repo_root
                / "services"
                / service_name
                / "src"
                / "controllers"
                / f"{module_name}.py"
            )

            # Only generate if file doesn't exist
            if output_file.exists():
                continue

            self._generate_controller(domain, module_name, output_file)
            generated.append(output_file)

        return generated

    def _generate_controller(self, domain, module_name: str, output_file: Path) -> None:
        """Generate a single controller stub."""
        handlers = []
        imports: set[str] = set()
        param_type_imports: set[str] = set()

        for operation in domain.operations:
            ctx = self.context_builder.build_for_protocol(operation)

            handler_ctx = {
                "name": ctx.name,
                "params": [{"name": p.name, "type": p.type} for p in ctx.params],
                "request_model": ctx.input_model,
                "response_model": ctx.output_model,
                "return_type": ctx.computed_return_type,
            }

            imports.update(ctx.imports)
            param_type_imports.update(ctx.param_type_imports)
            handlers.append(handler_ctx)

        context = {
            "module_name": module_name,
            "protocol_name": f"{module_name.capitalize()}ControllerProtocol",
            "handlers": handlers,
            "imports": imports,
            "param_type_imports": sorted(param_type_imports),
            "async_handlers": True,  # Always async in new format
        }

        env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,  # noqa: S701
        )
        template = env.get_template("controller.py.j2")

        content = template.render(**context)
        # Controllers are editable, don't add generated header
        self.write_file(output_file, content, add_header=False)
        self.format_file(output_file)
