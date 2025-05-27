import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from typing import Dict, Any

def render_jinja_config(template_path: str, substitutions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Renders a Jinja2 YAML config with multiple substitutions and returns it as a dictionary.

    Args:
        template_path: Path to the Jinja2 YAML file (e.g., config_template.yaml.j2)
        substitutions: Dictionary of variable substitutions

    Returns:
        Dict with rendered YAML content
    """
    template_dir = str(Path(template_path).parent)
    template_file = Path(template_path).name

    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(['html', 'xml'])
    )

    template = env.get_template(template_file)
    rendered_yaml = template.render(**substitutions)

    return yaml.safe_load(rendered_yaml)
