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
        return os.getenv(api_id)
    
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
        if "openai" in model_type or "gpt" in model_type:
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
        api_key = self.get_api_key(model["api_id"])
        if not api_key:
            raise APIError(f"API-ключ не найден для переменной {model['api_id']}")
        
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
        api_key = self.get_api_key(model["api_id"])
        if not api_key:
            raise APIError(f"API-ключ не найден для переменной {model['api_id']}")
        
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
    
    def _send_to_groq(self, model: Dict, prompt: str) -> str:
        """
        Отправить запрос в Groq API.
        
        Args:
            model: Данные модели
            prompt: Промт
            
        Returns:
            Ответ от модели
        """
        api_key = self.get_api_key(model["api_id"])
        if not api_key:
            raise APIError(f"API-ключ не найден для переменной {model['api_id']}")
        
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
        api_key = self.get_api_key(model["api_id"])
        if not api_key:
            raise APIError(f"API-ключ не найден для переменной {model['api_id']}")
        
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

