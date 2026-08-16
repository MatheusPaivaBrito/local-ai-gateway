"""Import every application module to catch broken vertical-slice imports early."""

import importlib
import pkgutil

import app


def main() -> None:
    failures: list[tuple[str, Exception]] = []
    modules = sorted(
        module.name
        for module in pkgutil.walk_packages(app.__path__, prefix="app.")
        if not module.name.endswith(".__pycache__")
    )

    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - diagnostic script must report all failures.
            failures.append((name, exc))

    if failures:
        print("Import check failed:\n")
        for name, exc in failures:
            print(f"- {name}: {type(exc).__name__}: {exc}")
        raise SystemExit(1)

    print(f"Import check OK: {len(modules)} application modules imported.")


if __name__ == "__main__":
    main()
