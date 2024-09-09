import importlib
import importlib.util
import sys

from smart_reload import hook


def reload(name: str, package: str | None = None):
    resolved = importlib.util.resolve_name(name, package)
    if resolved not in sys.modules:
        msg = f"Module {name!r}{f'in package {package!r}' if package else ''} was never imported."
        raise RuntimeError(msg)

    loader = sys.modules[resolved].__loader__
    if not isinstance(loader, hook.ShittyLoader):
        msg = (
            f"Module {resolved!r} cannot be reloaded as it wasn't imported with"
            " the import hook active. Make sure to import smart_reload first."
        )
        raise RuntimeError(msg)  # noqa: TRY004

    dependents = loader.get_dependents()
    for dependent_group in reversed(dependents):
        for dependent in dependent_group:
            del sys.modules[dependent.__name__]

    for dependent_group in dependents:
        for dependent in dependent_group:
            importlib.import_module(dependent.__name__)

