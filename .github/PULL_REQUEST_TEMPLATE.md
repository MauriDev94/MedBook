## 📌 Linked Issue

Closes #<!-- número del issue -->

## 🧠 Resumen

_Qué hace este PR, en 2-3 líneas._

## 📂 Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `path/to/file` | _Qué cambió y por qué_ |

## ✅ Checklist

- [ ] Tests pasan: `pytest`
- [ ] Cobertura ≥ 85% en apps modificadas
- [ ] Sin lógica de negocio en views/serializers (regla de 15 líneas)
- [ ] Conventional commits
- [ ] Sin migraciones huérfanas
- [ ] Sin imports de ORM en views (DIP)

## 🧪 Cómo probar

```bash
# Comandos para verificar
pytest tests/unit/
python manage.py migrate --check
```
