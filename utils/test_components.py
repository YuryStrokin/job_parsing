import sys
sys.path.insert(0, '.')

from core.parser import VacancyParser, VacancyScorer

def test_parser():
    """Тестирование парсера вакансий"""
    parser = VacancyParser()
    
    # Тестовый пост с вакансией
    test_post = """
#вакансия #python

Вакансия: Senior Python Developer

Компания: TechCorp Inc.

Мы ищем опытного Python разработчика в нашу команду.

Требования:
- Опыт работы с Python 3+
- Знание Django, FastAPI
- Работа с PostgreSQL, Redis
- Docker, Kubernetes

Условия:
- Зарплата: от $4000 до $6000
- Удаленная работа (remote)
- Гибкий график

Контакты: @hr_techcorp
    """
    
    print("=== Тестирование парсера ===\n")
    
    # Проверяем, определяется ли как вакансия
    is_vacancy = parser.is_vacancy_post(test_post)
    print(f"Определено как вакансия: {is_vacancy}")
    
    # Извлекаем данные
    vacancy_data = parser.extract_vacancy_data(
        test_post, 
        channel_id="@job_channel", 
        message_id=123
    )
    
    if vacancy_data:
        print("\nИзвлеченные данные:")
        for key, value in vacancy_data.items():
            if key != 'post_text':  # Не выводим полный текст
                print(f"  {key}: {value}")
    
    return vacancy_data


def test_scorer():
    """Тестирование скоринга вакансий"""
    print("\n=== Тестирование скоринга ===\n")
    
    # Тестовое резюме
    resume_text = """
Senior Python Developer с опытом 5 лет.
Навыки: Python, Django, FastAPI, PostgreSQL, Redis, Docker, AWS.
Работал в продуктовых компаниях, опыт управления командой.
    """
    
    # Целевые роли
    target_roles = ["Python Developer", "Backend Engineer", "Tech Lead"]
    
    # Тестовая вакансия
    vacancy = {
        'title': 'Senior Python Developer',
        'company': 'TechCorp',
        'description': 'Требуется Python разработчик с опытом Django и FastAPI',
        'location': 'Remote, удаленно',
        'salary': '$5000 - $7000'
    }
    
    scorer = VacancyScorer(resume_text=resume_text, target_roles=target_roles)
    score, match_reasons, risks = scorer.calculate_score(vacancy)
    
    print(f"Вакансия: {vacancy['title']} @ {vacancy['company']}")
    print(f"Скор релевантности: {score} ({int(score * 100)}%)")
    print(f"\nПричины соответствия:")
    for reason in match_reasons:
        print(f"  ✅ {reason}")
    
    if risks:
        print(f"\nРиски/пробелы:")
        for risk in risks:
            print(f"  ⚠️ {risk}")
    
    return score, match_reasons, risks


def test_deduplication():
    """Тестирование дедупликации"""
    print("\n=== Тестирование дедупликации ===\n")
    
    from core.database import Database
    import asyncio
    
    async def run_test():
        db = Database("data/test_vacancies.db")
        await db.init()
        
        # Сохраняем тестовую вакансию
        vacancy1 = {
            'channel_id': '@job_channel',
            'message_id': 100,
            'title': 'Python Developer',
            'company': 'Test Corp',
            'description': 'Test description',
            'salary': 'Not specified',
            'location': 'Remote',
            'post_text': 'Test post',
            'link': 'https://t.me/job_channel/100',
            'score': 0.75,
            'match_reasons': ['Test reason'],
            'risks': [],
            'published_date': '2024-01-01T00:00:00'
        }
        
        saved = await db.save_vacancy(vacancy1)
        print(f"Вакансия сохранена: {saved}")
        
        # Пытаемся сохранить дубликат
        vacancy2 = vacancy1.copy()
        saved_duplicate = await db.save_vacancy(vacancy2)
        print(f"Дубликат сохранен (должен быть False): {saved_duplicate}")
        
        # Проверяем существование
        exists = await db.check_vacancy_exists('@job_channel', 100)
        print(f"Вакансия существует в БД: {exists}")
        
        return saved, saved_duplicate, exists
    
    return asyncio.run(run_test())


def main():
    """Запуск всех тестов"""
    print("=" * 50)
    print("ТЕСТИРОВАНИЕ КОМПОНЕНТОВ БОТА")
    print("=" * 50)
    
    # Тест парсера
    vacancy_data = test_parser()
    
    # Тест скоринга
    score, reasons, risks = test_scorer()
    
    # Тест дедупликации
    test_deduplication()
    
    print("\n" + "=" * 50)
    print("ТЕСТЫ ЗАВЕРШЕНЫ")
    print("=" * 50)


if __name__ == '__main__':
    main()
