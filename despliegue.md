# Despliegue local con Docker

Este documento explica cómo ejecutar **Summoner's Fantasy** en un entorno local usando Docker y Docker Compose. No se requiere instalar Python ni Node.js — todo corre dentro de contenedores.

---

## Requisitos previos

- [Git](https://git-scm.com/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (incluye Docker Compose)
- Una cuenta en [Supabase](https://supabase.com) con un proyecto creado

---

## 1. Clonar el repositorio

```bash
git clone https://github.com/<tu-usuario>/Summoners_Fantasy.git
cd Summoners_Fantasy
```

---

## 2. Configurar variables de entorno

El proyecto necesita dos archivos `.env`: uno para el backend y otro para el frontend. Estos archivos contienen las credenciales de Supabase y otras configuraciones. **Nunca se suben al repositorio.**

### Backend

```bash
cp backend/.env.example backend/.env
```

Abrí `backend/.env` y completá los valores:

```env
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=tu-service-role-key

ENVIRONMENT=development
FRONTEND_URL=http://localhost:3002
BACKEND_URL=http://localhost:8000
```

> La `SUPABASE_SERVICE_ROLE_KEY` se obtiene en el panel de Supabase → Project Settings → API → `service_role`.

### Frontend

```bash
cp frontend/.env.example frontend/.env.local
```

Abrí `frontend/.env.local` y completá los valores:

```env
NEXT_PUBLIC_SUPABASE_URL=https://tu-proyecto.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=tu-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

> La `NEXT_PUBLIC_SUPABASE_ANON_KEY` se obtiene en el panel de Supabase → Project Settings → API → `anon public`.

---

## 3. Levantar el proyecto

Con un solo comando, Docker Compose construye las imágenes e inicia los contenedores:

```bash
docker compose up --build
```

Este comando realiza los siguientes pasos automáticamente:

1. **Construye la imagen del backend** — imagen `python:3.11-slim`, instala las dependencias de `requirements.txt` y levanta el servidor FastAPI con Uvicorn en el puerto `8000`.
2. **Construye la imagen del frontend** — imagen `node:22-alpine`, instala las dependencias de `package.json` y arranca el servidor de desarrollo de Next.js en el puerto `3002`.
3. **Inicia ambos contenedores** en red interna de Docker, con reinicio automático si alguno falla.

La primera vez tarda unos minutos mientras descarga las imágenes base e instala las dependencias. Las siguientes ejecuciones son mucho más rápidas gracias al caché de capas de Docker.

---

## 4. Acceder a la aplicación

Una vez que ambos contenedores estén corriendo, abrí el navegador:

| Servicio           | URL                          |
|--------------------|------------------------------|
| Frontend           | http://localhost:3002        |
| Backend API        | http://localhost:8000        |
| Documentación API  | http://localhost:8000/docs   |

---

## 5. Comandos útiles

```bash
# Ver los logs en tiempo real de ambos servicios
docker compose logs -f

# Ver solo los logs del backend
docker compose logs -f backend

# Ver solo los logs del frontend
docker compose logs -f frontend

# Detener los contenedores (sin borrar nada)
docker compose down

# Reconstruir las imágenes después de cambios en el código
docker compose up --build

# Ver el estado de los contenedores
docker compose ps
```

---

## Arquitectura del proyecto

```
Summoners_Fantasy/
├── backend/          ← API REST (FastAPI + Python 3.11)
│   ├── Dockerfile    ← Imagen del contenedor backend
│   └── .env          ← Variables de entorno (no versionado)
│
├── frontend/         ← Interfaz web (Next.js 14 + TypeScript)
│   ├── Dockerfile    ← Imagen del contenedor frontend
│   └── .env.local    ← Variables de entorno (no versionado)
│
├── docker-compose.yml ← Orquestación de ambos servicios
└── despliegue.md      ← Este archivo
```

La base de datos está alojada en **Supabase** (Postgres administrado en la nube) — no requiere ningún contenedor adicional.
