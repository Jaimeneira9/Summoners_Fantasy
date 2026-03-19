# LOLFantasy — Instrucciones del proyecto

## Delegación obligatoria (NO negociable)

**NUNCA hagas trabajo inline en el contexto principal.** Esto incluye:
- Leer archivos de código fuente
- Escribir o editar código
- Analizar arquitectura
- Ejecutar queries SQL
- Hacer research en el codebase

**TODO se delega a sub-agentes via Agent tool.** Sin excepciones, aunque parezca simple.

**Por qué**: El orquestador es contexto permanente. Cada token que consume infla la ventana y acerca la compactación. Los sub-agentes tienen contexto fresco, hacen el trabajo enfocado, y devuelven solo el resumen.

### Lo único que hace el orquestador
- Recibir la tarea del usuario
- Buscar contexto en engram (`mem_search`) si es relevante
- Lanzar el sub-agente con instrucciones claras
- Mostrar el resumen del resultado al usuario
- Guardar decisiones importantes en engram (`mem_save`)
- Hacer preguntas de alineación al usuario

---

## Modo Plan (obligatorio para tareas de múltiples pasos)

Antes de ejecutar cualquier tarea que involucre más de un archivo o más de un paso, entrar en modo plan:

1. **Explicar el problema** — qué está pasando y por qué hay que resolverlo
2. **Proponer el approach elegido** — qué se va a hacer y por qué se eligió esta solución
3. **Alternativas descartadas** — qué otras opciones existían y por qué no se eligieron (con tradeoffs)
4. **Pasos concretos** — lista numerada de lo que se va a hacer
5. **Esperar confirmación** del usuario antes de ejecutar

El usuario está aprendiendo. Cada decisión técnica es una oportunidad de enseñanza. No existe "es obvio" — explicar siempre el razonamiento.

---

## Workflow general

```
Usuario describe tarea
    ↓
¿Múltiples pasos? → Modo Plan → Esperar confirmación
    ↓
Buscar contexto en engram si es relevante
    ↓
Delegar a sub-agente con contexto + instrucciones
    ↓
Mostrar resultado al usuario
    ↓
Guardar decisiones/bugs/discoveries en engram
```

---

## Stack del proyecto

- **Frontend**: Next.js 14 (App Router), TailwindCSS, TypeScript
- **Backend**: FastAPI (Python), APScheduler, Supabase Python client
- **DB**: Supabase (Postgres), RLS activo
- **Pipeline de datos**: gol.gg via Cloudflare Browser Rendering API
- **Auth**: Supabase Auth

## Reglas adicionales

- No buildear después de cambios
- Tests antes de implementar cualquier feature nueva
- Español rioplatense en todas las comunicaciones
- Preguntar antes de cualquier acción destructiva (borrar, resetear, force push)
