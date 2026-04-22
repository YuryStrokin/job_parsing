import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

class VacancyParser:
    """Парсер вакансий из текстов постов Telegram"""
    
    # Ключевые слова для определения вакансии
    VACANCY_KEYWORDS = [
        'вакансия', 'требуется', 'ищем', 'ищу', 'работу', 'работа', 
        'позиция', 'должность', 'сотрудник', 'специалист', 'разработчик',
        'developer', 'engineer', 'manager', 'designer', 'analyst',
        'hiring', 'job', 'position', 'opportunity'
    ]
    
    # Паттерны для извлечения данных
    PATTERNS = {
        'title': [
            r'(?:вакансия|позиция|должность)[:\s]+([^\n]+)',
            r'([А-Яа-яA-Za-z]+\s+[А-Яа-яA-Za-z\s]+(?:Developer|Engineer|Manager|Designer|Analyst))',
            r'^([А-Я][^\n]*(?:Developer|Engineer|Manager|Designer|Lead|Senior|Junior)[^\n]*)',
        ],
        'company': [
            r'(?:компания|employer|company)[:\s]+([^\n]+)',
            r'[@#]?(\w+(?:\s+\w+)*(?:Inc|LLC|Ltd|ООО|АО|ЗАО))',
            r'в\s+компанию\s+([^\n]+)',
        ],
        'salary': [
            r'(?:зарплата|salary|оплата|оклад|доход)[:\s]+([^\n]+)',
            r'(\$|€|₽|USD|EUR|RUB)\s*[\d\s,-]+(?:\s*(?:тыс|млн|k|m|K|M))?',
            r'от\s*([\d\s,]+)\s*(?:до\s*([\d\s,]+))?\s*(?:тыс\.?|руб\.?|\$|€|₽)?',
        ],
        'location': [
            r'(?:город|location|локация|место|office)[:\s]+([^\n]+)',
            r'(Москва|Санкт-Петербург|Киев|Минск|Алматы|удаленно|remote|hybrid)',
        ],
    }
    
    def __init__(self):
        self.compiled_patterns = {}
        for key, patterns in self.PATTERNS.items():
            self.compiled_patterns[key] = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns]
    
    def is_vacancy_post(self, text: str) -> bool:
        """Проверяет, является ли пост вакансией"""
        text_lower = text.lower()
        
        # Проверяем наличие ключевых слов
        keyword_count = sum(1 for kw in self.VACANCY_KEYWORDS if kw in text_lower)
        
        # Проверяем наличие паттернов вакансии
        has_title_pattern = any(
            pattern.search(text) 
            for pattern in self.compiled_patterns['title']
        )
        
        # Вакансия если есть хотя бы 2 ключевых слова или заголовок позиции
        return keyword_count >= 2 or has_title_pattern
    
    def extract_vacancy_data(self, text: str, channel_id: str, message_id: int) -> Optional[Dict[str, Any]]:
        """Извлекает данные о вакансии из текста поста"""
        if not self.is_vacancy_post(text):
            return None
        
        vacancy = {
            'channel_id': channel_id,
            'message_id': message_id,
            'post_text': text[:4000],  # Ограничиваем длину
            'published_date': datetime.utcnow().isoformat(),
        }
        
        # Извлекаем заголовок
        vacancy['title'] = self._extract_field(text, 'title') or self._extract_title_fallback(text)
        
        # Извлекаем компанию
        vacancy['company'] = self._extract_field(text, 'company') or 'Не указана'
        
        # Извлекаем зарплату
        vacancy['salary'] = self._extract_field(text, 'salary') or 'Не указана'
        
        # Извлекаем локацию
        vacancy['location'] = self._extract_field(text, 'location') or 'Не указано'
        
        # Описание - очищенный текст без заголовков и метаданных
        vacancy['description'] = self._clean_description(text)
        
        # Ссылка формируется из channel_id и message_id
        if channel_id.startswith('@'):
            vacancy['link'] = f"https://t.me/{channel_id[1:]}/{message_id}"
        else:
            vacancy['link'] = f"https://t.me/c/{channel_id}/{message_id}"
        
        return vacancy
    
    def _extract_field(self, text: str, field_type: str) -> Optional[str]:
        """Извлекает поле по типу используя паттерны"""
        for pattern in self.compiled_patterns[field_type]:
            match = pattern.search(text)
            if match:
                result = match.group(1) if match.lastindex else match.group(0)
                return result.strip()[:200]
        return None
    
    def _extract_title_fallback(self, text: str) -> Optional[str]:
        """Fallback метод для извлечения заголовка"""
        lines = text.split('\n')
        for line in lines[:5]:  # Проверяем первые 5 строк
            line = line.strip()
            if len(line) > 10 and len(line) < 100:
                # Ищем строку с названием позиции
                if any(kw in line for kw in ['Developer', 'Engineer', 'Manager', 'Designer', 'Lead', 'Senior', 'Junior']):
                    return line
        # Возвращаем первую непустую строку
        for line in lines[:3]:
            line = line.strip()
            if line and len(line) > 5:
                return line[:80]
        return "Вакансия"
    
    def _clean_description(self, text: str) -> str:
        """Очищает текст от метаданных и оставляет описание"""
        lines = text.split('\n')
        clean_lines = []
        
        skip_keywords = ['#', '@', 'http', 'www', 't.me', 'telegram.me']
        
        for line in lines:
            line_stripped = line.strip()
            
            # Пропускаем хештеги и упоминания
            if any(line_stripped.startswith(kw) for kw in skip_keywords):
                continue
            
            # Пропускаем очень короткие строки (менее 3 символов)
            if len(line_stripped) < 3:
                continue
            
            clean_lines.append(line_stripped)
        
        return '\n'.join(clean_lines[:50])  # Ограничиваем количество строк


class VacancyScorer:
    """Скоринг релевантности вакансий на основе резюме и целевых ролей"""
    
    def __init__(self, resume_text: str = "", target_roles: List[str] = None):
        self.resume_text = resume_text.lower()
        self.target_roles = [r.lower() for r in (target_roles or [])]
        
        # Ключевые навыки для анализа (можно расширить)
        self.skill_keywords = [
            'python', 'java', 'javascript', 'typescript', 'go', 'rust', 'c++', 'c#',
            'react', 'vue', 'angular', 'django', 'flask', 'fastapi', 'spring',
            'sql', 'postgresql', 'mysql', 'mongodb', 'redis',
            'docker', 'kubernetes', 'aws', 'gcp', 'azure',
            'git', 'ci/cd', 'agile', 'scrum',
            'english', 'русский', 'українська'
        ]
    
    def calculate_score(self, vacancy: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """
        Вычисляет скор релевантности вакансии
        
        Returns:
            score: float от 0 до 1
            match_reasons: список причин соответствия
            risks: список рисков/пробелов
        """
        score = 0.0
        match_reasons = []
        risks = []
        
        vacancy_text = (
            f"{vacancy.get('title', '')} {vacancy.get('company', '')} "
            f"{vacancy.get('description', '')} {vacancy.get('location', '')}"
        ).lower()
        
        # 1. Проверка соответствия целевым ролям (максимум 0.4)
        role_score = self._check_role_match(vacancy, vacancy_text)
        score += role_score['score']
        match_reasons.extend(role_score['reasons'])
        risks.extend(role_score['risks'])
        
        # 2. Проверка навыков из резюме (максимум 0.3)
        skill_score = self._check_skill_match(vacancy_text)
        score += skill_score['score']
        match_reasons.extend(skill_score['reasons'])
        risks.extend(skill_score['risks'])
        
        # 3. Проверка локаций и формата работы (максимум 0.15)
        location_score = self._check_location_match(vacancy)
        score += location_score['score']
        match_reasons.extend(location_score['reasons'])
        
        # 4. Проверка зарплаты если указана (максимум 0.15)
        salary_score = self._check_salary_match(vacancy)
        score += salary_score['score']
        match_reasons.extend(salary_score['reasons'])
        
        # Нормализуем скор до 0-1
        score = min(1.0, max(0.0, score))
        
        return round(score, 2), match_reasons, risks
    
    def _check_role_match(self, vacancy: Dict[str, Any], vacancy_text: str) -> Dict[str, Any]:
        """Проверяет соответствие целевым ролям"""
        result = {'score': 0.0, 'reasons': [], 'risks': []}
        
        title = vacancy.get('title', '').lower()
        
        for role in self.target_roles:
            if role in title or role in vacancy_text:
                result['score'] += 0.4
                result['reasons'].append(f"Соответствует целевой роли: {role}")
                break
        else:
            # Если роль не найдена, проверяем на частичное совпадение
            for role in self.target_roles:
                role_parts = role.split()
                matches = sum(1 for part in role_parts if len(part) > 3 and part in vacancy_text)
                if matches >= len(role_parts) * 0.5:
                    result['score'] += 0.2
                    result['reasons'].append(f"Частично соответствует роли: {role}")
                    break
            else:
                result['risks'].append("Роль не соответствует целевым позициям")
        
        return result
    
    def _check_skill_match(self, vacancy_text: str) -> Dict[str, Any]:
        """Проверяет соответствие навыков из резюме"""
        result = {'score': 0.0, 'reasons': [], 'risks': []}
        
        if not self.resume_text:
            return result
        
        matched_skills = []
        missing_skills = []
        
        for skill in self.skill_keywords:
            if skill in self.resume_text and skill in vacancy_text:
                matched_skills.append(skill)
        
        # Если найдено более 3 общих навыков, добавляем скор
        if len(matched_skills) >= 3:
            result['score'] = 0.3
            result['reasons'].append(f"Найдены общие навыки: {', '.join(matched_skills[:5])}")
        elif len(matched_skills) > 0:
            result['score'] = 0.15
            result['reasons'].append(f"Есть совпадения по навыкам: {', '.join(matched_skills)}")
        
        return result
    
    def _check_location_match(self, vacancy: Dict[str, Any]) -> Dict[str, Any]:
        """Проверяет локацию и формат работы"""
        result = {'score': 0.0, 'reasons': [], 'risks': []}
        
        location = vacancy.get('location', '').lower()
        
        # Предпочтение удаленке
        if 'remote' in location or 'удаленно' in location:
            result['score'] = 0.15
            result['reasons'].append("Удаленная работа")
        elif 'hybrid' in location or 'гибрид' in location:
            result['score'] = 0.1
            result['reasons'].append("Гибридный формат")
        else:
            result['score'] = 0.05
            result['reasons'].append(f"Локация: {vacancy.get('location', 'Не указана')}")
        
        return result
    
    def _check_salary_match(self, vacancy: Dict[str, Any]) -> Dict[str, Any]:
        """Проверяет зарплату"""
        result = {'score': 0.0, 'reasons': [], 'risks': []}
        
        salary = vacancy.get('salary', '')
        
        if salary and 'не указана' not in salary.lower():
            result['score'] = 0.15
            result['reasons'].append(f"Зарплата: {salary}")
        else:
            result['risks'].append("Зарплата не указана")
        
        return result
