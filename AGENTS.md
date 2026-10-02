# Development

- Work directly on `main` and commit and push changes to `origin/main`.
- Update documentation with changes. Keep README focused on behavior and monitored boards.
- Do not include personal machine paths, secrets, or runtime data in tracked files. Provide configuration examples in `.env.example`.
- Retain meaningful tests for collection, deduplication, and retry behavior.
- Deploy to the existing Lightsail worker without affecting other services. Preserve the external secrets file and state database.
