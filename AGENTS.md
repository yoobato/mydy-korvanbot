# KoreaVancouverBot development rules

- This product's repository is https://github.com/yoobato/mydy-korvanbot.
- Work directly on `main`. Commit and push authorized changes to `origin/main`; do not create feature branches or PRs unless the user changes this instruction.
- Update README.md and relevant documentation whenever behavior, configuration, deployment, or operational status changes.
- Run meaningful tests and verify actual collection when changing the site integration. Report Telegram delivery as unverified unless a real message was sent and confirmed.
- Deploy this product to `yoobato-canada-lightsail`, `/opt/services/korvanbot`. Preserve CaLog, ChutChut, BabyLog, their data, Caddy, and shared networks.
- This outbound polling worker needs no domain or inbound ports. Keep its network separate, preserve its SQLite data, and keep resource limits on its container.
- Never commit bot tokens or runtime state. Local secrets live outside this workspace at `/Users/yoobato/YoobatoDev/secrets/consulate-alerts/telegram.env`; server secrets live at `/opt/secrets/korvanbot/telegram.env`.
