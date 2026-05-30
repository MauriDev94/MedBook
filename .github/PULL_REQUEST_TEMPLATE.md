## 📌 Linked Issue

Closes #<!-- número del issue -->

## 🧠 Resumen

_Qué hace este PR, en 2-3 líneas._

## 📂 Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `path/to/file` | _Qué cambió y por qué_ |

## ✅ Checklist

- [ ] Lint pasa: `ruff check . && ruff format --check .`
- [ ] Tests pasan: `pytest`
- [ ] Cobertura: models+services ≥ 90% · views+serializers ≥ 80% · permissions = 100%
- [ ] Sin lógica de negocio en views/serializers (regla de 15 líneas)
- [ ] Conventional commits
- [ ] Sin migraciones huérfanas: `python manage.py makemigrations --check --dry-run`
- [ ] Sin imports de ORM en views (DIP)

## 🧪 Cómo probar

```bash
ruff check . && ruff format --check .
pytest -q
python manage.py makemigrations --check --dry-run
```
