import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any
import json

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей и их настроек
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    resume_text TEXT,
                    resume_file_path TEXT,
                    target_roles TEXT,
                    filters TEXT,
                    channels TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица вакансий
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vacancies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT,
                    message_id INTEGER,
                    title TEXT,
                    company TEXT,
                    description TEXT,
                    salary TEXT,
                    location TEXT,
                    post_text TEXT,
                    link TEXT,
                    score REAL,
                    match_reasons TEXT,
                    risks TEXT,
                    published_date TIMESTAMP,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_sent BOOLEAN DEFAULT FALSE,
                    UNIQUE(channel_id, message_id)
                )
            """)
            
            # Индексы для ускорения поиска
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_vacancies_score ON vacancies(score DESC)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_vacancies_published ON vacancies(published_date DESC)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_vacancies_is_sent ON vacancies(is_sent)
            """)
            
            await db.commit()
    
    async def save_user_settings(self, user_id: int, **kwargs):
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, существует ли запись
            cursor = await db.execute(
                "SELECT id FROM user_settings WHERE user_id = ?", (user_id,)
            )
            exists = await cursor.fetchone()
            
            if exists:
                # Обновляем существующую запись
                set_clauses = []
                values = []
                for key, value in kwargs.items():
                    if isinstance(value, (list, dict)):
                        value = json.dumps(value)
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
                
                if set_clauses:
                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                    values.append(user_id)
                    query = f"UPDATE user_settings SET {', '.join(set_clauses)} WHERE user_id = ?"
                    await db.execute(query, values)
            else:
                # Создаем новую запись
                columns = ["user_id"]
                placeholders = ["?"]
                values = [user_id]
                
                for key, value in kwargs.items():
                    columns.append(key)
                    placeholders.append("?")
                    if isinstance(value, (list, dict)):
                        value = json.dumps(value)
                    values.append(value)
                
                query = f"INSERT INTO user_settings ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                await db.execute(query, values)
            
            await db.commit()
    
    async def get_user_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                result = dict(row)
                # Парсим JSON поля
                for field in ['target_roles', 'filters', 'channels']:
                    if result.get(field):
                        try:
                            result[field] = json.loads(result[field])
                        except json.JSONDecodeError:
                            result[field] = []
                return result
            return None
    
    async def save_vacancy(self, vacancy: Dict[str, Any]) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT OR IGNORE INTO vacancies 
                    (channel_id, message_id, title, company, description, salary, 
                     location, post_text, link, score, match_reasons, risks, published_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    vacancy.get('channel_id'),
                    vacancy.get('message_id'),
                    vacancy.get('title'),
                    vacancy.get('company'),
                    vacancy.get('description'),
                    vacancy.get('salary'),
                    vacancy.get('location'),
                    vacancy.get('post_text'),
                    vacancy.get('link'),
                    vacancy.get('score', 0),
                    json.dumps(vacancy.get('match_reasons', [])),
                    json.dumps(vacancy.get('risks', [])),
                    vacancy.get('published_date')
                ))
                await db.commit()
                return True
            except Exception as e:
                print(f"Error saving vacancy: {e}")
                return False
    
    async def get_unsent_vacancies(self, min_score: float = 0.0) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM vacancies 
                WHERE is_sent = FALSE AND score >= ?
                ORDER BY score DESC, published_date DESC
            """, (min_score,))
            rows = await cursor.fetchall()
            
            vacancies = []
            for row in rows:
                vacancy = dict(row)
                # Парсим JSON поля
                for field in ['match_reasons', 'risks']:
                    if vacancy.get(field):
                        try:
                            vacancy[field] = json.loads(vacancy[field])
                        except json.JSONDecodeError:
                            vacancy[field] = []
                vacancies.append(vacancy)
            
            return vacancies
    
    async def mark_vacancies_as_sent(self, vacancy_ids: List[int]):
        async with aiosqlite.connect(self.db_path) as db:
            placeholders = ','.join('?' * len(vacancy_ids))
            await db.execute(
                f"UPDATE vacancies SET is_sent = TRUE WHERE id IN ({placeholders})",
                vacancy_ids
            )
            await db.commit()
    
    async def get_all_vacancies_for_channel(self, channel_id: str) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM vacancies WHERE channel_id = ?
                ORDER BY published_date DESC
            """, (channel_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def check_vacancy_exists(self, channel_id: str, message_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id FROM vacancies WHERE channel_id = ? AND message_id = ?",
                (channel_id, message_id)
            )
            row = await cursor.fetchone()
            return row is not None
