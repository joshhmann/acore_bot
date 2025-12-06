# Template System

This directory contains Jinja2 templates for the web dashboard and other HTML generation.

## Structure

```
templates/
├── dashboard/
│   ├── index.html          # Main dashboard page
│   ├── components/         # Reusable components
│   │   ├── header.html
│   │   ├── footer.html
│   │   ├── status_card.html
│   │   └── activity_log.html
│   └── base.html           # Base template
└── README.md               # This file
```

## Usage

### In Services

```python
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path

# Create Jinja2 environment
template_dir = Path(__file__).parent.parent / "templates"
env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml'])
)

# Render template
template = env.get_template('dashboard/index.html')
html = template.render(
    bot_status=self.status,
    metrics=self.metrics,
    logs=self.recent_logs
)
```

### Template Syntax

Templates use Jinja2 syntax:

**Variables**:
```html
<h1>{{ bot_name }}</h1>
<p>Status: {{ status }}</p>
```

**Conditionals**:
```html
{% if bot_online %}
    <span class="online">Online</span>
{% else %}
    <span class="offline">Offline</span>
{% endif %}
```

**Loops**:
```html
<ul>
{% for log in logs %}
    <li class="log-{{ log.level }}">{{ log.message }}</li>
{% endfor %}
</ul>
```

**Template Inheritance**:
```html
{% extends "dashboard/base.html" %}

{% block content %}
    <h2>My Custom Content</h2>
{% endblock %}
```

## Migration Status

### ✅ Completed
- Template infrastructure created
- Jinja2 environment setup
- Base template structure

### ⏳ In Progress
- Extracting `services/web_dashboard.py` HTML (2009 lines)
  - Main dashboard page
  - Status cards
  - Activity logs
  - Configuration editor

### 📋 TODO
1. Extract HTML from `handle_index()` → `dashboard/index.html`
2. Create component templates for reusable elements
3. Update `WebDashboard` class to use template renderer
4. Add template caching for performance
5. Create additional templates for other endpoints

## Benefits

- **Separation of Concerns**: HTML separated from Python logic
- **Reusability**: Components can be shared across pages
- **Maintainability**: Easier to update styles and structure
- **Security**: Auto-escaping prevents XSS attacks
- **Flexibility**: Easy to add themes or customize appearance

## Template Best Practices

1. **Use Base Templates**: Avoid duplicating headers/footers
2. **Component Templates**: Break complex UIs into components
3. **Context Data**: Pass clean, structured data to templates
4. **Auto-escaping**: Let Jinja2 handle escaping (enabled by default)
5. **Comments**: Use `{# comment #}` for template comments
6. **Filters**: Use built-in filters like `|safe`, `|length`, `|default`

## Example Migration

Before (embedded HTML):
```python
async def handle_index(self, request):
    html = f"""
    <html>
        <body>
            <h1>Bot Status: {self.status}</h1>
            <p>Uptime: {self.uptime}</p>
        </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')
```

After (using templates):
```python
async def handle_index(self, request):
    html = self.env.get_template('dashboard/index.html').render(
        status=self.status,
        uptime=self.uptime
    )
    return web.Response(text=html, content_type='text/html')
```

Template file (`dashboard/index.html`):
```html
<!DOCTYPE html>
<html>
<body>
    <h1>Bot Status: {{ status }}</h1>
    <p>Uptime: {{ uptime }}</p>
</body>
</html>
```
