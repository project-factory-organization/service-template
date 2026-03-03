"""Protocol generator for controllers.

Generates typing.Protocol classes from domain specifications.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from framework.generators.base import BaseGenerator
from framework.generators.context import OperationContextBuilder


class ProtocolsGenerator(BaseGenerator):
    """Generate controller protocols from domain specs."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize generator."""
        super().__init__(*args, **kwargs)
        self.context_builder = OperationContextBuilder()

    def generate(self) -> list[Path]:
        """Generate protocols for all services."""
        generated_files = []

        # Group domains by service
        services_domains: dict[str, list] = {}
        services_imports: dict[str, set[str]] = {}
        services_param_type_imports: dict[str, set[str]] = {}

        for domain_key, domain in sorted(self.specs.domains.items()):
            service_name, domain_name = domain_key.split("/")

            if service_name not in services_domains:
                services_domains[service_name] = []
                services_imports[service_name] = set()
                services_param_type_imports[service_name] = set()

            protocol_name = f"{domain_name.capitalize()}ControllerProtocol"

            handlers = []
            for operation in domain.operations:
                ctx = self.context_builder.build_for_protocol(operation)

                handler_ctx = {
                    "name": ctx.name,
                    "params": [{"name": p.name, "type": p.type} for p in ctx.params],
                    "request_model": ctx.input_model,
                    "response_model": ctx.output_model,
                    "return_type": ctx.return_type,
                    # Transport type flags for unified handlers
                    "is_rest_only": ctx.is_rest_only,
                    "is_events_only": ctx.is_events_only,
                    "is_dual_transport": ctx.is_dual_transport,
                }

                # Collect imports
                services_imports[service_name].update(ctx.imports)
                services_param_type_imports[service_name].update(ctx.param_type_imports)

                handlers.append(handler_ctx)

            services_domains[service_name].append(
                {
                    "name": domain_name,
                    "protocol_name": protocol_name,
                    "handlers": handlers,
                }
            )

        # Generate protocols.py for each service
        env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,  # noqa: S701
        )
        template = env.get_template("protocols.py.j2")

        for service_name, domains_context in services_domains.items():
            output_file = (
                self.repo_root / "services" / service_name / "src" / "generated" / "protocols.py"
            )

            content = template.render(
                routers=domains_context,  # Template expects 'routers' key
                imports=services_imports[service_name],
                param_type_imports=sorted(services_param_type_imports[service_name]),
                async_handlers=True,
            )
            self.write_file(output_file, content)
            self.format_file(output_file)
            generated_files.append(output_file)

        return generated_files
