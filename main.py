import os
import staypresent

staypresent.web.json({"status": "running"})

staypresent.cron(
    os.getenv("APP_URL", "https://tu-app-name.onrender.com"),
    interval=240,
)

staypresent.run(
    "bot.py",
    port=int(os.getenv("PORT", 8080)),
    restart_on_crash=True,
    max_restarts=5,
    restart_delay=2.0,
)
