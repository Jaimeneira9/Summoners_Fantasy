# Changelog

## [1.1.0](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/compare/v1.0.0...v1.1.0) (2026-03-24)


### Features

* precios dinámicos, cláusulas de rescisión y explorador de jugadores ([5e1ac26](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/5e1ac26638c76332840a66209c41d496c7135260))
* sistema de precios dinámicos, cláusulas de rescisión y explorador de jugadores ([8ac7835](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/8ac78357d515db85f8197287cef11ee0ab623796))


### Bug Fixes

* actualizar tests de scoring con nuevos pesos del engine ([06aa7d6](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/06aa7d6f8c034e05e55953888f7a91e67f98e309))
* corregir imports rotos tras refactor de pricing y PlayerStatsModal ([39f44e3](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/39f44e36033be84448814f12e780a792c3e356f1))
* operaciones de presupuesto atómicas via RPC para prevenir race conditions ([e46326c](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/e46326c93ae9c9337dbe1db623ab9607fdc3591f))
* prevenir IDOR cross-liga en activate_clause ([72f2d5f](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/72f2d5f19ea1bd2694bae2def4ac66276c7af0ef))

## 1.0.0 (2026-03-23)


### Features

* add agent skills (supabase, vercel, fastapi, web-design) ([05e8709](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/05e8709ef788ca52fb045e39a6b837703eb84604))
* **db:** migraciones para soporte de series y stats extendidas ([5c5f3a5](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/5c5f3a5527a57f57df194214a0c750f9b6b699c0))
* initial commit — LOLFantasy LEC fantasy platform ([52284c4](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/52284c47b88b6c3b4530bfa5d374deec646301e8))
* pipeline gol.gg, UI light theme y schema de series ([867cfea](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/867cfea3499520d7e666ac1272c741b9931d2fdf))
* **pipeline:** implementar scraper gol.gg y orquestador de series ([5a48e32](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/5a48e325f9e98de8575521f96055c654ceb08363))
* sistema de perfiles, mejoras UI y fixes ([01927cf](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/01927cfcc7c7cdfc792837e4f9968610bc7d8984))
* sistema de perfiles, mejoras UI y fixes de stats ([a29ab19](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/a29ab19422411fe7cd25d5792d0b89b8d394ccc2))
* UI redesign Paper B Premium + backend improvements + CI ([e57ed7d](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/e57ed7dd69a7b99e0a6cf8cd43cbe508e53fceea))
* UI redesign Paper B Premium + backend improvements + CI ([2b93d7e](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/2b93d7e78f8ff6c69c07f464369b991c1063d143))
* **ui:** layout por liga con tabs y loading states ([4d5f8e5](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/4d5f8e5654355d4cbe72e28de28efba89243455c))
* **ui:** migrar de dark theme (neon azul) a light theme cream/púrpura/gold ([baf66e2](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/baf66e2e92ae3ff95bff22d12970bfeef56034f2))
* **ui:** nuevos componentes y actualización de existentes con light theme ([11b19cc](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/11b19cc51f985c8eccfcc909421eb25e928bdb5e))


### Bug Fixes

* agregar tabla profiles a los tipos de Supabase ([3fabef1](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/3fabef1b326720a966831e1d725e4b4306347378))
* **backend:** CORS desde env vars, fixes en scoring engine y routers ([7fc5f52](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/7fc5f5206483b9cd0a55caa98d0df0773218339d))
* corregir fallos de CI (ESLint unused vars + tests backend) ([6efc318](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/6efc318832e98e2235ed5a2c955336a5caad42fa))
* eliminar variable USERNAME_REGEX no utilizada en onboarding ([d714301](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/d71430101bc69f66e12375edb28d58e0c5e25843))
* resolver conflicto release-please workflow (master → main) ([c892e23](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/c892e23d542e66f413cdcf8e5d7051cb65145656))
* type error initialTab en market page ([46dacbb](https://github.com/Jaimeneira9/Fantasy-League-of-Legends/commit/46dacbbb11f804e4725d48c27e92cfe36fd6f6c4))
