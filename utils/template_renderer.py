"""Template rendering utility using Jinja2."""

import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """Utility for rendering Jinja2 templates.

    Provides a simple interface for loading and rendering templates
    with automatic escaping and error handling.
    """

    def __init__(self, template_dir: Optional[Path] = None):
        """Initialize the template renderer.

        Args:
            template_dir: Path to templates directory (defaults to project templates/)
        """
        if template_dir is None:
            # Default to project root / templates
            template_dir = Path(__file__).parent.parent / "templates"

        self.template_dir = template_dir

        # Create Jinja2 environment with auto-escaping enabled
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters
        self._register_filters()

        logger.info(f"Template renderer initialized (template_dir: {template_dir})")

    def _register_filters(self):
        """Register custom Jinja2 filters."""
        def format_uptime(seconds):
            """Format seconds as human-readable uptime."""
            if seconds < 60:
                return f"{seconds:.0f}s"
            elif seconds < 3600:
                return f"{seconds/60:.0f}m"
            elif seconds < 86400:
                return f"{seconds/3600:.1f}h"
            else:
                return f"{seconds/86400:.1f}d"

        def format_bytes(bytes_val):
            """Format bytes as human-readable size."""
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_val < 1024:
                    return f"{bytes_val:.1f} {unit}"
                bytes_val /= 1024
            return f"{bytes_val:.1f} TB"

        # Register filters
        self.env.filters['format_uptime'] = format_uptime
        self.env.filters['format_bytes'] = format_bytes

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a template with the given context.

        Args:
            template_name: Template file name (e.g., "dashboard/index.html")
            context: Dictionary of variables to pass to template

        Returns:
            Rendered HTML string

        Raises:
            TemplateNotFound: If template file doesn't exist
            TemplateSyntaxError: If template has syntax errors

        Example:
            ```python
            renderer = TemplateRenderer()
            html = renderer.render('dashboard/index.html', {
                'bot_name': 'Acore Bot',
                'status': 'online',
                'uptime': 3600
            })
            ```
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render template '{template_name}': {e}")
            raise

    def render_string(self, template_string: str, context: Dict[str, Any]) -> str:
        """Render a template from a string.

        Args:
            template_string: Template content as string
            context: Dictionary of variables to pass to template

        Returns:
            Rendered HTML string

        Example:
            ```python
            renderer = TemplateRenderer()
            html = renderer.render_string(
                '<h1>Hello {{ name }}!</h1>',
                {'name': 'World'}
            )
            ```
        """
        try:
            template = self.env.from_string(template_string)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render template string: {e}")
            raise

    def add_global(self, name: str, value: Any):
        """Add a global variable available to all templates.

        Args:
            name: Variable name
            value: Variable value

        Example:
            ```python
            renderer.add_global('app_name', 'Acore Bot')
            # Now {{ app_name }} is available in all templates
            ```
        """
        self.env.globals[name] = value

    def add_filter(self, name: str, filter_func):
        """Add a custom filter.

        Args:
            name: Filter name
            filter_func: Filter function

        Example:
            ```python
            def uppercase(text):
                return text.upper()

            renderer.add_filter('uppercase', uppercase)
            # Usage in template: {{ "hello" | uppercase }}
            ```
        """
        self.env.filters[name] = filter_func


# ============================================================================
# Global Template Renderer Instance
# ============================================================================

# Global renderer instance (can be imported and used directly)
renderer = TemplateRenderer()


# ============================================================================
# Helper Functions
# ============================================================================

def render_template(template_name: str, context: Dict[str, Any]) -> str:
    """Convenience function to render a template using the global renderer.

    Args:
        template_name: Template file name
        context: Template context

    Returns:
        Rendered HTML

    Example:
        ```python
        from utils.template_renderer import render_template

        html = render_template('dashboard/index.html', {
            'status': 'online',
            'uptime': 3600
        })
        ```
    """
    return renderer.render(template_name, context)
