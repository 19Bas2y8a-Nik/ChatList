"""
Модуль для работы с HTTP-запросами к API нейросетей.
Обрабатывает отправку запросов, ошибки и таймауты.
"""

import requests
from typing import Dict, Optional, Any
import time


class APIError(Exception):
    """Исключение для ошибок API."""
    pass


class NetworkClient:
    """Базовый класс для работы с HTTP-запросами."""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        Инициализация клиента.
        
        Args:
            timeout: Таймаут запроса в секундах
            max_retries: Максимальное количество попыток при ошибке
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
    
    def post(self, url: str, headers: Dict[str, str], 
             json_data: Dict[str, Any], timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Отправить POST запрос.
        
        Args:
            url: URL для запроса
            headers: Заголовки запроса
            json_data: JSON данные для отправки
            timeout: Таймаут запроса (если не указан, используется self.timeout)
            
        Returns:
            Ответ от сервера в виде словаря
            
        Raises:
            APIError: При ошибке запроса
        """
        timeout = timeout or self.timeout
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    url,
                    headers=headers,
                    json=json_data,
                    timeout=timeout
                )
                
                # Проверка статуса ответа
                response.raise_for_status()
                
                # Проверка Content-Type
                content_type = response.headers.get('Content-Type', '').lower()
                
                # Если получен HTML вместо JSON, это ошибка
                if 'text/html' in content_type or response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html'):
                    raise APIError(
                        f"Получен HTML вместо JSON ответа. Возможно, неправильный API URL.\n"
                        f"URL: {url}\n"
                        f"Content-Type: {content_type}\n"
                        f"Проверьте, что API URL правильный (например, https://openrouter.ai/api/v1/chat/completions)\n"
                        f"Первые 200 символов ответа: {response.text[:200]}"
                    )
                
                # Попытка распарсить JSON
                try:
                    return response.json()
                except ValueError:
                    # Если ответ не JSON, проверяем, не HTML ли это
                    text = response.text.strip()
                    if text.startswith('<!DOCTYPE') or text.startswith('<html'):
                        raise APIError(
                            f"Получен HTML вместо JSON ответа. Возможно, неправильный API URL.\n"
                            f"URL: {url}\n"
                            f"Проверьте, что API URL правильный.\n"
                            f"Первые 200 символов ответа: {text[:200]}"
                        )
                    # Если ответ не JSON, возвращаем текст
                    return {"text": response.text}
                    
            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Экспоненциальная задержка
                    continue
                raise APIError(f"Таймаут запроса к {url} после {self.max_retries} попыток")
            
            except requests.exceptions.ConnectionError as e:
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise APIError(f"Ошибка подключения к {url}: {str(e)}")
            
            except requests.exceptions.HTTPError as e:
                error_msg = f"HTTP ошибка {response.status_code}"
                try:
                    error_data = response.json()
                    # Обработка различных форматов ошибок
                    if "error" in error_data:
                        error_info = error_data["error"]
                        if isinstance(error_info, dict):
                            error_msg = error_info.get("message", str(error_info))
                        else:
                            error_msg = str(error_info)
                    elif "message" in error_data:
                        error_msg = error_data["message"]
                        # Добавляем дополнительную информацию для специфичных ошибок
                        if "data policy" in error_msg.lower() or "privacy" in error_msg.lower():
                            error_msg += "\n\nНастройте политику данных на: https://openrouter.ai/settings/privacy"
                        elif "credits" in error_msg.lower() or "payment" in error_msg.lower() or response.status_code == 402:
                            # Ошибка нехватки кредитов
                            if "credits" in error_msg.lower():
                                error_msg += "\n\nПопробуйте уменьшить max_tokens или пополните баланс на: https://openrouter.ai/settings/credits"
                            else:
                                error_msg = f"Недостаточно кредитов для выполнения запроса.\n\n{error_msg}\n\nПополните баланс: https://openrouter.ai/settings/credits"
                        if "code" in error_data:
                            error_msg = f"{error_msg} (код: {error_data['code']})"
                    else:
                        error_msg = str(error_data)
                except:
                    # Если не удалось распарсить JSON, используем текст ответа
                    text = response.text[:500]
                    if "data policy" in text.lower() or "privacy" in text.lower():
                        error_msg = f"Ошибка политики данных. Настройте: https://openrouter.ai/settings/privacy"
                    elif "credits" in text.lower() or "payment" in text.lower() or response.status_code == 402:
                        error_msg = f"Недостаточно кредитов. Пополните баланс: https://openrouter.ai/settings/credits"
                    else:
                        error_msg += f": {text}"
                
                # Специальная обработка для статуса 402 (Payment Required)
                if response.status_code == 402:
                    if "credits" not in error_msg.lower() and "payment" not in error_msg.lower():
                        error_msg = f"Недостаточно кредитов для выполнения запроса.\n\n{error_msg}\n\nПополните баланс: https://openrouter.ai/settings/credits"
                
                raise APIError(error_msg)
            
            except requests.exceptions.RequestException as e:
                raise APIError(f"Ошибка запроса к {url}: {str(e)}")
        
        raise APIError(f"Не удалось выполнить запрос к {url} после {self.max_retries} попыток")
    
    def get(self, url: str, headers: Dict[str, str], 
            params: Optional[Dict[str, Any]] = None,
            timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Отправить GET запрос.
        
        Args:
            url: URL для запроса
            headers: Заголовки запроса
            params: Параметры запроса
            timeout: Таймаут запроса
            
        Returns:
            Ответ от сервера в виде словаря
            
        Raises:
            APIError: При ошибке запроса
        """
        timeout = timeout or self.timeout
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=timeout
                )
                
                response.raise_for_status()
                
                try:
                    return response.json()
                except ValueError:
                    return {"text": response.text}
                    
            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise APIError(f"Таймаут запроса к {url} после {self.max_retries} попыток")
            
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise APIError(f"Ошибка запроса к {url}: {str(e)}")
        
        raise APIError(f"Не удалось выполнить запрос к {url} после {self.max_retries} попыток")
    
    def close(self):
        """Закрыть сессию."""
        self.session.close()

