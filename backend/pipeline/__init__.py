"""
Pipeline de ingestión de datos — Summoner's Fantasy.

Este paquete contiene los módulos responsables de obtener datos externos
de partidas LEC, calcular puntos de fantasy y persistirlos en Supabase.

Flujo general del pipeline:
  1. scheduler.py   → APScheduler dispara los jobs periódicos
  2. leaguepedia.py → detecta partidas LEC terminadas (Cargo API de la wiki)
  3. gol_gg.py      → scrapea stats por jugador y por partida desde gol.gg
  4. series_ingest.py → orquesta el proceso completo: agrupa games en series,
                        calcula puntos y actualiza precios de jugadores
  5. oracles_elixir.py → fuente alternativa de stats via CSV (pipeline legacy)
  6. ingest.py      → helpers de persistencia usados por el pipeline legacy

Módulos expuestos públicamente:
  - pipeline.series_ingest.run_series_ingest  (función principal del pipeline activo)
  - pipeline.scheduler                         (worker standalone con APScheduler)
"""
