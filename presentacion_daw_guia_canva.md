# 🎨 GUÍA PARA CREAR LA PRESENTACIÓN EN CANVA

## Paso 1: Abrir Canva y seleccionar template

1. Ir a https://www.canva.com
2. Buscar "Presentación tecnológica" o "Tech Presentation"
3. Alternativamente, usar el template de referencia: https://www.canva.com/templates/EAGYUVWCNP8/
4. Seleccionar formato: Presentación (1920 × 1080 px)
5. Click en "Personalizar este template"

---

## Paso 2: Configurar paleta de colores

**Colores de Summoner's Fantasy:**
- Cream (fondo): `#FDF8F0`
- Purple (primary): `#6B4C9A`
- Gold (accents): `#D4AF37`
- Dark (texto): `#1A1A2E`
- White (secondary): `#FFFFFF`

**Cómo aplicar:**
1. Click en el fondo del slide → Color → "+" → Pegar hex
2. Guardar como "Colores de marca" para uso rápido

---

## Paso 3: Crear los 22 slides

### Slide 1 - PORTADA
**Elementos:**
- Fondo: Purple (`#6B4C9A`)
- Título grande: "Summoner's Fantasy" (blanco, bold, 48px)
- Subtítulo: "Plataforma de Fantasy Esports para la LEC" (cream, 24px)
- Badge: "Proyecto Final DAW 2026" (gold, 18px)
- Tu nombre abajo (cream, 20px)
- Visual: Buscar "League of Legends logo" en Elements o subir imagen

**Layout:**
```
┌─────────────────────────────────────┐
│                                     │
│         [Logo LoL]                  │
│                                     │
│      SUMMONER'S FANTASY             │
│                                     │
│   Plataforma de Fantasy Esports     │
│         para la LEC                 │
│                                     │
│      [Badge: Proyecto Final DAW]    │
│                                     │
│          Tu Nombre                  │
│                                     │
└─────────────────────────────────────┘
```

---

### Slide 2 - ¿QUÉ ES SUMMONER'S FANTASY?
**Elementos:**
- Título: Purple, 36px
- 5 bullets con emojis (usar emojis de Canva)
- Screenshot del dashboard a la derecha

**Texto:**
- 🏟️ Private Leagues - Crea ligas privadas con amigos (hasta 10 miembros, $100 de presupuesto)
- 🎯 Auction Market - Mercado de jugadores con sistema de subastas a ciegas
- 📊 Real-Time Scoring - Puntos calculados automáticamente con datos reales de la LEC
- 🔄 Trade System - Intercambia jugadores con otros miembros de tu liga
- 📱 Responsive - Sidebar en desktop, bottom nav en móvil

**Layout:**
```
┌─────────────────────────────────────┐
│  ¿Qué es Summoner's Fantasy?        │
│                                     │
│  🏟️ Private Leagues...             │
│  🎯 Auction Market...               │
│  📊 Real-Time Scoring...            │
│  🔄 Trade System...                 │
│  📱 Responsive...                   │
│                                     │
│           [Screenshot]              │
└─────────────────────────────────────┘
```

---

### Slide 3 - EL PROBLEMA / LA MOTIVACIÓN
**Elementos:**
- Dos columnas (Problema vs Oportunidad)
- Checkmarks y X marks rojos/verdes

**Texto columna izquierda (Problema):**
- ❌ Las apps existentes son genéricas
- ❌ No permiten ligas privadas con reglas custom
- ❌ Los sistemas de scoring no son transparentes
- ❌ No hay mercado de jugadores dinámico

**Texto columna derecha (Oportunidad):**
- ✅ Crear una experiencia más social y competitiva
- ✅ Scoring transparente y personalizado por rol
- ✅ Mercado de subastas que refleja valor real

---

### Slide 4 - HISTORIA PERSONAL
**Elementos:**
- Timeline horizontal
- Iconos para cada hito

**Timeline:**
1. 🎮 Enero 2026 - Idea inicial
2. 💻 Febrero 2026 - Primer prototipo (Google Sheets)
3. 🚀 Marzo 2026 - Decido construir la app
4. 🏗️ Abril 2026 - Arquitectura completa
5. 📚 Mayo 2026 - Proyecto final de DAW

---

### Slides 5-8 - DEMO
**Elementos:**
- Screenshots grandes de cada flow
- Flechas indicando el flow
- Captions explicando cada paso

**Qué capturar:**
1. Login page
2. Dashboard con ligas
3. Lineup screen
4. Market screen
5. Standings screen

**Tip:** Usar "Mockup" de Canva para poner screenshots en frames de dispositivos

---

### Slide 9 - ARQUITECTURA GENERAL
**Elementos:**
- Diagrama de bloques
- Flechas de flujo
- Iconos para cada capa

**Diagrama (copiar y adaptar):**
```
┌─────────────────────────────────────┐
│     DATA PIPELINE (hourly)          │
│  gol.gg → Cloudflare API → ingest   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      SUPABASE (PostgreSQL + RLS)    │
│  players, series, leagues, market   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│        FASTAPI BACKEND              │
│  /players, /leagues, /market        │
│  APScheduler (hourly jobs)          │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│       NEXT.JS 14 FRONTEND           │
│  /dashboard, /leagues, /market      │
└─────────────────────────────────────┘
```

**Cómo hacerlo en Canva:**
1. Insert → Shapes → Rectangles para cada capa
2. Insert → Lines → Arrows para conexiones
3. Text boxes para labels
4. Usar colores: Purple para boxes, Gold para arrows

---

### Slide 10 - FRONTEND STACK
**Elementos:**
- Logos de Next.js, TypeScript, Tailwind
- Tree structure para carpetas

**Estructura:**
```
frontend/src/
├── app/
│   ├── (auth)/          → login, signup
│   └── (protected)/     → dashboard, leagues
├── components/          → UI reusable
└── lib/                 → utils, api client
```

---

### Slide 11 - BACKEND STACK
**Elementos:**
- Logos de FastAPI, Python, APScheduler
- Lista de endpoints
- Lista de jobs programados

**Endpoints (usar formato code):**
```
/players          → CRUD jugadores
/leagues          → Ligas privadas
/market           → Listings y bids
/scoring          → Cálculo de puntos
/trades           → Intercambios
```

---

### Slide 12 - DATA PIPELINE
**Elementos:**
- Logo de Cloudflare
- Logo de gol.gg (o screenshot)
- Flow diagram paso a paso

**Flow:**
```
1. fetch_matchlist(slug)
2. fetch_game_fullstats(game_id)
3. fetch_game_meta(game_id)
4. Calcular fantasy points
5. Upsert a Supabase
```

---

### Slide 13 - BASE DE DATOS
**Elementos:**
- Logo de Supabase
- Logo de PostgreSQL
- Screenshot del dashboard de Supabase

**Bullets:**
- PostgreSQL completo con RLS nativo
- Auth integrado
- Migrations versionadas
- 20+ tablas, ~400 líneas de migraciones

---

### Slide 14 - MODELO DE DATOS
**Elementos:**
- Diagrama ERD simplificado
- Dos secciones: Core LEC vs Fantasy Layer

**Core LEC:**
- competitions → teams → players → series → games → stats

**Fantasy Layer:**
- fantasy_leagues → league_members → roster_slots → market_listings → bids

---

### Slide 15 - ROW-LEVEL SECURITY
**Elementos:**
- Diagrama de cómo RLS filtra queries
- Código SQL de ejemplo (usar formato monospace)

**SQL ejemplo:**
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

---

### Slide 16 - EL MAYOR DESAFÍO
**Elementos:**
- Screenshot de gol.gg
- Lista de complejidades con iconos

**Complejidades:**
- 🧩 Resolver nombres de equipos (aliases)
- 🧩 Calcular puntos con weights por rol
- 🧩 Manejar BO3/BO5 (promedios)
- 🧩 Actualizar precios sin duplicar
- 🧩 Auto-avanzar current_week

---

### Slide 17 - LA SOLUCIÓN - PIPELINE
**Elementos:**
- Diagrama de flujo numerado (1-10)
- Iconos para cada paso

**Pasos clave (resumir a 6-8 para el slide):**
1. Lookup competiciones activas
2. Fetch matchlist desde gol.gg
3. Filtrar por current_week
4. Agrupar games por serie
5. Resolver equipos por aliases
6. Calcular fantasy points
7. Upsert a DB
8. Auto-avanzar current_week

---

### Slide 18 - SCORING ENGINE
**Elementos:**
- Tabla con weights por rol
- Fórmula de anti-snowball

**Tabla:**
| Rol | Kills | Deaths | CS/min | Special |
|-----|-------|--------|--------|---------|
| Top | 1.0 | -0.5 | 0.3 | gold diff |
| Jungle | 1.0 | -0.5 | 0.3 | obj steals 1.5 |
| Mid | 1.2 | -0.5 | 0.3 | gold diff |
| ADC | 1.3 | -0.5 | 0.3 | damage share |
| Support | 0.5 | -0.3 | - | vision score |

---

### Slide 19 - LEARNINGS
**Elementos:**
- Tres columnas: Técnico, Arquitectura, Soft Skills

**Técnico:**
- Next.js 14 App Router
- FastAPI + async Python
- PostgreSQL RLS
- Cloudflare Browser Rendering

**Arquitectura:**
- Separación frontend/backend/DB
- Idempotencia en pipelines
- RLS como seguridad

**Soft Skills:**
- Debugging sistemático
- Documentación técnica
- Gestión de dependencias

---

### Slide 20 - ESPECIALIZACIÓN
**Elementos:**
- Tres iconos: Backend, Big Data, IA

**Backend:**
- Lógica compleja (scoring, pipeline)
- Arquitecturas escalables

**Big Data:**
- Miles de stats de jugadores
- Pipelines ETL en tiempo real

**IA:**
- AI como Jarvis (agentic development)
- Engram: memoria persistente
- SDD: spec-driven development

---

### Slide 21 - FUTURO DEL PROYECTO
**Elementos:**
- Timeline horizontal (Short/Medium/Long term)

**Short-term:**
- Más regiones (LCK, LPL, LCS)
- Mejorar analytics
- Playoffs bracket predictor

**Medium-term:**
- ML para predecir precios
- App móvil nativa
- Multi-language

**Long-term:**
- Riot API oficial
- Monetización
- Partnerships con equipos LEC

---

### Slide 22 - Q&A / GRACIAS
**Elementos:**
- Fondo purple
- "¡Gracias!" grande (blanco)
- "¿Preguntas?" abajo
- Links: Web, GitHub, Email
- QR code a summoners-fantasy.com

**Cómo generar QR:**
1. Ir a https://www.qr-code-generator.com
2. Pegar URL: https://summoners-fantasy.com
3. Descargar PNG
4. Subir a Canva

---

## Paso 4: Exportar presentación

1. Click en "Compartir" (arriba derecha)
2. "Descargar"
3. Formato: PDF Standard (para presentar offline)
4. También: "Presentar" para modo presentación online
5. Opcional: "Obtener link" para compartir

---

## Consejos de diseño

1. **Consistencia:** Usar misma fuente y tamaños en todos los slides
2. **Espacio en blanco:** No saturar, dejar aire entre elementos
3. **Contraste:** Texto oscuro sobre fondo claro, viceversa para títulos
4. **Imágenes:** Usar screenshots reales de la app
5. **Animaciones:** Usar con moderación (fade in simple)
6. **Notas del orador:** Canva permite agregar notas por slide

---

## Recursos visuales a buscar en Canva

- "Technology presentation"
- "Software architecture"
- "Database diagram"
- "Flowchart"
- "Timeline"
- "League of Legends" (puede haber fan art)
- "Esports"
- "Code snippet" (para mostrar código)

---

## Tiempo estimado de creación

- Configurar template y colores: 10 min
- Crear 22 slides con contenido: 60-90 min
- Buscar/agregar imágenes: 30 min
- Revisar y ajustar: 20 min
- **Total: ~2-2.5 horas**

---

**¡Éxitos con la presentación! 🚀**
