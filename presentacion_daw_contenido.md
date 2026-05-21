# 🏆 Summoner's Fantasy - Presentación Final DAW
## Duración: 20-25 minutos | 22 slides aprox.

---

## 📑 ÍNDICE DE SLIDES

### SECCIÓN 1: INTRODUCCIÓN (3 min)
- Slide 1: Portada
- Slide 2: ¿Qué es Summoner's Fantasy?
- Slide 3: El problema / La motivación
- Slide 4: Historia personal: De hobby a proyecto académico

### SECCIÓN 2: DEMO (5 min)
- Slide 5: Demo - Login y Dashboard
- Slide 6: Demo - Gestión de Equipo (Lineup)
- Slide 7: Demo - Mercado de Jugadores
- Slide 8: Demo - Clasificación y Activity Feed

### SECCIÓN 3: ARQUITECTURA (5 min)
- Slide 9: Arquitectura General - Diagrama de Despliegue
- Slide 10: Frontend - Next.js 14 + TypeScript
- Slide 11: Backend - FastAPI + APScheduler
- Slide 12: Data Pipeline - Cloudflare Browser Rendering API

### SECCIÓN 4: BASE DE DATOS (4 min)
- Slide 13: Supabase - PostgreSQL con RLS
- Slide 14: Modelo de Datos - Tablas Principales
- Slide 15: Row-Level Security - Cómo funciona

### SECCIÓN 5: DESAFÍOS TÉCNICOS (4 min)
- Slide 16: El mayor desafío - Ingesta de partidos
- Slide 17: Solución - Pipeline de 10 pasos
- Slide 18: Scoring Engine - Cálculo de puntos fantasy

### SECCIÓN 6: CIERRE (3-4 min)
- Slide 19: Learnings - Qué aprendí
- Slide 20: Especialización - Backend, Big Data e IA
- Slide 21: Futuro del proyecto
- Slide 22: Q&A / Gracias

---

## 📝 CONTENIDO DETALLADO POR SLIDE

### Slide 1: PORTADA
**Título:** Summoner's Fantasy  
**Subtítulo:** Plataforma de Fantasy Esports para la LEC  
**Badge:** Proyecto Final DAW 2026  
**Autor:** [Tu nombre]  
**Visual:** Logo de League of Legends + título con estilo cream/purple/gold

**Notas del orador (30 seg):**
"Buenos días, soy [nombre] y hoy les voy a presentar Summoner's Fantasy, una plataforma de fantasy esports para la liga europea de League of Legends que empezó como un hobby para jugar con amigos y terminó convirtiéndose en mi proyecto final de DAW por su complejidad técnica."

---

### Slide 2: ¿QUÉ ES SUMMONER'S FANTASY?
**Título:** ¿Qué es Summoner's Fantasy?

**Contenido:**
- 🏟️ **Private Leagues** - Crea ligas privadas con amigos (hasta 10 miembros, $100 de presupuesto)
- 🎯 **Auction Market** - Mercado de jugadores con sistema de subastas a ciegas
- 📊 **Real-Time Scoring** - Puntos calculados automáticamente con datos reales de la LEC
- 🔄 **Trade System** - Intercambia jugadores con otros miembros de tu liga
- 📱 **Responsive** - Sidebar en desktop, bottom nav en móvil

**Visual:** Screenshot del dashboard principal

**Notas del orador (30 seg):**
"Summoner's Fantasy es una app donde gestionas tu equipo ideal de jugadores profesionales de la LEC. Cada usuario crea o se une a ligas privadas, tiene un presupuesto de $100 para armar su roster de 5 jugadores (uno por rol), y compite contra sus amigos basándose en el rendimiento real de esos jugadores en los partidos oficiales."

---

### Slide 3: EL PROBLEMA / LA MOTIVACIÓN
**Título:** ¿Por qué esta app?

**Contenido:**
**Problema:**
- ❌ Las apps existentes de fantasy LEC son genéricas
- ❌ No permiten ligas privadas con reglas custom
- ❌ Los sistemas de scoring no son transparentes
- ❌ No hay mercado de jugadores dinámico

**Oportunidad:**
- ✅ Crear una experiencia más social y competitiva
- ✅ Scoring transparente y personalizado por rol
- ✅ Mercado de subastas que refleja valor real

**Visual:** Comparación lado a lado (apps existentes vs Summoner's Fantasy)

**Notas del orador (1 min):**
"Cuando empecé a jugar fantasy LEC con amigos, probé las plataformas existentes. El problema: todas son muy genéricas, no puedes crear ligas verdaderamente privadas con tus propias reglas, y el scoring es una caja negra. Quería algo más social, más competitivo, donde el sistema de puntuación tenga sentido según el rol de cada jugador. Así que decidí construirla yo mismo."

---

### Slide 4: HISTORIA PERSONAL
**Título:** De hobby a proyecto académico

**Contenido:**
**Timeline:**
1. 🎮 **Enero 2026** - Idea inicial: "Armemos un fantasy para la LEC"
2. 💻 **Febrero 2026** - Primer prototipo: Google Sheets + scraping manual
3. 🚀 **Marzo 2026** - Decido construir la app completa
4. 🏗️ **Abril 2026** - Arquitectura completa + pipeline automático
5. 📚 **Mayo 2026** - Evoluciona a proyecto final de DAW

**¿Por qué evolved?**
- La complejidad técnica creció exponencialmente
- El pipeline de datos se convirtió en un desafío de big data
- La arquitectura multi-servicio merecía documentación académica

**Visual:** Timeline horizontal con hitos

**Notas del orador (1 min):**
"Esto empezó literalmente como un Google Sheet donde anotábamos los stats de los jugadores manualmente. Cuando mis amigos me dijeron 'esto debería ser automático', me di cuenta de la complejidad real: tenía que scrapear datos de gol.gg, procesarlos, calcular scores, actualizar precios... Cada capa que agregaba revelaba nuevos desafíos técnicos. Ahí me di cuenta: esto no es solo un hobby, es un proyecto que demuestra todo lo que aprendí en DAW."

---

### Slide 5: DEMO - LOGIN Y DASHBOARD
**Título:** Demo - Primeros pasos

**Contenido:**
**Flow a mostrar:**
1. Landing page con login
2. Registro de nuevo usuario
3. Dashboard con lista de ligas
4. Crear nueva liga (genera invite code)
5. Unirse a liga existente

**Features clave:**
- 🔐 Auth con Supabase (JWT)
- 🎨 UI responsive cream/purple/gold
- ⚡ Server Components para carga rápida

**Visual:** Screenshots del flow de login → dashboard

**Notas del orador (1 min):**
*[Aquí hacés la demo en vivo]*
"Les muestro cómo funciona. Primero el login, que usa Supabase Auth con JWT. Al entrar, ven el dashboard con tus ligas. Pueden crear una nueva —que genera un código de invitación automático— o unirse a una existente. Todo esto carga con Server Components de Next.js para que sea lo más rápido posible."

---

### Slide 6: DEMO - GESTIÓN DE EQUIPO (LINEUP)
**Título:** Demo - Armar tu equipo

**Contenido:**
**Flow a mostrar:**
1. Entrar a una liga
2. Ver roster actual (5 slots: Top, Jungle, Mid, ADC, Support)
3. Cambiar un jugador del mercado
4. Ver puntos proyectados vs reales

**Features clave:**
- 🎯 5 roles obligatorios
- 💰 Presupuesto de $100
- 📊 Puntos calculados por rol (weights diferentes)

**Visual:** Screenshot de la pantalla de lineup

**Notas del orador (1 min):**
*[Continuás la demo]*
"Acá está el núcleo del juego. Tenés que armar tu roster con un jugador por rol. Cada rol tiene un sistema de scoring diferente —no es lo mismo un Jungle que un ADC—. El sistema valida que tengas exactamente 5 jugadores y que no te pases del presupuesto. Los puntos se actualizan automáticamente después de cada serie de la LEC."

---

### Slide 7: DEMO - MERCADO DE JUGADORES
**Título:** Demo - Mercado de subastas

**Contenido:**
**Flow a mostrar:**
1. Ver listings activos del mercado
2. Hacer un bid (puja ciega)
3. Ver histórico de transacciones
4. Sistema de rotación hourly

**Features clave:**
- 🛒 Blind bid system (no ves las pujas de otros)
- ⏰ Listings rotan cada hora
- 📈 Precios basados en performance reciente

**Visual:** Screenshot del mercado con cards de jugadores

**Notas del orador (1 min):**
*[Continuás la demo]*
"El mercado es un sistema de subastas a ciegas. Cuando ves un jugador, no sabés cuánto pujaron otros. El mercado rota cada hora automáticamente gracias a APScheduler. Los precios de los jugadores se ajustan según su performance —si un jugador rompe la última semana, su precio sube—."

---

### Slide 8: DEMO - CLASIFICACIÓN Y ACTIVITY
**Título:** Demo - Standings y Activity

**Contenido:**
**Flow a mostrar:**
1. Ver leaderboard de la liga
2. Ver activity feed (últimas transacciones)
3. Ver detalle de puntos por jugador

**Features clave:**
- 🏆 Standings por split (season resets)
- 📰 Activity feed en tiempo real
- 📊 Stats históricas preservadas

**Visual:** Screenshot del standings + activity feed

**Notas del orador (1 min):**
*[Terminás la demo]*
"Acá ven la clasificación de su liga y el feed de actividad. Cada transacción, puja ganada o trade queda registrado. El standings se resetea por split pero las stats históricas se mantienen. Todo esto es en tiempo real —cuando terminan los partidos de la LEC, los puntos se actualizan solos."

---

### Slide 9: ARQUITECTURA GENERAL
**Título:** Arquitectura de Despliegue

**Contenido:**
```
┌─────────────────────────────────────────────────────────────┐
│                  DATA PIPELINE (hourly)                     │
│  gol.gg → Cloudflare Browser API → series_ingest.py         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               SUPABASE (PostgreSQL + RLS)                   │
│  players, series, games, fantasy_leagues, market_listings   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  FASTAPI BACKEND                            │
│  /players, /leagues, /market, /scoring, /trades             │
│  APScheduler: series_ingest, market_refresh, split_reset    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               NEXT.JS 14 FRONTEND                           │
│  /dashboard, /leagues/[id]/lineup, /market, /standings      │
└─────────────────────────────────────────────────────────────┘
```

**Visual:** Diagrama de arquitectura (arriba)

**Notas del orador (1 min):**
"Esta es la arquitectura completa. Arriba tienen el data pipeline que scrapear gol.gg cada hora usando la Cloudflare Browser Rendering API. Los datos van a Supabase (PostgreSQL). El backend en FastAPI expone los endpoints REST y corre jobs programados con APScheduler. El frontend en Next.js consume la API y se despliega en Vercel."

---

### Slide 10: FRONTEND - NEXT.JS 14
**Título:** Frontend Stack

**Contenido:**
**Tecnologías:**
- ⚛️ **Next.js 14** con App Router
- 📘 **TypeScript 5.x** (strict mode)
- 🎨 **TailwindCSS** (design system cream/purple/gold)
- 🔐 **Supabase Auth** (JWT + SSR)

**Decisiones de arquitectura:**
- ✅ Server Components para datos (menos client JS)
- ✅ File-based routing (`/leagues/[id]/lineup`)
- ✅ Responsive: sidebar desktop / bottom nav mobile

**Estructura:**
```
frontend/src/
├── app/
│   ├── (auth)/          → login, signup
│   └── (protected)/     → dashboard, leagues
├── components/          → UI reusable
└── lib/                 → utils, api client
```

**Visual:** Screenshot de la estructura de carpetas + UI

**Notas del orador (30 seg):**
"El frontend usa Next.js 14 con App Router. La decisión clave: usar Server Components siempre que sea posible para reducir JavaScript en el cliente. La UI es responsive con un design system propio en tonos cream, purple y gold. Auth integrado con Supabase para SSR."

---

### Slide 11: BACKEND - FASTAPI
**Título:** Backend Stack

**Contenido:**
**Tecnologías:**
- ⚡ **FastAPI 0.100+** (async-ready)
- 🕐 **APScheduler** (background jobs)
- 🐍 **Python 3.11+**
- 🔒 **JWT Auth** (dependency injection)

**Endpoints principales:**
```
/players          → CRUD jugadores
/leagues          → Ligas privadas
/market           → Listings y bids
/scoring          → Cálculo de puntos
/trades           → Intercambios
/roster           → Gestión de lineup
/activity         → Feed de eventos
```

**Jobs programados (hourly):**
- `series_ingest` → Pipeline de datos
- `market_refresh` → Rotación de listings
- `split_reset` → Reset de temporada

**Visual:** Screenshot de Swagger UI (/docs)

**Notas del orador (1 min):**
"El backend es FastAPI, elegido por su soporte async nativo y documentación automática con Swagger. Los jobs corren en un BackgroundScheduler de APScheduler —cada hora se ejecutan la ingesta de partidos y el refresco del mercado. Hay protección por entorno para endpoints de debug en producción."

---

### Slide 12: DATA PIPELINE - CLOUDFLARE API
**Título:** Data Pipeline Automatizado

**Contenido:**
**Fuente:** gol.gg (stats de LEC)  
**Método:** Cloudflare Browser Rendering API  
**Frecuencia:** Cada hora

**¿Por qué Cloudflare?**
- ❌ gol.gg no tiene API pública
- ❌ Scraping tradicional bloqueado por anti-bot
- ✅ Cloudflare Browser Rendering = browser headless gestionado
- ✅ Endpoint que devuelve markdown parseable

**Flow:**
```
1. fetch_matchlist(slug) → lista de partidos
2. fetch_game_fullstats(game_id) → stats por jugador
3. fetch_game_meta(game_id) → duración, winner
4. Calcular fantasy points
5. Upsert a Supabase
```

**Visual:** Diagrama del pipeline

**Notas del orador (1 min):**
"Este es el corazón del sistema. gol.gg no tiene API pública, así que uso la Cloudflare Browser Rendering API, que es básicamente un browser headless gestionado. Le paso la URL de gol.gg y me devuelve el contenido en markdown, que es fácil de parsear. Esto corre cada hora automáticamente y procesa todos los partidos de la semana actual."

---

### Slide 13: BASE DE DATOS - SUPABASE
**Título:** Supabase - PostgreSQL con RLS

**Contenido:**
**¿Por qué Supabase?**
- ✅ PostgreSQL completo (no un NoSQL limitado)
- ✅ Row-Level Security nativo
- ✅ Auth integrado
- ✅ Migrations versionadas
- ✅ Dashboard para queries manuales

**Configuración:**
- 📍 Región: Frankfurt (baja latencia para Europa)
- 🔐 RLS habilitado en TODAS las tablas
- 🔑 Service role key solo en backend

**Visual:** Screenshot del dashboard de Supabase

**Notas del orador (30 seg):**
"Elegí Supabase porque necesitaba PostgreSQL con relaciones complejas y RLS nativo. Cada tabla tiene Row-Level Security activado —los usuarios solo ven datos de las ligas a las que pertenecen. El backend usa la service role key para bypass, el frontend va directo a Supabase con RLS activo."

---

### Slide 14: MODELO DE DATOS
**Título:** Esquema de Base de Datos

**Contenido:**
**Tablas principales (387 líneas de migraciones):**

**Core LEC:**
- `competitions` → LEC Spring/Summer
- `teams` → Equipos con aliases[] para fuzzy matching
- `players` → Jugadores con rol, precio, historial
- `series` → BO3/BO5 entre dos equipos
- `games` → Partidas individuales dentro de una serie
- `player_game_stats` → Stats + fantasy points por game
- `player_series_stats` → Promedios por serie

**Fantasy Layer:**
- `fantasy_leagues` → Ligas privadas con invite codes
- `league_members` → Usuarios con presupuesto y puntos
- `roster_slots` → 5 slots por miembro (Top/Jungle/Mid/ADC/Support)
- `market_listings` → Listings activos con closes_at
- `bids` → Pujas ciegas
- `trades` → Intercambios entre miembros
- `transactions` → Historial inmutable
- `activity_log` → Feed de eventos

**Visual:** Diagrama ERD simplificado

**Notas del orador (1 min):**
"Tengo dos capas de tablas. La capa 'Core LEC' con datos reales de la liga: competiciones, equipos, jugadores, series, games y stats. La capa 'Fantasy Layer' con toda la lógica del juego: ligas privadas, rosters, mercado, bids, trades. Las relaciones son complejas —un miembro tiene 5 roster slots, una serie tiene múltiples games, cada game tiene stats de 10 jugadores—."

---

### Slide 15: ROW-LEVEL SECURITY
**Título:** RLS - Seguridad a nivel de fila

**Contenido:**
**¿Qué es RLS?**
- PostgreSQL permite definir políticas QUE FILTROS SE APLICAN A CADA FILA
- No es un middleware de la app —es la DB que filtra
- Imposible de bypassear desde el cliente

**Ejemplo real (roster_slots):**
```sql
CREATE POLICY "users_see_own_league_rosters"
  ON roster_slots FOR SELECT
  USING (
    league_id IN (
      SELECT league_id FROM league_members
      WHERE user_id = auth.uid()
    )
  );
```

**Políticas por tabla:**
| Tabla | Política |
|-------|----------|
| `players` | SELECT público (datos de LEC) |
| `fantasy_leagues` | Solo miembros ven su liga |
| `roster_slots` | Solo miembros de esa liga |
| `bids` | Solo el usuario que puja |
| `activity_log` | Solo miembros de la liga |

**Visual:** Diagrama de cómo RLS filtra queries

**Notas del orador (1 min):**
"RLS es crítico para la seguridad. Cuando un usuario hace una query, PostgreSQL filtra las filas ANTES de devolverlas. En el ejemplo, un usuario solo ve roster slots de ligas donde es miembro. Esto no se puede bypassear —incluso si alguien intenta manipular el cliente, la DB rechaza la query. Es seguridad en la capa de datos, no en la app."

---

### Slide 16: EL MAYOR DESAFÍO
**Título:** El desafío técnico #1 - Ingesta de partidos

**Contenido:**
**El problema:**
- ❌ gol.gg no tiene API → scraping necesario
- ❌ Anti-bot protection → bloquea requests directos
- ❌ Datos en HTML no estructurado → parsing complejo
- ❌ 10 jugadores × ~10 games/semana × múltiples series
- ❌ Datos deben ser consistentes (no puedo fallar a mitad)

**Complejidades:**
- 🧩 Resolver nombres de equipos (aliases: "G2" vs "G2 Esports")
- 🧩 Calcular puntos con weights por rol
- 🧩 Manejar BO3/BO5 (promediar stats por serie)
- 🧩 Actualizar precios sin duplicar
- 🧩 Auto-avanzar current_week cuando termina

**Visual:** Screenshot de gol.gg con datos complejos

**Notas del orador (1 min):**
"Este fue EL desafío. Tenés que scrapear un sitio sin API, con anti-bot, parsear HTML complejo, resolver nombres de equipos que varían, calcular puntos con fórmulas diferentes por rol, promediar stats en BO3/BO5, actualizar precios sin duplicar, y auto-detectar cuándo avanza la semana. Cualquier error y tenés datos inconsistentes. Me llevó semanas tenerlo estable."

---

### Slide 17: LA SOLUCIÓN - PIPELINE DE 10 PASOS
**Título:** Arquitectura del Pipeline

**Contenido:**
**Flujo completo (run_series_ingest):**

```
1. Lookup competiciones activas (LEC Spring)
2. Fetch matchlist desde gol.gg (Cloudflare API)
3. Filtrar por current_week (solo jornada actual)
4. Agrupar games por serie (home/away/fecha)
5. Snapshot de game_ids existentes (idempotencia)
6. Por cada serie:
   a. Resolver equipos por aliases
   b. Upsert serie en DB
   c. Por cada game: fetch stats + meta
   d. Calcular fantasy points por jugador
   e. Upsert player_game_stats
   f. Calcular promedios → player_series_stats
   g. Actualizar winner_id y game_count
7. Actualizar precios (solo games nuevos)
8. Auto-avanzar current_week si todas finished
9. Snapshot de alineaciones (idempotente)
10. Calcular total_points de managers
```

**Visual:** Diagrama de flujo numerado

**Notas del orador (1 min):**
"Acá está la solución paso a paso. Lo clave: idempotencia. Si el pipeline falla a mitad, puede rerunear sin duplicar datos. El snapshot de game_ids existentes previene updates de precio duplicados. La resolución de aliases maneja nombres variables. Y el auto-avance de current_week detecta automáticamente cuándo termina la semana."

---

### Slide 18: SCORING ENGINE
**Título:** Cálculo de Puntos Fantasy

**Contenido:**
**Fórmula por rol (weights diferentes):**

| Rol | Stats clave | Weights |
|-----|-------------|---------|
| Top | kills, deaths, assists, CS/min, gold diff @15 | 1.0, -0.5, 0.5, 0.3, 0.2 |
| Jungle | kills, deaths, assists, CS/min, **obj steals** | 1.0, -0.5, 0.5, 0.3, **1.5** |
| Mid | kills, deaths, assists, CS/min, gold diff @15 | 1.2, -0.5, 0.5, 0.3, 0.2 |
| ADC | kills, deaths, assists, CS/min, **damage share** | 1.3, -0.5, 0.5, 0.3, **0.8** |
| Support | kills, deaths, assists, **vision score**, obj steals | 0.5, -0.3, 0.8, **1.0**, 1.0 |

**Bonificaciones:**
- Double Kill: +2 pts
- Triple Kill: +5 pts
- Quadra Kill: +8 pts
- Penta Kill: +15 pts

**Anti-snowball:**
```python
if duration > 30 min:
    points = points / (1 + excess_minutes × 0.01)
```

**Visual:** Tabla de weights + fórmula

**Notas del orador (1 min):**
"El scoring no es igual para todos los roles. Un Jungle gana puntos por robar objetivos, un Support por visión, un ADC por damage share. Hay bonificaciones por multikills —una penta kill son 15 puntos—. Y hay un dampening factor: si el partido dura más de 30 minutos, los puntos se normalizan para evitar que late-game inflation distorsione el scoring."

---

### Slide 19: LEARNINGS
**Título:** Qué aprendí

**Contenido:**
**Técnico:**
- ✅ Next.js 14 App Router (Server Components vs Client)
- ✅ FastAPI + async patterns en Python
- ✅ PostgreSQL avanzado (RLS, triggers, arrays)
- ✅ Scraping con Cloudflare Browser Rendering
- ✅ APScheduler para background jobs
- ✅ TypeScript strict mode a escala

**Arquitectura:**
- ✅ Separación clara frontend/backend/DB
- ✅ Idempotencia en pipelines de datos
- ✅ RLS como seguridad de capa de datos
- ✅ Design patterns: repository, dependency injection

**Soft skills:**
- ✅ Debugging sistemático (logs, tracing)
- ✅ Documentación técnica (README, comentarios)
- ✅ Gestión de dependencias y versionado

**Visual:** Lista de learnings con iconos

**Notas del orador (1 min):**
"Técnicamente, aprendí un montón: desde Server Components de Next.js hasta RLS de PostgreSQL. Pero lo más importante fue aprender a debuggear sistemáticamente —cuando el pipeline fallaba, tenía que trazar logs a través de 10 capas—. Y a documentar: sin un README claro, hubiera olvidado por qué tomé ciertas decisiones."

---

### Slide 20: ESPECIALIZACIÓN
**Título:** Mi camino: Backend, Big Data e IA

**Contenido:**
**Por qué Backend:**
- 🧠 Me encanta la lógica compleja (scoring engine, pipeline)
- 🏗️ Disfréo diseñar arquitecturas escalables
- 📊 El desafío de datos masivos me motiva

**Por qué Big Data:**
- 📈 Procesar miles de stats de jugadores
- 🔄 Pipelines ETL en tiempo real
- 📊 Agregaciones y normalizaciones complejas

**Por qué IA:**
- 🤖 Usé AI como Jarvis, no como Stack Overflow
- 🧠 Engram: memoria persistente para decisiones
- 📋 SDD: spec-driven development con AI

**Visual:** Iconos de backend/data/AI

**Notas del orador (1 min):**
"Este proyecto confirmó que quiero especializarme en backend. Me encanta la lógica compleja —el scoring engine, el pipeline de datos—. Big Data porque procesar miles de stats en tiempo real es un desafío que me motiva. E IA porque usé herramientas agentic development: Engram para memoria persistente y SDD para spec-driven development. La AI fue mi Jarvis, no mi Stack Overflow."

---

### Slide 21: FUTURO DEL PROYECTO
**Título:** ¿Qué sigue?

**Contenido:**
**Short-term:**
- 🎯 Integrar más regiones (LCK, LPL, LCS)
- 📊 Mejorar analytics (gráficos de trends)
- 🏆 Playoffs bracket predictor

**Medium-term:**
- 🤖 ML para predecir precios de jugadores
- 📱 App móvil nativa (React Native)
- 🌍 Multi-language support

**Long-term:**
- 🎮 Integrar con Riot API oficial
- 💰 Monetización (premium features)
- 🏟️ Partnerships con equipos de LEC

**Visual:** Roadmap timeline

**Notas del orador (1 min):**
"El proyecto sigue vivo. A corto plazo: más regiones, mejor analytics. A mediano: ML para predecir precios de jugadores —tengo históricos de performance, puedo entrenar modelos—. A largo plazo: integrar con la API oficial de Riot y quizás monetizar features premium. Me encantaría que equipos oficiales de LEC usen esto para engagement con fans."

---

### Slide 22: Q&A / GRACIAS
**Título:** ¡Gracias!

**Contenido:**
**Links:**
- 🌐 Web: https://summoners-fantasy.com
- 💻 GitHub: github.com/[tu-username]/Summoners_Fantasy
- 📧 Email: [tu-email]

**¿Preguntas?**

**Visual:** QR code a la web + logo final

**Notas del orador (30 seg):**
"Esto fue Summoner's Fantasy. La web está en vivo, el código está en GitHub. ¿Tienen preguntas?"

---

## 🎨 GUÍA DE ESTILO VISUAL

**Paleta de colores (del README):**
- Cream: `#FDF8F0` (fondo principal)
- Purple: `#6B4C9A` (primary, headers)
- Gold: `#D4AF37` (accents, badges)
- Dark: `#1A1A2E` (texto)

**Tipografía:**
- Títulos: Font bold, 28-32px
- Body: Font regular, 16-18px
- Code: Monospace, 14px

**Layout:**
- Sidebar en desktop, bottom nav en mobile (como la app)
- Cards con shadow suave
- Iconos emojis para bullets

**Imágenes a incluir:**
1. Screenshot del dashboard
2. Screenshot del lineup
3. Screenshot del mercado
4. Screenshot del standings
5. Diagrama de arquitectura
6. Diagrama ERD
7. Screenshot de gol.gg
8. Screenshot de Swagger UI
9. Screenshot de Supabase dashboard

---

## 📊 MÉTRICAS DEL PROYECTO (para mencionar)

**Código:**
- ~387 líneas solo en README
- Backend: main.py (389 líneas) + pipeline (1490 líneas) + routers
- Frontend: Next.js 14 con App Router
- DB: ~20 migraciones SQL

**Complejidad:**
- 10 pasos en el pipeline de ingesta
- 5 roles con scoring diferente
- 7 tablas principales en fantasy layer
- 3 jobs programados hourly

**Tecnologías:**
- Next.js 14, FastAPI, Supabase, APScheduler, Cloudflare API, TypeScript, Python, TailwindCSS

---

## 🎯 CONSEJOS DE PRESENTACIÓN

1. **Ensayar la demo** - Que el flow sea fluido, tener datos de prueba cargados
2. **No leer los slides** - Las notas son guía, mirá a los profesores
3. **Destacar lo difícil** - La ingesta de datos es tu mayor logro técnico
4. **Mostrar pasión** - Es un proyecto que empezó como hobby, transmití eso
5. **Preparar preguntas** - Pensá qué te pueden preguntar (RLS, scoring, pipeline)
6. **Timing** - 20-25 minutos, ensayá con cronómetro
7. **QR code** - Poné un QR al final para que puedan probar la app

---

## 📌 CHECKLIST PRE-PRESENTACIÓN

- [ ] Presentación creada en Canva con este contenido
- [ ] Demo ensayada (login, lineup, market, standings)
- [ ] Datos de prueba cargados (usuarios, ligas, jugadores)
- [ ] Servicios corriendo (frontend:3002, backend:8000)
- [ ] Backup: screenshots por si falla la demo en vivo
- [ ] QR code generado a summoners-fantasy.com
- [ ] README.md actualizado con métricas recientes
- [ ] GitHub con commits visibles (historial de desarrollo)

---

**¡Éxitos con la presentación! 🚀**
