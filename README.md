# IA Tests 2

Proyecto de pruebas en Python.

## Instalación

```bash
# Crear un entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -e .

# Instalar dependencias de desarrollo
pip install -e ".[dev]"
```

## Ejecución

```bash
python -m ia_tests_2.main
```

## Tests

```bash
pytest tests/ -v
```

## Estructura del proyecto

```
ia-tests-2/
├── src/
│   └── ia_tests_2/
│       ├── __init__.py
│       └── main.py
├── tests/
│   ├── __init__.py
│   └── test_main.py
├── docs/
├── pyproject.toml
├── README.md
├── LICENSE
└── .gitignore
```

## Licencia

Este proyecto está licenciado bajo la licencia MIT. Véase el archivo [LICENSE](LICENSE) para más detalles.
