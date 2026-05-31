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
- [ ] Tests pasan: `pytest` → N passed, 0 failed
- [ ] Sin lógica de negocio en views/serializers (regla de 15 líneas)
- [ ] Sin imports de ORM en views (DIP)
- [ ] Conventional commits
- [ ] Sin migraciones huérfanas: `python manage.py makemigrations --check --dry-run`

## 🧪 Cómo probar

```bash
ruff check . && ruff format --check .
pytest -q
```

## 📝 Notas técnicas

<!-- Opcional — gotchas, decisiones de diseño no obvias, bugs encontrados -->
