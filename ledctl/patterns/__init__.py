# ledctl/patterns/__init__.py
from importlib import import_module
from typing import Dict, Iterable, Callable, Any

# name -> relative module path
_PATTERNS: Dict[str, str] = {
    "stillred": ".stillred",
    "stillblue": ".stillblue",
    "breathered": ".breathered",
    "alarm": ".alarm",
}


def list_patterns() -> Iterable[str]:
    return sorted(_PATTERNS.keys())


def get_pattern(name: str) -> Callable[..., Any]:
    modname = _PATTERNS.get(name)
    if not modname:
        raise SystemExit(f"Unknown pattern: {name}")
    mod = import_module(modname, package=__name__)
    fn = getattr(mod, "run", None)
    if not callable(fn):
        raise SystemExit(f"Pattern '{name}' has no callable run()")
    return fn


def run_pattern(name: str, **kwargs):
    return get_pattern(name)(**kwargs)
