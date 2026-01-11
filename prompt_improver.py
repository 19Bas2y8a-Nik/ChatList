"""
Модуль для улучшения промтов с помощью AI-ассистента.
Содержит промт-шаблоны и класс для обработки улучшения промтов.
"""

from typing import Dict, List, Optional
import re
import json
from models import ModelHandler, APIError
from db import Database


class PromptImprover:
    """Класс для улучшения промтов с помощью AI-моделей."""
    
    def __init__(self, db: Database, model_handler: Optional[ModelHandler] = None):
        """
        Инициализация улучшителя промтов.
        
        Args:
            db: Экземпляр базы данных
            model_handler: Обработчик моделей (если не указан, создается новый)
        """
        self.db = db
        self.model_handler = model_handler or ModelHandler(db)
    
    def _create_improvement_prompt(self, original_prompt: str, 
                                   improvement_type: str = "general") -> str:
        """
        Создать промт для улучшения исходного промта.
        
        Args:
            original_prompt: Исходный промт
            improvement_type: Тип улучшения ("general", "code", "analysis", "creative")
            
        Returns:
            Промт для отправки в модель
        """
        base_prompt = f"""Ты - эксперт по созданию эффективных промтов для AI-моделей.

Исходный промт пользователя:
"{original_prompt}"

Задача:
1. Проанализируй исходный промт
2. Предложи улучшенную версию промта, которая:
   - Более четко формулирует задачу
   - Содержит необходимые детали и контекст
   - Использует лучшие практики создания промтов
   - Сохраняет исходную суть и намерение
3. Предложи 2-3 альтернативных варианта переформулировки, которые могут быть полезны

Формат ответа (строго соблюдай формат JSON):
{{
    "improved": "улучшенная версия промта",
    "variants": [
        "вариант 1",
        "вариант 2",
        "вариант 3"
    ],
    "explanation": "краткое объяснение улучшений"
}}

Важно: отвечай ТОЛЬКО валидным JSON, без дополнительных комментариев до или после JSON."""
        
        # Специализированные промты для разных типов
        if improvement_type == "code":
            base_prompt += "\n\nОсобое внимание удели:\n- Точности технических требований\n- Ясности описания алгоритма\n- Указанию языка программирования и стиля кода"
        elif improvement_type == "analysis":
            base_prompt += "\n\nОсобое внимание удели:\n- Четкости критериев анализа\n- Структурированности запроса\n- Определению формата вывода"
        elif improvement_type == "creative":
            base_prompt += "\n\nОсобое внимание удели:\n- Творческим элементам\n- Стилю и тону\n- Вдохновению и оригинальности"
        
        return base_prompt
    
    def _parse_response(self, response_text: str) -> Dict[str, any]:
        """
        Распарсить ответ от модели и извлечь улучшенные варианты.
        
        Args:
            response_text: Текст ответа от модели
            
        Returns:
            Словарь с улучшенными вариантами:
            {
                "improved": str,
                "variants": List[str],
                "explanation": str
            }
        """
        # Попытка извлечь JSON из ответа
        # Модель может вернуть JSON в разных форматах
        
        # Удаляем markdown код блоки, если есть
        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*', '', response_text)
        response_text = response_text.strip()
        
        # Попытка найти JSON объект в тексте
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            try:
                result = json.loads(json_str)
                
                # Валидация структуры
                if "improved" not in result:
                    # Если нет "improved", но есть другие поля, используем их
                    result = self._fallback_parse(response_text, result)
                
                return result
            except json.JSONDecodeError:
                pass
        
        # Если не удалось распарсить JSON, используем fallback
        return self._fallback_parse(response_text)
    
    def _fallback_parse(self, response_text: str, partial_result: Optional[Dict] = None) -> Dict[str, any]:
        """
        Альтернативный парсинг, если JSON не распарсился.
        
        Args:
            response_text: Текст ответа
            partial_result: Частично распарсенный результат
            
        Returns:
            Словарь с результатами
        """
        result = partial_result or {}
        
        # Попытка найти улучшенную версию по ключевым словам
        improved_match = re.search(
            r'(?:улучшен|improved|улучшенная версия)[\s:]*["\']?([^"\']+)["\']?',
            response_text, re.IGNORECASE
        )
        if improved_match:
            result["improved"] = improved_match.group(1).strip()
        
        # Если улучшенная версия не найдена, используем первый абзац
        if "improved" not in result:
            lines = [line.strip() for line in response_text.split('\n') if line.strip()]
            if lines:
                # Пропускаем первые строки, если они содержат метаданные
                start_idx = 0
                for i, line in enumerate(lines[:5]):
                    if any(keyword in line.lower() for keyword in ['json', '{', '}', 'improved', 'variants']):
                        start_idx = i + 1
                        break
                
                if start_idx < len(lines):
                    result["improved"] = lines[start_idx]
        
        # Если все еще нет улучшенной версии, используем весь текст
        if "improved" not in result:
            result["improved"] = response_text.strip()
        
        # Поиск вариантов
        variants = []
        variant_patterns = [
            r'(?:вариант|variant)[\s\d:]*["\']?([^"\'\n]+)["\']?',
            r'["\']([^"\']{20,})["\']',  # Строки в кавычках длиной от 20 символов
        ]
        
        for pattern in variant_patterns:
            matches = re.findall(pattern, response_text, re.IGNORECASE)
            for match in matches[:3]:  # Максимум 3 варианта
                if len(match.strip()) > 10:  # Минимальная длина варианта
                    variants.append(match.strip())
        
        # Если вариантов не найдено, разбиваем текст на абзацы
        if not variants:
            paragraphs = [p.strip() for p in response_text.split('\n\n') if len(p.strip()) > 20]
            variants = paragraphs[1:4]  # Пропускаем первый абзац (улучшенная версия), берем следующие
        
        result["variants"] = variants[:3]  # Максимум 3 варианта
        
        # Объяснение
        explanation_match = re.search(
            r'(?:объяснение|explanation|комментарий)[\s:]*["\']?([^"\']+)["\']?',
            response_text, re.IGNORECASE
        )
        if explanation_match:
            result["explanation"] = explanation_match.group(1).strip()
        else:
            result["explanation"] = "Промт улучшен для большей ясности и эффективности."
        
        return result
    
    def improve_prompt(self, original_prompt: str, model: Dict, 
                       improvement_type: str = "general") -> Dict[str, any]:
        """
        Улучшить промт с помощью указанной модели.
        
        Args:
            original_prompt: Исходный промт
            model: Словарь с данными модели из БД
            improvement_type: Тип улучшения ("general", "code", "analysis", "creative")
            
        Returns:
            Словарь с результатами улучшения:
            {
                "improved": str,
                "variants": List[str],
                "explanation": str,
                "original": str
            }
            
        Raises:
            APIError: При ошибке запроса к модели
            ValueError: При невалидных входных данных
        """
        if not original_prompt or not original_prompt.strip():
            raise ValueError("Исходный промт не может быть пустым")
        
        if not model:
            raise ValueError("Модель не указана")
        
        # Создаем промт для улучшения
        improvement_prompt = self._create_improvement_prompt(
            original_prompt.strip(), 
            improvement_type
        )
        
        # Отправляем запрос к модели
        try:
            response_text = self.model_handler.send_prompt_to_model(model, improvement_prompt)
        except APIError as e:
            raise APIError(f"Ошибка при запросе улучшения промта: {str(e)}")
        
        # Парсим ответ
        result = self._parse_response(response_text)
        result["original"] = original_prompt.strip()
        
        # Гарантируем наличие всех полей
        if "improved" not in result or not result["improved"]:
            result["improved"] = original_prompt.strip()
        
        if "variants" not in result:
            result["variants"] = []
        
        if "explanation" not in result:
            result["explanation"] = "Промт обработан."
        
        return result
    
    def close(self):
        """Закрыть соединения."""
        if self.model_handler:
            self.model_handler.close()
