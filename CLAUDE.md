# NewBody Content Auditor

## Objetivo

Herramienta para comparar contenido publicado en varias cuentas de Instagram (master: `newbodycol`; branches: `newbodyclubmedellin`, `newbodyclubantienvejecimientoc`, `newbodybaq`).

**Pregunta clave:** ¿Qué publicaciones existen en `newbodycol` pero NO existen en una o varias de las otras cuentas?

**Salida:** Excel con fecha original, link, caption, tipo de publicación y disponibilidad por cuenta.

## Alcance MVP

- NO utilizar: Supabase, PostgreSQL, Firebase, Redis, Celery, Docker, APIs de pago, SaaS de pago, autenticación de usuarios, infraestructura cloud.
- Persistencia inicial: archivos JSON locales.
- NO implementar todavía: scraping real de Instagram, InstagramProvider, Instaloader, matching, procesamiento de imágenes, exportación Excel, background tasks, UI definitiva.

## Stack

**Backend:**
- Python 3.12
- FastAPI
- Pydantic
- pytest
- httpx

**Frontend:**
- React 18+
- TypeScript
- Vite

**Procesamiento futuro:**
- Pillow
- RapidFuzz
- OpenPyXL

## Arquitectura

Capas claras y separadas:

```
backend/
├── app/
│   ├── main.py                 # Punto de entrada FastAPI
│   ├── domain/                 # Lógica de negocio pura
│   │   ├── __init__.py
│   │   ├── models.py           # Entidades de dominio
│   │   └── comparator.py       # Lógica de comparación
│   ├── providers/              # Abstracciones externas
│   │   ├── __init__.py
│   │   └── instagram.py        # InstagramProvider (abstracción)
│   ├── repositories/           # Persistencia
│   │   ├── __init__.py
│   │   ├── base.py             # Interfaz Repository
│   │   └── json_repo.py        # Implementación JsonRepository
│   ├── services/               # Orquestación
│   │   ├── __init__.py
│   │   └── audit_service.py    # Lógica de negocio
│   └── api/                    # Endpoints HTTP
│       ├── __init__.py
│       ├── routes.py           # Rutas FastAPI
│       └── schemas.py          # Pydantic models para API
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Fixtures pytest
│   └── test_api.py             # Tests de API
├── data/                       # Almacenamiento JSON local
├── pyproject.toml              # Dependencias y configuración
├── pytest.ini                  # Configuración pytest
└── .env.example                # Variables de entorno (sin secretos)

frontend/
├── src/
│   ├── main.tsx                # Punto de entrada
│   ├── App.tsx                 # Componente raíz
│   ├── components/
│   │   └── HealthCheck.tsx     # Componente mínimo para verificar backend
│   ├── services/
│   │   └── api.ts              # Cliente HTTP
│   └── style.css
├── public/
├── index.html
├── tsconfig.json
├── vite.config.ts
├── package.json
└── .gitignore
```

## Convenciones

- **Backend:** naming snake_case, imports agrupados (stdlib, third-party, local), no usar f-strings innecesarias.
- **Frontend:** PascalCase para componentes, camelCase para funciones/variables, strict TypeScript.
- **Tests:** prefix `test_`, usar pytest fixtures, >80% coverage en lógica de negocio.
- **Commits:** estilo convencional (feat:, fix:, chore:, test:, etc.).
- **No hardcodear:** secretos, credenciales, rutas absolutas, hosts reales de Instagram en código.

## Comandos de Desarrollo

**Backend:**

```bash
cd backend

# Instalar dependencias
pip install -e .

# Ejecutar servidor desarrollo
python -m uvicorn app.main:app --reload

# Tests
pytest

# Tests con coverage
pytest --cov=app --cov-report=html

# Validación de tipos
mypy app
```

**Frontend:**

```bash
cd frontend

# Instalar dependencias
npm install

# Ejecutar desarrollo
npm run dev

# Build producción
npm run build

# Validar TypeScript
npm run type-check

# Preview build
npm run preview
```

## Política de Tests

- Todo endpoint debe tener un test mínimo (happy path).
- Todo servicio de dominio debe tener tests.
- Repositories: tomar de fixtures JSON, no crear archivos reales durante tests.
- Frontend: tests de integración básica (backend disponible, datos se muestran).
- Cobertura mínima: 80% en lógica de negocio.

## Restricciones del MVP

1. **No infraestructura innecesaria:** Si funciona con JSON, no agregar PostgreSQL.
2. **Persistencia:** Solo JsonRepository implementado, preparado para reemplazo futuro.
3. **Providers:** InstagramProvider como abstracción, implementación mínima.
4. **No background tasks:** Hacer scraping síncrono o en request (si es rápido).
5. **No caching sofisticado:** Si es necesario, usar simples dicts en memoria.
6. **CORS:** Solo permite localhost:5173 (frontend dev), será configurable después.

## Filosofía de Código

- Tipado siempre (Python con type hints, TypeScript strict).
- Código simple > abstracciones prematuras.
- Arquitectura hexagonal: domain al centro, providers/repos afuera.
- Responsabilidad única: domain no conoce repos, services orquesta, API no tiene lógica.
- No dependencies circulares.

## No Agregar Todavía

- Scraping real de Instagram o Instaloader.
- Matching / deduplicación de contenido.
- Procesamiento de imágenes.
- Exportación a Excel.
- Autenticación de usuarios.
- Variables de entorno para credenciales (las haremos después).
- Logging estructurado complejo.
- Monitoreo / observabilidad.

## Próxima Fase (FASE 1)

Después de validar esta foundation:
- InstagramProvider con Instaloader (mock durante tests).
- Endpoints para escanear cuentas.
- Lógica de comparación y matching.
- Exportación a Excel.
- UI para ejecutar auditorías.
