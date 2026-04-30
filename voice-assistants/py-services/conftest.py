"""
Корневой conftest.py — регистрирует сервисы с дефисами как Python-модули.
Нужен потому что директории вида 'translation-checker' нельзя импортировать напрямую.
"""
import sys
import importlib
from pathlib import Path

ROOT = Path(__file__).parent


def _register_service(dir_name: str):
    """Регистрирует services/<dir-name> как services.<dir_name_with_underscores>."""
    module_name = dir_name.replace("-", "_")
    package_path = ROOT / "services" / dir_name
    if not package_path.exists():
        return

    full_module = f"services.{module_name}"
    if full_module not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            full_module,
            package_path / "__init__.py",
            submodule_search_locations=[str(package_path)],
        )
        if spec:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[full_module] = mod
            spec.loader.exec_module(mod)


# Регистрируем все сервисы с дефисами
for service_dir in (ROOT / "services").iterdir():
    if service_dir.is_dir() and "-" in service_dir.name:
        _register_service(service_dir.name)
