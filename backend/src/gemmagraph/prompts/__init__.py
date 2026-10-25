from importlib.resources import files


def render(name: str, **values):
    template = files("gemmagraph.prompts").joinpath(f"{name}.md").read_text()
    return template.format_map({k: str(v) for k, v in values.items()})
