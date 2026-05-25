# 📝 NOTAS DEL ORADOR - Summoner's Fantasy
## Proyecto Final DAW | 20-25 minutos

---

## SLIDE 1 - PORTADA (30 seg)

**Decir:**
"Buenos días, soy [TU NOMBRE] y hoy les voy a presentar Summoner's Fantasy, una plataforma de fantasy esports para la liga europea de League of Legends que empezó como un hobby para jugar con amigos y terminó convirtiéndose en mi proyecto final de DAW por su complejidad técnica."

**Tips:**
- Contacto visual con los 3 profesores
- Sonreír, mostrar pasión
- No leer el slide

---

## SLIDE 2 - ¿QUÉ ES? (30 seg)

**Decir:**
"Summoner's Fantasy es una app donde gestionás tu equipo ideal de jugadores profesionales de la LEC. Cada usuario crea o se une a ligas privadas, tiene un presupuesto de $100 para armar su roster de 5 jugadores —uno por rol—, y compite contra sus amigos basándose en el rendimiento real de esos jugadores en los partidos oficiales."

**Tips:**
- Mencionar los 5 features clave rápido
- No entrar en detalle aún (viene en la demo)

---

## SLIDE 3 - EL PROBLEMA (1 min)

**Decir:**
"Cuando empecé a jugar fantasy LEC con amigos, probé las plataformas existentes. El problema: todas son muy genéricas, no podés crear ligas verdaderamente privadas con tus propias reglas, y el scoring es una caja negra. Quería algo más social, más competitivo, donde el sistema de puntuación tenga sentido según el rol de cada jugador. Así que decidí construirla yo mismo."

**Tips:**
- Validar que el problema tiene sentido
- Mostrar empatía con el usuario

---

## SLIDE 4 - HISTORIA PERSONAL (1 min)

**Decir:**
"Esto empezó literalmente como un Google Sheet donde anotábamos los stats de los jugadores manualmente. Cuando mis amigos me dijeron 'esto debería ser automático', me di cuenta de la complejidad real: tenía que scrapear datos de gol.gg, procesarlos, calcular scores, actualizar precios... Cada capa que agregaba revelaba nuevos desafíos técnicos. Ahí me di cuenta: esto no es solo un hobby, es un proyecto que demuestra todo lo que aprendí en DAW."

**Tips:**
- Contar como historia, no como lista
- Énfasis en "complejidad técnica"

---

## SLIDES 5-8 - DEMO (5 min total)

### Slide 5 - Login y Dashboard (1 min)

**Decir:**
*[Demo en vivo]*
"Les muestro cómo funciona. Primero el login, que usa Supabase Auth con JWT. Al entrar, ven el dashboard con tus ligas. Pueden crear una nueva —que genera un código de invitación automático— o unirse a una existente. Todo esto carga con Server Components de Next.js para que sea lo más rápido posible."

**Acciones:**
1. Mostrar landing page
2. Loguearse
3. Mostrar dashboard
4. Click en "Crear liga"

---

### Slide 6 - Lineup (1 min)

**Decir:**
*[Continuás la demo]*
"Acá está el núcleo del juego. Tenés que armar tu roster con un jugador por rol. Cada rol tiene un sistema de scoring diferente —no es lo mismo un Jungle que un ADC—. El sistema valida que tengas exactamente 5 jugadores y que no te pases del presupuesto. Los puntos se actualizan automáticamente después de cada serie de la LEC."

**Acciones:**
1. Entrar a una liga
2. Mostrar roster actual
3. Intentar cambiar un jugador

---

### Slide 7 - Mercado (1 min)

**Decir:**
*[Continuás la demo]*
"El mercado es un sistema de subastas a ciegas. Cuando ves un jugador, no sabés cuánto pujaron otros. El mercado rota cada hora automáticamente gracias a APScheduler. Los precios de los jugadores se ajustan según su performance —si un jugador rompe la última semana, su precio sube—."

**Acciones:**
1. Mostrar listings del mercado
2. Hacer un bid
3. Mostrar histórico de transacciones

---

### Slide 8 - Standings y Activity (1 min)

**Decir:**
*[Terminás la demo]*
"Acá ven la clasificación de su liga y el feed de actividad. Cada transacción, puja ganada o trade queda registrado. El standings se resetea por split pero las stats históricas se mantienen. Todo esto es en tiempo real —cuando terminan los partidos de la LEC, los puntos se actualizan solos."

**Acciones:**
1. Mostrar standings
2. Mostrar activity feed
3. Volver al dashboard

---

## SLIDE 9 - ARQUITECTURA (1 min)

**Decir:**
"Esta es la arquitectura completa. Arriba tienen el data pipeline que scrapear gol.gg cada hora usando la Cloudflare Browser Rendering API. Los datos van a Supabase (PostgreSQL). El backend en FastAPI expone los endpoints REST y corre jobs programados con APScheduler. El frontend en Next.js consume la API y se despliega en Vercel."

**Tips:**
- Señalar cada capa en el diagrama
- Mencionar que es unidireccional (flujo de datos)

---

## SLIDE 10 - FRONTEND (30 seg)

**Decir:**
"El frontend usa Next.js 14 con App Router. La decisión clave: usar Server Components siempre que sea posible para reducir JavaScript en el cliente. La UI es responsive con un design system propio en tonos cream, purple y gold. Auth integrado con Supabase para SSR."

**Tips:**
- Mencionar TypeScript strict mode
- Si preguntan: "Sí, todo tipado"

---

## SLIDE 11 - BACKEND (1 min)

**Decir:**
"El backend es FastAPI, elegido por su soporte async nativo y documentación automática con Swagger. Los jobs corren en un BackgroundScheduler de APScheduler —cada hora se ejecutan la ingesta de partidos y el refresco del mercado. Hay protección por entorno para endpoints de debug en producción."

**Tips:**
- Mencionar que Swagger está en /docs
- Si preguntan: "Sí, hay tests"

---

## SLIDE 12 - DATA PIPELINE (1 min)

**Decir:**
"Este es el corazón del sistema. gol.gg no tiene API pública, así que uso la Cloudflare Browser Rendering API, que es básicamente un browser headless gestionado. Le paso la URL de gol.gg y me devuelve el contenido en markdown, que es fácil de parsear. Esto corre cada hora automáticamente y procesa todos los partidos de la semana actual."

**Tips:**
- Énfasis en "Cloudflare Browser Rendering"
- Mencionar que es la solución al anti-bot

---

## SLIDE 13 - BASE DE DATOS (30 seg)

**Decir:**
"Elegí Supabase porque necesitaba PostgreSQL con relaciones complejas y RLS nativo. Cada tabla tiene Row-Level Security activado —los usuarios solo ven datos de las ligas a las que pertenecen. El backend usa la service role key para bypass, el frontend va directo a Supabase con RLS activo."

**Tips:**
- RLS es importante, lo vas a explicar después
- Mencionar que hay ~20 migraciones

---

## SLIDE 14 - MODELO DE DATOS (1 min)

**Decir:**
"Tengo dos capas de tablas. La capa 'Core LEC' con datos reales de la liga: competiciones, equipos, jugadores, series, games y stats. La capa 'Fantasy Layer' con toda la lógica del juego: ligas privadas, rosters, mercado, bids, trades. Las relaciones son complejas —un miembro tiene 5 roster slots, una serie tiene múltiples games, cada game tiene stats de 10 jugadores—."

**Tips:**
- Señalar las dos secciones en el diagrama
- No leer todas las tablas

---

## SLIDE 15 - RLS (1 min)

**Decir:**
"RLS es crítico para la seguridad. Cuando un usuario hace una query, PostgreSQL filtra las filas ANTES de devolverlas. En el ejemplo, un usuario solo ve roster slots de ligas donde es miembro. Esto no se puede bypassear —incluso si alguien intenta manipular el cliente, la DB rechaza la query. Es seguridad en la capa de datos, no en la app."

**Tips:**
- Énfasis en "imposible de bypassear"
- Si preguntan: mostrar el SQL de ejemplo

---

## SLIDE 16 - EL MAYOR DESAFÍO (1 min)

**Decir:**
"Este fue EL desafío. Tenés que scrapear un sitio sin API, con anti-bot, parsear HTML complejo, resolver nombres de equipos que varían, calcular puntos con fórmulas diferentes por rol, promediar stats en BO3/BO5, actualizar precios sin duplicar, y auto-detectar cuándo avanza la semana. Cualquier error y tenés datos inconsistentes. Me llevó semanas tenerlo estable."

**Tips:**
- Mostrar frustración genuina
- Énfasis en "semanas tenerlo estable"

---

## SLIDE 17 - LA SOLUCIÓN (1 min)

**Decir:**
"Acá está la solución paso a paso. Lo clave: idempotencia. Si el pipeline falla a mitad, puede rerunear sin duplicar datos. El snapshot de game_ids existentes previene updates de precio duplicados. La resolución de aliases maneja nombres variables. Y el auto-avance de current_week detecta automáticamente cuándo termina la semana."

**Tips:**
- Mencionar "idempotencia" (palabra clave)
- Si preguntan: explicar el snapshot

---

## SLIDE 18 - SCORING ENGINE (1 min)

**Decir:**
"El scoring no es igual para todos los roles. Un Jungle gana puntos por robar objetivos, un Support por visión, un ADC por damage share. Hay bonificaciones por multikills —una penta kill son 15 puntos—. Y hay un dampening factor: si el partido dura más de 30 minutos, los puntos se normalizan para evitar que late-game inflation distorsione el scoring."

**Tips:**
- Mencionar ejemplos concretos (Jungle, Support)
- "Dampening factor" suena técnico, está bien

---

## SLIDE 19 - LEARNINGS (1 min)

**Decir:**
"Técnicamente, aprendí un montón: desde Server Components de Next.js hasta RLS de PostgreSQL. Pero lo más importante fue aprender a debuggear sistemáticamente —cuando el pipeline fallaba, tenía que trazar logs a través de 10 capas—. Y a documentar: sin un README claro, hubiera olvidado por qué tomé ciertas decisiones."

**Tips:**
- Ser genuino, no suena a discurso
- Mencionar "debuggear sistemáticamente"

---

## SLIDE 20 - ESPECIALIZACIÓN (1 min)

**Decir:**
"Este proyecto confirmó que quiero especializarme en backend. Me encanta la lógica compleja —el scoring engine, el pipeline de datos—. Big Data porque procesar miles de stats en tiempo real es un desafío que me motiva. E IA porque usé herramientas agentic development: Engram para memoria persistente y SDD para spec-driven development. La AI fue mi Jarvis, no mi Stack Overflow."

**Tips:**
- Énfasis en "Jarvis, no Stack Overflow"
- Mencionar Engram y SDD (suena avanzado)

---

## SLIDE 21 - FUTURO (1 min)

**Decir:**
"El proyecto sigue vivo. A corto plazo: más regiones, mejor analytics. A mediano: ML para predecir precios de jugadores —tengo históricos de performance, puedo entrenar modelos—. A largo plazo: integrar con la API oficial de Riot y quizás monetizar features premium. Me encantaría que equipos oficiales de LEC usen esto para engagement con fans."

**Tips:**
- Mostrar visión a largo plazo
- ML para predecir precios (suena a big data)

---

## SLIDE 22 - Q&A (30 seg)

**Decir:**
"Esto fue Summoner's Fantasy. La web está en vivo, el código está en GitHub. ¿Tienen preguntas?"

**Tips:**
- Pausa breve
- Sonreír
- Contacto visual
- QR code visible

---

## 🎯 CONSEJOS FINALES

### Antes de empezar:
- [ ] Respirá profundo (3 segundos inhalar, 3 exhalar)
- [ ] Tomá un sorbo de agua
- [ ] Verificá que el proyector funcione
- [ ] Tenés el clicker a mano (si hay)

### Durante:
- [ ] No apures (20-25 minutos es TIEMPO, no menos)
- [ ] Si te trabás, respirá y seguís
- [ ] Mirá a los profesores, no a la pantalla
- [ ] Usá las manos (gestos naturales)

### Para las preguntas:
- [ ] Escuchá toda la pregunta antes de responder
- [ ] Si no sabés: "Buena pregunta, no lo investigué a fondo, pero mi intuición es..."
- [ ] Si te corrigen: "Tenés razón, gracias" (no defender)

### Después:
- [ ] Agradecé
- [ ] Guardá la presentación
- [ ] Celebrá (¡terminaste!)

---

## 📊 TIMING

| Slide | Tiempo acumulado |
|-------|------------------|
| 1 | 0:30 |
| 2 | 1:00 |
| 3 | 2:00 |
| 4 | 3:00 |
| 5-8 | 8:00 |
| 9 | 9:00 |
| 10 | 9:30 |
| 11 | 10:30 |
| 12 | 11:30 |
| 13 | 12:00 |
| 14 | 13:00 |
| 15 | 14:00 |
| 16 | 15:00 |
| 17 | 16:00 |
| 18 | 17:00 |
| 19 | 18:00 |
| 20 | 19:00 |
| 21 | 20:00 |
| 22 | 20:30 |

**Buffer:** 4-5 minutos para preguntas o imprevistos

---

## 🚀 ¡VOS PODÉS!

Preparaste esto durante meses. Conocés el código mejor que nadie. Es TU proyecto.

**¡A romperla! 💪**
