"""Factory to load and instantiate dynamically named / configured class instances."""
import importlib


def load_class(path: str):
    module_name, _, class_name = path.rpartition(".")
    if not module_name:
        raise RuntimeError(f"class path not found: {path}")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def load_strategies(app):
    strategies = {}

    for cfg in app.config["SECONDARY_SOURCE_STRATEGIES"]:
        name = cfg["name"]
        cls = load_class(cfg["class"])
        kwargs = cfg.copy()
        kwargs.pop("class")
        kwargs.pop("name")

        strategies[name] = cls(name, **kwargs)

    return strategies
