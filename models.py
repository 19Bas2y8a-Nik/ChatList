"""
Модуль для работы с нейросетями (моделями).
Обрабатывает отправку промтов в различные API.
"""

import os
from typing import List, Dict, Optional, Callable
from dotenv import load_dotenv
from db import Database
from network import NetworkClient, APIError


# Загружаем переменные окружения из .env файла
load_dotenv()


class ModelHandler:
    """Базовый класс для работы с моделями."""
    
    def __init__(self, db: Database, network_client: Optional[NetworkClient] = None):
        """
        Инициализация обработчика моделей.
        
        Args:
            db: Экземпляр базы данных
            network_client: Клиент для HTTP-запросов (если не указан, создается новый)
        """
        self.db = db
        self.network_client = network_client or NetworkClient()
    
    def get_api_key(self, api_id: str) -> Optional[str]:
        """
        Получить API-ключ из переменной окружения.
        
        Args:
            api_id: Имя переменной окружения
            
        Returns:
            API-ключ или None, если не найден
        """
        if not api_id or not api_id.strip():
            return None
        
        api_key = os.getenv(api_id.strip())
        
        # Если ключ не найден и api_id содержит слэш, вероятно это имя модели, а не переменная
        if not api_key and ("/" in api_id or "\\" in api_id):
            raise APIError(
                f"Ошибка: '{api_id}' выглядит как имя модели, а не как переменная окружения.\n\n"
                "В поле 'API ID' должно быть имя переменной из файла .env (например, OPENROUTER_API_KEY),\n"
                "а не имя модели (например, meta-llama/llama-3.3-70b-instruct).\n\n"
                "Имя модели указывается в поле 'Название' модели."
            )
        
        return api_key
    
    def get_active_models(self) -> List[Dict]:
        """
        Получить список активных моделей из базы данных.
        
        Returns:
            Список словарей с данными активных моделей
        """
        return self.db.get_models(active_only=True)
    
    def send_prompt_to_model(self, model: Dict, prompt: str) -> str:
        """
        Отправить промт в модель и получить ответ.
        
        Args:
            model: Словарь с данными модели из БД
            prompt: Текст промта
            
        Returns:
            Текст ответа от модели
            
        Raises:
            APIError: При ошибке запроса
        """
        model_type = model.get("model_type", "").lower()
        
        # Выбор обработчика в зависимости от типа модели
        if "openrouter" in model_type:
            return self._send_to_openrouter(model, prompt)
        elif "openai" in model_type or "gpt" in model_type:
            return self._send_to_openai(model, prompt)
        elif "deepseek" in model_type:
            return self._send_to_deepseek(model, prompt)
        elif "groq" in model_type:
            return self._send_to_groq(model, prompt)
        else:
            # Попытка универсального запроса
            return self._send_generic(model, prompt)
    
    def _send_to_openai(self, model: Dict, prompt: str) -> str:
        """
        Отправить запрос в OpenAI API.
        
        Args:
            model: Данные модели
            prompt: Промт
            
        Returns:
            Ответ от модели
        """
        api_id = model.get("api_id", "").strip()
        if not api_id:
            raise APIError("API ID не указан в настройках модели")
        
        api_key = self.get_api_key(api_id)
        if not api_key:
            raise APIError(
                f"API-ключ не найден для переменной '{api_id}'.\n\n"
                "Проверьте:\n"
                f"1. Файл .env существует и содержит переменную {api_id}\n"
                f"2. В файле .env есть строка: {api_id}=ваш_ключ\n"
                "3. Переменная указана правильно (без пробелов, кавычек и т.д.)"
            )
        
        url = model["api_url"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Определяем имя модели из URL или используем название из БД
        model_name = model.get("name", "gpt-3.5-turbo")
        
        json_data = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        try:
            response = self.network_client.post(url, headers, json_data)
            
            # Обработка ответа OpenAI
            if "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"]
            else:
                raise APIError("Неожиданный формат ответа от OpenAI API")
                
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Ошибка при запросе к OpenAI: {str(e)}")
    
    def _send_to_deepseek(self, model: Dict, prompt: str) -> str:
        """
        Отправить запрос в DeepSeek API.
        
        Args:
            model: Данные модели
            prompt: Промт
            
        Returns:
            Ответ от модели
        """
        api_id = model.get("api_id", "").strip()
        if not api_id:
            raise APIError("API ID не указан в настройках модели")
        
        api_key = self.get_api_key(api_id)
        if not api_key:
            raise APIError(
                f"API-ключ не найден для переменной '{api_id}'.\n\n"
                "Проверьте:\n"
                f"1. Файл .env существует и содержит переменную {api_id}\n"
                f"2. В файле .env есть строка: {api_id}=ваш_ключ\n"
                "3. Переменная указана правильно (без пробелов, кавычек и т.д.)"
            )
        
        url = model["api_url"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        model_name = model.get("name", "deepseek-chat")
        
        json_data = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        try:
            response = self.network_client.post(url, headers, json_data)
            
            if "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"]
            else:
                raise APIError("Неожиданный формат ответа от DeepSeek API")
                
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Ошибка при запросе к DeepSeek: {str(e)}")
    
    def _send_to_openrouter(self, model: Dict, prompt: str) -> str:
        """
        Отправить запрос в OpenRouter API.
        
        Args:
            model: Данные модели
            prompt: Промт
            
        Returns:
            Ответ от модели
        """
        api_id = model.get("api_id", "").strip()
        if not api_id:
            raise APIError("API ID не указан в настройках модели")
        
        api_key = self.get_api_key(api_id)
        if not api_key:
            raise APIError(
                f"API-ключ не найден для переменной '{api_id}'.\n\n"
                "Проверьте:\n"
                f"1. Файл .env существует и содержит переменную {api_id}\n"
                f"2. В файле .env есть строка: {api_id}=ваш_ключ\n"
                "3. Переменная указана правильно (без пробелов, кавычек и т.д.)"
            )
        
        url = model["api_url"].strip()
        original_url = url
        
        # Автоматическое исправление URL для OpenRouter, если он неправильный
        # Правильный URL должен быть: https://openrouter.ai/api/v1/chat/completions
        if "openrouter.ai" in url.lower() and "/api/v1/chat/completions" not in url.lower():
            # Если URL содержит имя модели вместо правильного endpoint, исправляем
            if "/" in url and url.count("/") > 3:  # Например: https://openrouter.ai/meta-llama/llama-3.3-70b-instruct
                url = "https://openrouter.ai/api/v1/chat/completions"
            elif not url.endswith("/api/v1/chat/completions"):
                # Если URL просто openrouter.ai или openrouter.ai/что-то, исправляем
                url = "https://openrouter.ai/api/v1/chat/completions"
            
            # Логируем исправление (если есть доступ к логгеру)
            # В этом контексте мы не имеем доступа к логгеру, но можем добавить предупреждение в ошибку
            if url != original_url:
                # URL был исправлен, но мы не можем логировать здесь
                # Вместо этого просто используем правильный URL
                pass
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/yourusername/chatlist",  # Опционально
            "X-Title": "ChatList"  # Опционально
        }
        
        # В OpenRouter имя модели указывается в поле "model"
        # Оно должно быть в формате "provider/model-name" (например, "meta-llama/llama-3.3-70b-instruct")
        # Используем поле "name" из БД, но если оно не содержит слэш, это может быть проблема
        model_name = model.get("name", "").strip()
        
        # Если имя модели не содержит слэш, возможно это просто название для отображения
        # В этом случае нужно использовать полный идентификатор модели OpenRouter
        # Но так как мы не знаем точный формат, попробуем использовать как есть
        # Пользователь должен указать полный идентификатор модели в поле "name"
        # Например: "meta-llama/llama-3.3-70b-instruct"
        
        if not model_name:
            model_name = "openai/gpt-3.5-turbo"  # Значение по умолчанию
        
        json_data = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 4096  # Ограничение max_tokens для предотвращения ошибок нехватки кредитов
        }
        
        try:
            response = self.network_client.post(url, headers, json_data)
            
            # Проверка на HTML в ответе (дополнительная проверка)
            if "text" in response:
                text = response.get("text", "")
                if isinstance(text, str) and (text.strip().startswith('<!DOCTYPE') or text.strip().startswith('<html')):
                    raise APIError(
                        f"Получен HTML вместо JSON ответа от OpenRouter.\n\n"
                        f"Возможные причины:\n"
                        f"1. Неправильный API URL. Должен быть: https://openrouter.ai/api/v1/chat/completions\n"
                        f"2. Проблема с аутентификацией (неверный API-ключ)\n"
                        f"3. Сервер вернул HTML-страницу с ошибкой\n\n"
                        f"Текущий URL: {url}\n"
                        f"Первые 200 символов ответа: {text[:200]}"
                    )
            
            # Детальная обработка ответа OpenRouter
            # OpenRouter может возвращать ответ в разных форматах
            
            # Проверяем наличие ошибки в ответе
            if "error" in response:
                error_msg = response.get("error", {})
                if isinstance(error_msg, dict):
                    error_text = error_msg.get("message", str(error_msg))
                else:
                    error_text = str(error_msg)
                raise APIError(f"Ошибка от OpenRouter API: {error_text}")
            
            # Стандартный формат OpenAI-совместимого API
            if "choices" in response and len(response["choices"]) > 0:
                choice = response["choices"][0]
                if "message" in choice:
                    content = choice["message"].get("content")
                    if content:
                        return content
                    else:
                        # Возможно, ответ в другом поле
                        if "text" in choice["message"]:
                            return choice["message"]["text"]
                        else:
                            raise APIError(f"Ответ не содержит текста. Структура: {list(choice['message'].keys())}")
                elif "text" in choice:
                    return choice["text"]
                else:
                    raise APIError(f"Неожиданная структура choice: {list(choice.keys())}")
            else:
                # Если ответ содержит только "text" с HTML, это уже обработано выше
                # Логируем полный ответ для отладки
                import json
                response_str = json.dumps(response, ensure_ascii=False, indent=2)
                raise APIError(
                    f"Неожиданный формат ответа от OpenRouter API.\n"
                    f"Отправлено: model={model_name}, URL={url}\n"
                    f"Структура ответа: {list(response.keys())}\n"
                    f"Проверьте:\n"
                    f"1. Правильность API URL (должен быть: https://openrouter.ai/api/v1/chat/completions)\n"
                    f"2. Правильность API-ключа в файле .env\n"
                    f"3. Правильность идентификатора модели\n\n"
                    f"Полный ответ: {response_str[:500]}..."
                )
                
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Ошибка при запросе к OpenRouter: {str(e)}")
    
    def _send_to_groq(self, model: Dict, prompt: str) -> str:
        """
        Отправить запрос в Groq API.
        
        Args:
            model: Данные модели
            prompt: Промт
            
        Returns:
            Ответ от модели
        """
        api_id = model.get("api_id", "").strip()
        if not api_id:
            raise APIError("API ID не указан в настройках модели")
        
        api_key = self.get_api_key(api_id)
        if not api_key:
            raise APIError(
                f"API-ключ не найден для переменной '{api_id}'.\n\n"
                "Проверьте:\n"
                f"1. Файл .env существует и содержит переменную {api_id}\n"
                f"2. В файле .env есть строка: {api_id}=ваш_ключ\n"
                "3. Переменная указана правильно (без пробелов, кавычек и т.д.)"
            )
        
        url = model["api_url"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        model_name = model.get("name", "mixtral-8x7b-32768")
        
        json_data = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "model": model_name,
            "temperature": 0.7
        }
        
        try:
            response = self.network_client.post(url, headers, json_data)
            
            if "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"]
            else:
                raise APIError("Неожиданный формат ответа от Groq API")
                
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Ошибка при запросе к Groq: {str(e)}")
    
    def _send_generic(self, model: Dict, prompt: str) -> str:
        """
        Универсальный метод отправки запроса (для неизвестных типов API).
        
        Args:
            model: Данные модели
            prompt: Промт
            
        Returns:
            Ответ от модели
        """
        api_id = model.get("api_id", "").strip()
        if not api_id:
            raise APIError("API ID не указан в настройках модели")
        
        api_key = self.get_api_key(api_id)
        if not api_key:
            raise APIError(
                f"API-ключ не найден для переменной '{api_id}'.\n\n"
                "Проверьте:\n"
                f"1. Файл .env существует и содержит переменную {api_id}\n"
                f"2. В файле .env есть строка: {api_id}=ваш_ключ\n"
                "3. Переменная указана правильно (без пробелов, кавычек и т.д.)"
            )
        
        url = model["api_url"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Попытка стандартного формата OpenAI-совместимого API
        json_data = {
            "model": model.get("name", "default"),
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            response = self.network_client.post(url, headers, json_data)
            
            # Попытка извлечь ответ в разных форматах
            if "choices" in response and len(response["choices"]) > 0:
                choice = response["choices"][0]
                if "message" in choice:
                    return choice["message"]["content"]
                elif "text" in choice:
                    return choice["text"]
            
            if "text" in response:
                return response["text"]
            
            if "response" in response:
                return response["response"]
            
            # Если ничего не подошло, возвращаем весь ответ как строку
            return str(response)
                
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Ошибка при запросе к API: {str(e)}")
    
    def send_prompt_to_all_active(self, prompt: str, 
                                  callback: Optional[Callable[[Dict, str, Optional[str]], None]] = None) -> List[Dict]:
        """
        Отправить промт во все активные модели.
        
        Args:
            prompt: Текст промта
            callback: Функция обратного вызова для каждого результата
                     Принимает: (model_dict, response, error_message)
            
        Returns:
            Список словарей с результатами: [{"model": {...}, "response": "...", "error": "..."}, ...]
        """
        active_models = self.get_active_models()
        results = []
        
        for model in active_models:
            result = {
                "model": model,
                "response": None,
                "error": None
            }
            
            try:
                response = self.send_prompt_to_model(model, prompt)
                result["response"] = response
                
                if callback:
                    callback(model, response, None)
                    
            except APIError as e:
                result["error"] = str(e)
                if callback:
                    callback(model, None, str(e))
            
            except Exception as e:
                result["error"] = f"Неожиданная ошибка: {str(e)}"
                if callback:
                    callback(model, None, result["error"])
            
            results.append(result)
        
        return results
    
    def close(self):
        """Закрыть соединения."""
        if self.network_client:
            self.network_client.close()

