"""Events generator for FastStream pub/sub."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from framework.generators.base import BaseGenerator


class EventsGenerator(BaseGenerator):
    """Generate event publishers and subscribers."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize with output path."""
        super().__init__(*args, **kwargs)
        self.output_file = self.repo_root / "shared" / "shared" / "generated" / "events.py"

    def generate(self) -> list[Path]:
        """Generate events module.

        Always generates at least a stub with get_broker() so the import
        never fails and coding agents have a clear place to add events.
        """
        publishers = []
        subscribers = []
        imports: set[str] = set()

        for event in self.specs.events.events:
            event_ctx = {
                "name": event.name,
                "message_model": event.message,
                "subject": event.name.replace("_", "."),  # user_created -> user.created
            }
            imports.add(event.message)

            if event.publish:
                publishers.append(event_ctx)
            if event.subscribe:
                subscribers.append(event_ctx)

        context = {
            "publishers": publishers,
            "subscribers": subscribers,
            "imports": imports,
        }

        env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,  # noqa: S701
        )
        template = env.get_template("events.py.j2")

        content = template.render(**context)
        self.write_file(self.output_file, content)
        self.format_file(self.output_file)

        return [self.output_file]
