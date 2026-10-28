# MediaDownloader maintenance

- Read README.md, BUILD.md and ACTUALIZACIONES.md before changing releases.
- Source of truth is main. Preserve the existing Qt UI, Windows Shell identity, settings/session, downloads and transactional updater.
- Bump mediadownloader/__init__.py for a new delivered change and commit to main. Actions owns tags, releases, full ZIP, incremental ZIP and latest.json. Do not ask the user to create GitHub commits/tags/releases.
- Never overwrite an immutable complete release or rebuild the reference baseline approximately. Use exact published bytes.
- Give existing users the incremental update channel or patch, not the full installer. A new installation may use the separate full package.
- Inspect final Actions status, published assets and SHA-256 before saying an update is ready. Windows binaries require Windows tests; Linux smoke tests are insufficient.
- Recovery: workflow_dispatch on main with release_tag uses the current pipeline/tools and sources from that tag. Do not rerun the obsolete tag workflow as the repair strategy.
- Run source privacy audit and meaningful tests. Never commit cookies, credentials, preferences, downloads, private paths or working files.
- Do not claim the user's PC acceptance passed without their confirmation of online download/apply/restart/data preservation/latest-version check.
