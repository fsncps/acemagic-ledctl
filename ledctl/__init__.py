# ledctl/__init__.py  (lazy re-export)
__version__ = "0.1.0"
__all__ = ["LedCtl", "MODE", "__version__"]


def __getattr__(name):
    if name in ("LedCtl", "MODE"):
        from .core import LedCtl, MODE  # imported only when accessed

        return {"LedCtl": LedCtl, "MODE": MODE}[name]
    raise AttributeError(name)
