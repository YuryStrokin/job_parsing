import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import asyncio
from datetime import datetime
from typing import List, Dict, Any

from core.database import Database
from core.parser import VacancyParser, VacancyScorer
from config import DATABASE_PATH, MIN_RELEVANCE_SCORE


class JobBot:
    """Telegram бот для сбора и анализа вакансий"""
    
    def __init__(self, token: str):
        self.token = token
        self.db = Database(DATABASE_PATH)
        self.parser = VacancyParser()
        self.application = None
        
        # Хранилище состояний пользователей
        self.user_states: Dict[int, Dict[str, Any]] = {}
    
    async def init(self):
        """Инициализация бота и базы данных"""
        await self.db.init()
        
        # Создаем приложение
        self.application = Application.builder().token(self.token).build()
        
        # Регистрируем обработчики
        self._register_handlers()
    
    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        # Команды
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("resume", self.cmd_resume))
        self.application.add_handler(CommandHandler("channels", self.cmd_channels))
        self.application.add_handler(CommandHandler("roles", self.cmd_roles))
        self.application.add_handler(CommandHandler("filters", self.cmd_filters))
        self.application.add_handler(CommandHandler("digest", self.cmd_digest))
        self.application.add_handler(CommandHandler("settings", self.cmd_settings))
        
        # Обработка файлов (резюме)
        self.application.add_handler(MessageHandler(
            filters.Document.ALL, 
            self.handle_document
        ))
        
        # Обработка текста
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_text
        ))
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start - приветствие"""
        user_id = update.effective_user.id
        
        welcome_text = """
👋 Привет! Я бот для поиска релевантных вакансий.

Я умею:
• Анализировать вакансии из Telegram-каналов
• Сравнивать их с твоим резюме
• Присылать персонализированный дайджест

Для начала настройки отправь:
/resume - загрузить резюме
/channels - добавить каналы с вакансиями
/roles - указать целевые роли
/digest - получить дайджест вручную
        """
        
        await update.message.reply_text(welcome_text)
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help - справка"""
        help_text = """
📚 Справка по командам:

/resume - Загрузить резюме (файлом или текстом)
/channels - Добавить/удалить Telegram-каналы
/roles - Указать целевые должности
/filters - Настроить фильтры вакансий
/digest - Получить дайджест вручную
/settings - Показать текущие настройки

Ежедневный дайджест приходит автоматически в настроенное время.
        """
        
        await update.message.reply_text(help_text)
    
    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /resume - загрузка резюме"""
        user_id = update.effective_user.id
        
        instructions = """
📄 Загрузка резюме

Отправь мне резюме одним из способов:
1. Файлом (PDF, DOC, DOCX, TXT)
2. Текстовым сообщением

После загрузки я проанализирую его и буду использовать для подбора вакансий.
        """
        
        await update.message.reply_text(instructions)
        self.user_states[user_id] = {'state': 'waiting_resume'}
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка загруженного файла резюме"""
        user_id = update.effective_user.id
        document = update.message.document
        
        # Проверяем тип файла
        allowed_types = ['application/pdf', 'application/msword', 
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'text/plain']
        
        if document.mime_type not in allowed_types:
            await update.message.reply_text(
                "❌ Неверный формат файла. Поддерживаются: PDF, DOC, DOCX, TXT"
            )
            return
        
        # Скачиваем файл
        file = await context.bot.get_file(document.file_id)
        file_path = f"data/resumes/{user_id}_{document.file_name}"
        
        import os
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        await file.download_to_drive(file_path)
        
        # Сохраняем путь к файлу в БД
        await self.db.save_user_settings(user_id, resume_file_path=file_path)
        
        # Читаем текст из файла (упрощенно - для TXT)
        resume_text = ""
        if document.mime_type == 'text/plain':
            with open(file_path, 'r', encoding='utf-8') as f:
                resume_text = f.read()
            await self.db.save_user_settings(user_id, resume_text=resume_text)
        
        await update.message.reply_text(
            f"✅ Резюме загружено!\nФайл: {document.file_name}\n\n"
            f"Теперь укажи целевые роли командой /roles"
        )
        
        # Очищаем состояние
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # Проверяем состояние пользователя
        state = self.user_states.get(user_id, {})
        
        if state.get('state') == 'waiting_resume':
            # Пользователь отправил резюме текстом
            await self.db.save_user_settings(user_id, resume_text=text)
            
            await update.message.reply_text(
                "✅ Резюме сохранено!\n\n"
                "Теперь укажи целевые роли командой /roles"
            )
            del self.user_states[user_id]
        
        elif state.get('state') == 'waiting_roles':
            # Пользователь указал роли
            roles = [r.strip() for r in text.split(',')]
            await self.db.save_user_settings(user_id, target_roles=roles)
            
            await update.message.reply_text(
                f"✅ Целевые роли сохранены: {', '.join(roles)}\n\n"
                "Теперь добавь каналы с вакансиями командой /channels"
            )
            del self.user_states[user_id]
        
        elif state.get('state') == 'waiting_channels':
            # Пользователь добавил каналы
            channels = [ch.strip() for ch in text.split(',')]
            
            # Получаем текущие каналы и добавляем новые
            settings = await self.db.get_user_settings(user_id)
            existing_channels = settings.get('channels', []) if settings else []
            
            all_channels = list(set(existing_channels + channels))
            await self.db.save_user_settings(user_id, channels=all_channels)
            
            await update.message.reply_text(
                f"✅ Каналы добавлены: {', '.join(channels)}\n\n"
                "Всего каналов: {}. Теперь бот будет собирать вакансии.".format(len(all_channels))
            )
            del self.user_states[user_id]
        
        elif state.get('state') == 'waiting_filters':
            # Пользователь настроил фильтры
            # Парсим фильтры (формат: key=value, key=value)
            filters_dict = {}
            for item in text.split(','):
                if '=' in item:
                    key, value = item.split('=', 1)
                    filters_dict[key.strip()] = value.strip()
            
            await self.db.save_user_settings(user_id, filters=filters_dict)
            
            await update.message.reply_text("✅ Фильтры сохранены!")
            del self.user_states[user_id]
    
    async def cmd_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /channels - управление каналами"""
        user_id = update.effective_user.id
        
        settings = await self.db.get_user_settings(user_id)
        channels = settings.get('channels', []) if settings else []
        
        if channels:
            channels_list = '\n'.join(f"• {ch}" for ch in channels)
            text = f"📺 Ваши каналы:\n{channels_list}\n\n"
        else:
            text = "📺 У вас пока нет добавленных каналов.\n\n"
        
        text += """
Отправьте список каналов через запятую:
@channel1, @channel2, channel3

Или напишите названия каналов, которые вы хотите отслеживать.
        """
        
        await update.message.reply_text(text)
        self.user_states[user_id] = {'state': 'waiting_channels'}
    
    async def cmd_roles(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /roles - управление целевыми ролями"""
        user_id = update.effective_user.id
        
        settings = await self.db.get_user_settings(user_id)
        roles = settings.get('target_roles', []) if settings else []
        
        if roles:
            roles_list = '\n'.join(f"• {r}" for r in roles)
            text = f"🎯 Ваши целевые роли:\n{roles_list}\n\n"
        else:
            text = "🎯 У вас пока нет указанных ролей.\n\n"
        
        text += """
Отправьте список желаемых должностей через запятую:
Python Developer, Backend Engineer, Tech Lead

Это поможет мне лучше подбирать вакансии.
        """
        
        await update.message.reply_text(text)
        self.user_states[user_id] = {'state': 'waiting_roles'}
    
    async def cmd_filters(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /filters - настройка фильтров"""
        user_id = update.effective_user.id
        
        settings = await self.db.get_user_settings(user_id)
        filters = settings.get('filters', {}) if settings else {}
        
        text = "🔧 Текущие фильтры:\n"
        if filters:
            for key, value in filters.items():
                text += f"• {key}: {value}\n"
        else:
            text += "Нет активных фильтров\n"
        
        text += """

Отправьте фильтры в формате: ключ=значение
Пример: min_salary=5000, location=remote, exclude_words=стажер
        """
        
        await update.message.reply_text(text)
        self.user_states[user_id] = {'state': 'waiting_filters'}
    
    async def cmd_digest(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /digest - ручной запуск дайджеста"""
        user_id = update.effective_user.id
        
        await update.message.reply_text("⏳ Формирую дайджест...")
        
        # Получаем настройки пользователя
        settings = await self.db.get_user_settings(user_id)
        
        if not settings:
            await update.message.reply_text(
                "❌ Сначала настройте бота:\n"
                "1. /resume - загрузите резюме\n"
                "2. /roles - укажите целевые роли\n"
                "3. /channels - добавьте каналы"
            )
            return
        
        resume_text = settings.get('resume_text', '')
        target_roles = settings.get('target_roles', [])
        
        # Получаем несохраненные вакансии
        vacancies = await self.db.get_unsent_vacancies(min_score=MIN_RELEVANCE_SCORE)
        
        if not vacancies:
            await update.message.reply_text(
                "📭 Пока нет новых релевантных вакансий.\n"
                "Проверьте позже или добавьте больше каналов."
            )
            return
        
        # Формируем дайджест
        scorer = VacancyScorer(resume_text=resume_text, target_roles=target_roles)
        
        digest_text = f"📊 Дайджест вакансий ({len(vacancies)})\n\n"
        
        for i, vacancy in enumerate(vacancies[:10], 1):  # Максимум 10 вакансий
            # Пересчитываем скор для актуальности
            score, match_reasons, risks = scorer.calculate_score(vacancy)
            
            digest_text += f"""
{i}. **{vacancy.get('title', 'Вакансия')}** @{vacancy.get('company', '')}
   💰 {vacancy.get('salary', 'Не указана')}
   📍 {vacancy.get('location', 'Не указано')}
   ⭐ Релевантность: {int(score * 100)}%
   
   ✅ Почему подходит:
   {chr(10).join('   • ' + r for r in match_reasons[:3])}
   
   ⚠️ Риски:
   {chr(10).join('   • ' + r for r in risks[:2]) if risks else '   • Нет явных рисков'}
   
   🔗 {vacancy.get('link', '')}
---
"""
        
        # Отправляем дайджест
        await update.message.reply_text(digest_text, parse_mode='Markdown')
        
        # Помечаем вакансии как отправленные
        if vacancies:
            await self.db.mark_vacancies_as_sent([v['id'] for v in vacancies])
        
        await update.message.reply_text("✅ Дайджест отправлен!")
    
    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /settings - показать настройки"""
        user_id = update.effective_user.id
        
        settings = await self.db.get_user_settings(user_id)
        
        if not settings:
            await update.message.reply_text("❌ У вас пока нет настроек.")
            return
        
        text = "⚙️ Ваши настройки:\n\n"
        
        if settings.get('resume_text') or settings.get('resume_file_path'):
            text += "📄 Резюме: ✅ Загружено\n"
        else:
            text += "📄 Резюме: ❌ Не загружено\n"
        
        roles = settings.get('target_roles', [])
        text += f"🎯 Роли: {', '.join(roles) if roles else 'Не указаны'}\n"
        
        channels = settings.get('channels', [])
        text += f"📺 Каналы: {len(channels)} шт.\n"
        
        filters = settings.get('filters', {})
        if filters:
            text += f"🔧 Фильтры: {filters}\n"
        
        await update.message.reply_text(text)
    
    async def send_daily_digest(self, context: ContextTypes.DEFAULT_TYPE):
        """Ежедневная рассылка дайджеста"""
        # Получаем всех пользователей с настройками
        # В MVP версии просто проверяем ADMIN_USER_ID
        
        user_id = context.job.data.get('user_id', None) if context.job else None
        
        if not user_id:
            return
        
        settings = await self.db.get_user_settings(user_id)
        
        if not settings:
            return
        
        resume_text = settings.get('resume_text', '')
        target_roles = settings.get('target_roles', [])
        
        # Получаем несохраненные вакансии
        vacancies = await self.db.get_unsent_vacancies(min_score=MIN_RELEVANCE_SCORE)
        
        if not vacancies:
            return
        
        # Формируем дайджест
        scorer = VacancyScorer(resume_text=resume_text, target_roles=target_roles)
        
        digest_text = f"🌅 Утренний дайджест вакансий ({len(vacancies)})\n\n"
        
        for i, vacancy in enumerate(vacancies[:10], 1):
            score, match_reasons, risks = scorer.calculate_score(vacancy)
            
            digest_text += f"""
{i}. **{vacancy.get('title', 'Вакансия')}**
   Компания: {vacancy.get('company', '')}
   Зарплата: {vacancy.get('salary', 'Не указана')}
   Локация: {vacancy.get('location', 'Не указано')}
   ⭐ Релевантность: {int(score * 100)}%
   
   ✅ Подходит потому что:
   {chr(10).join('   • ' + r for r in match_reasons[:3])}
   
   🔗 {vacancy.get('link', '')}
---
"""
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=digest_text,
                parse_mode='Markdown'
            )
            
            # Помечаем как отправленные
            await self.db.mark_vacancies_as_sent([v['id'] for v in vacancies])
            
        except Exception as e:
            print(f"Error sending daily digest: {e}")
    
    async def collect_vacancies_from_channels(self):
        """Сбор вакансий из каналов (требует Telegram Client)"""
        # В MVP версии эта функция будет заглушкой
        # Для полноценной работы нужен Telethon или Pyrogram
        pass
    
    async def run(self):
        """Запуск бота"""
        await self.init()
        
        # Добавляем ежедневную задачу
        if self.application.job_queue:
            self.application.job_queue.run_daily(
                self.send_daily_digest,
                time=datetime.strptime("09:00", "%H:%M").time(),
                data={'user_id': 0},  # Будет заменено на реальный user_id
                name='daily_digest'
            )
        
        print("Бот запущен...")
        # Запускаем polling с правильной инициализацией
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        # Держим бота запущенным
        while True:
            await asyncio.sleep(1)


async def main():
    from config import TELEGRAM_BOT_TOKEN
    
    if not TELEGRAM_BOT_TOKEN:
        print("❌Ошибка: TELEGRAM_BOT_TOKEN не установлен!")
        print("Получите токен от @BotFather и установите переменную окружения")
        return
    
    bot = JobBot(TELEGRAM_BOT_TOKEN)
    await bot.run()


if __name__ == '__main__':
    asyncio.run(main())
