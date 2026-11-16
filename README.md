# Follow Poppy

Walking AR navigation for Android: Poppy, a fluffy little pet, walks ahead of you on a glowing 3D trail and leads you
to where you're going. Hebrew and English.

**Download:** [Follow-Poppy.apk](https://github.com/innomaster01-del/Follow-Poppy/releases/latest/download/Follow-Poppy.apk)

- Kotlin + Jetpack Compose, ARCore through SceneView (Filament)
- Mapbox walking directions and search; optional ARCore Geospatial (Street View VPS) for metre-level accuracy
- Repo secrets: `MAPBOX_TOKEN` (public Mapbox token), `GOOGLE_AR_KEY` (optional, Google Cloud key with the ARCore API)
- Every push to `main` builds the APK and publishes a release; `tools/3d/poppy` makes Poppy's 3D models
