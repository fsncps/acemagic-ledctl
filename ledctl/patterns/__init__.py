import importlib
import pkgutil

import ledctl.patterns


def list_patterns():
    return sorted(
        name
        for _finder, name, is_pkg in pkgutil.iter_modules(ledctl.patterns.__path__)
        if not is_pkg
    )


def run_pattern(name, **kwargs):
    available = list_patterns()
    if name not in available:
        raise SystemExit(f"Unknown pattern '{name}'. Available: {', '.join(available)}")
    mod = importlib.import_module(f"ledctl.patterns.{name}")
    return mod.run(**kwargs)
