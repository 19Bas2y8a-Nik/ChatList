"""
Модуль для логирования запросов к API и ошибок.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional


def get_user_data_dir() -> str:
    """
    Получить путь к папке данных пользователя.
    Для установленной версии использует AppData, для разработки - текущую директорию.
    
    Returns:
        Путь к папке данных пользователя
    """
    # Проверяем, запущено ли приложение из установленной версии (в Program Files)
    if getattr(sys, 'frozen', False):
        # Приложение запущено из exe файла (установленная версия)
        app_data = os.path.join(os.getenv('APPDATA', ''), 'ChatList')
    else:
        # Приложение запущено из исходников (разработка)
        app_data = os.path.dirname(os.path.abspath(__file__))
    
    # Создаем папку, если её нет
    os.makedirs(app_data, exist_ok=True)
    return app_data


def get_default_log_path() -> str:
    """
    Получить путь к файлу логов по умолчанию.
    
    Returns:
        Путь к файлу логов
    """
    data_dir = get_user_data_dir()
    return os.path.join(data_dir, "chatlist.log")


class Logger:
    """Класс для логирования работы приложения."""
    
    def __init__(self, log_file: Optional[str] = None, log_level: int = logging.INFO):
        """
        Инициализация логгера.
        
        Args:
            log_file: Путь к файлу логов (если None, используется путь по умолчанию)
            log_level: Уровень логирования
        """
        if log_file is None:
            log_file = get_default_log_path()
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
