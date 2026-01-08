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
                
                # Попытка распарсить JSON
                try:
                    return response.json()
                except ValueError:
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
                    if "error" in error_data:
                        error_msg += f": {error_data['error']}"
                except:
                    error_msg += f": {response.text[:200]}"
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

