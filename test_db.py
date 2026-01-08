"""
Простые тесты для проверки работы базы данных.
"""

import os
import sys
from db import Database


def test_database():
    """Тестирование работы с базой данных."""
    print("=== Тестирование базы данных ===\n")
    
    # Используем тестовую БД
    test_db_path = "test_chatlist.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    db = Database(test_db_path)
    
    try:
        # Тест 1: Создание промта
        print("1. Тест создания промта...")
        prompt_id = db.add_prompt("Тестовый промт", "тест, проверка")
        assert prompt_id > 0, "Промт не создан"
        print(f"   ✓ Промт создан с ID: {prompt_id}")
        
        # Тест 2: Получение промта
        print("2. Тест получения промта...")
        prompt = db.get_prompt_by_id(prompt_id)
        assert prompt is not None, "Промт не найден"
        assert prompt["prompt"] == "Тестовый промт", "Текст промта не совпадает"
        print(f"   ✓ Промт получен: {prompt['prompt']}")
        
        # Тест 3: Создание модели
        print("3. Тест создания модели...")
        model_id = db.add_model(
            "Test Model",
            "https://api.test.com/v1/chat",
            "TEST_API_KEY",
            "Test",
            1
        )
        assert model_id > 0, "Модель не создана"
        print(f"   ✓ Модель создана с ID: {model_id}")
        
        # Тест 4: Получение активных моделей
        print("4. Тест получения активных моделей...")
        active_models = db.get_models(active_only=True)
        assert len(active_models) > 0, "Нет активных моделей"
        print(f"   ✓ Найдено активных моделей: {len(active_models)}")
        
        # Тест 5: Сохранение результата
        print("5. Тест сохранения результата...")
        result_id = db.save_result(prompt_id, model_id, "Тестовый ответ")
        assert result_id > 0, "Результат не сохранен"
        print(f"   ✓ Результат сохранен с ID: {result_id}")
        
        # Тест 6: Получение результатов
        print("6. Тест получения результатов...")
        results = db.get_results(prompt_id=prompt_id)
        assert len(results) > 0, "Результаты не найдены"
        print(f"   ✓ Найдено результатов: {len(results)}")
        
        # Тест 7: Поиск промтов
        print("7. Тест поиска промтов...")
        found_prompts = db.search_prompts("Тестовый")
        assert len(found_prompts) > 0, "Промты не найдены"
        print(f"   ✓ Найдено промтов: {len(found_prompts)}")
        
        # Тест 8: Настройки
        print("8. Тест работы с настройками...")
        db.set_setting("test_key", "test_value")
        value = db.get_setting("test_key")
        assert value == "test_value", "Настройка не сохранена"
        print(f"   ✓ Настройка сохранена и получена: {value}")
        
        print("\n=== Все тесты пройдены успешно! ===")
        
    except AssertionError as e:
        print(f"\n✗ Ошибка теста: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Неожиданная ошибка: {e}")
        return False
    finally:
        db.close()
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
    
    return True


if __name__ == "__main__":
    success = test_database()
    sys.exit(0 if success else 1)
