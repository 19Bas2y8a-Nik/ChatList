"""
Модуль для логирования запросов к API и ошибок.
"""

import logging
import os
from datetime import datetime
from typing import Optional


class Logger:
    """Класс для логирования работы приложения."""
    
    def __init__(self, log_file: str = "chatlist.log", log_level: int = logging.INFO):
        """
        Инициализация логгера.
        
        Args:
            log_file: Путь к файлу логов
            log_level: Уровень логирования
        """
        self.log_file = log_file
        self.logger = logging.getLogger("ChatList")
        self.logger.setLevel(log_level)
        
        # Очистка существующих обработчиков
        self.logger.handlers.clear()
        
        # Формат логов
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Обработчик для файла
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Обработчик для консоли
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def log_request(self, model_name: str, prompt: str, response: Optional[str] = None, 
                   error: Optional[str] = None):
        """
        Логировать запрос к API.
        
        Args:
            model_name: Название модели
            prompt: Промт
            response: Ответ (если успешно)
            error: Ошибка (если была)
        """
        if error:
            self.logger.error(f"Запрос к {model_name} завершился ошибкой: {error}")
            self.logger.debug(f"Промт: {prompt[:100]}...")
        else:
            self.logger.info(f"Запрос к {model_name} выполнен успешно")
            self.logger.debug(f"Промт: {prompt[:100]}...")
            if response:
                self.logger.debug(f"Ответ: {response[:200]}...")
    
    def log_error(self, message: str, exception: Optional[Exception] = None):
        """
        Логировать ошибку.
        
        Args:
            message: Сообщение об ошибке
            exception: Исключение (если есть)
        """
        if exception:
            self.logger.error(f"{message}: {str(exception)}", exc_info=True)
        else:
            self.logger.error(message)
    
    def log_info(self, message: str):
        """
        Логировать информационное сообщение.
        
        Args:
            message: Сообщение
        """
        self.logger.info(message)
    
    def log_debug(self, message: str):
        """
        Логировать отладочное сообщение.
        
        Args:
            message: Сообщение
        """
        self.logger.debug(message)
    
    def log_api_response(self, model_name: str, response_data: dict, error: Optional[str] = None):
        """
        Логировать полный ответ от API для отладки.
        
        Args:
            model_name: Название модели
            response_data: Полный ответ от API
            error: Ошибка (если была)
        """
        if error:
            self.logger.error(f"Ошибка API для {model_name}: {error}")
        
        # Логируем структуру ответа
        import json
        try:
            response_str = json.dumps(response_data, ensure_ascii=False, indent=2)
            self.logger.debug(f"Полный ответ от {model_name}:\n{response_str[:1000]}...")
        except:
            self.logger.debug(f"Ответ от {model_name}: {str(response_data)[:500]}...")
