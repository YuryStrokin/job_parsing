import os

# Telegram Bot Token (получить от @BotFather)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ID пользователя для получения дайджеста
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

# Путь к базе данных
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/vacancies.db")

# Время ежедневной рассылки (UTC)
DAILY_DIGEST_TIME = os.getenv("DAILY_DIGEST_TIME", "09:00")

# Минимальный скор релевантности для показа
MIN_RELEVANCE_SCORE = float(os.getenv("MIN_RELEVANCE_SCORE", "0.3"))

# API ID и Hash для Telegram Client (если нужно читать каналы)
TG_API_ID = os.getenv("TG_API_ID", "")
TG_API_HASH = os.getenv("TG_API_HASH", "")
