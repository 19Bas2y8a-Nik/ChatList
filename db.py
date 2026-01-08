"""
Модуль для работы с базой данных SQLite.
Инкапсулирует все операции с базой данных.
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class Database:
    """Класс для работы с базой данных SQLite."""
    
    def __init__(self, db_path: str = "chatlist.db"):
        """
        Инициализация подключения к базе данных.
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.conn = None
        self.init_database()
    
    def get_connection(self) -> sqlite3.Connection:
        """Получить соединение с базой данных."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
        return self.conn
    
    def close(self):
        """Закрыть соединение с базой данных."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def init_database(self):
        """Инициализация базы данных: создание таблиц и индексов."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица prompts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                prompt TEXT NOT NULL,
                tags TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prompts_date ON prompts(date)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prompts_tags ON prompts(tags)
        """)
        
        # Таблица models
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                api_url TEXT NOT NULL,
                api_id TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                model_type TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_models_is_active ON models(is_active)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_models_name ON models(name)
        """)
        
        # Таблица results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id INTEGER NOT NULL,
                model_id INTEGER NOT NULL,
                response TEXT NOT NULL,
                saved_at TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE,
                FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_prompt_id ON results(prompt_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_model_id ON results(model_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_saved_at ON results(saved_at)
        """)
        
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_results_prompt_model 
            ON results(prompt_id, model_id)
        """)
        
        # Таблица settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT,
                updated_at TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key)
        """)
        
        conn.commit()
    
    # ==================== Работа с таблицей prompts ====================
    
    def add_prompt(self, prompt: str, tags: Optional[str] = None) -> int:
        """
        Добавить новый промт.
        
        Args:
            prompt: Текст промта
            tags: Теги (через запятую)
            
        Returns:
            ID созданного промта
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO prompts (date, prompt, tags)
            VALUES (?, ?, ?)
        """, (date, prompt, tags))
        
        conn.commit()
        return cursor.lastrowid
    
    def get_prompts(self, order_by: str = "date DESC") -> List[Dict]:
        """
        Получить список всех промтов.
        
        Args:
            order_by: Поле и направление сортировки (например, "date DESC")
            
        Returns:
            Список словарей с данными промтов
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Безопасная сортировка - только по разрешенным полям
        allowed_fields = ["id", "date", "prompt", "tags"]
        field, direction = order_by.split() if " " in order_by else (order_by, "ASC")
        
        if field not in allowed_fields:
            field = "date"
            direction = "DESC"
        
        cursor.execute(f"""
            SELECT id, date, prompt, tags
            FROM prompts
            ORDER BY {field} {direction}
        """)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_prompt_by_id(self, prompt_id: int) -> Optional[Dict]:
        """
        Получить промт по ID.
        
        Args:
            prompt_id: ID промта
            
        Returns:
            Словарь с данными промта или None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, date, prompt, tags
            FROM prompts
            WHERE id = ?
        """, (prompt_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def search_prompts(self, query: str, search_in_tags: bool = True) -> List[Dict]:
        """
        Поиск промтов по тексту или тегам.
        
        Args:
            query: Поисковый запрос
            search_in_tags: Искать также в тегах
            
        Returns:
            Список найденных промтов
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        search_pattern = f"%{query}%"
        
        if search_in_tags:
            cursor.execute("""
                SELECT id, date, prompt, tags
                FROM prompts
                WHERE prompt LIKE ? OR tags LIKE ?
                ORDER BY date DESC
            """, (search_pattern, search_pattern))
        else:
            cursor.execute("""
                SELECT id, date, prompt, tags
                FROM prompts
                WHERE prompt LIKE ?
                ORDER BY date DESC
            """, (search_pattern,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def search_prompts_by_tags(self, tags: List[str]) -> List[Dict]:
        """
        Поиск промтов по тегам.
        
        Args:
            tags: Список тегов для поиска
            
        Returns:
            Список найденных промтов
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Поиск промтов, содержащих хотя бы один из указанных тегов
        conditions = " OR ".join(["tags LIKE ?" for _ in tags])
        search_patterns = [f"%{tag}%" for tag in tags]
        
        cursor.execute(f"""
            SELECT id, date, prompt, tags
            FROM prompts
            WHERE {conditions}
            ORDER BY date DESC
        """, search_patterns)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def update_prompt(self, prompt_id: int, prompt: Optional[str] = None, 
                     tags: Optional[str] = None) -> bool:
        """
        Обновить промт.
        
        Args:
            prompt_id: ID промта
            prompt: Новый текст промта (если нужно обновить)
            tags: Новые теги (если нужно обновить)
            
        Returns:
            True если обновление успешно
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if prompt is not None:
            updates.append("prompt = ?")
            params.append(prompt)
        
        if tags is not None:
            updates.append("tags = ?")
            params.append(tags)
        
        if not updates:
            return False
        
        params.append(prompt_id)
        
        cursor.execute(f"""
            UPDATE prompts
            SET {', '.join(updates)}
            WHERE id = ?
        """, params)
        
        conn.commit()
        return cursor.rowcount > 0
    
    def delete_prompt(self, prompt_id: int) -> bool:
        """
        Удалить промт.
        
        Args:
            prompt_id: ID промта
            
        Returns:
            True если удаление успешно
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
        conn.commit()
        
        return cursor.rowcount > 0
    
    # ==================== Работа с таблицей models ====================
    
    def add_model(self, name: str, api_url: str, api_id: str, 
                  model_type: Optional[str] = None, is_active: int = 1) -> int:
        """
        Добавить новую модель.
        
        Args:
            name: Название модели
            api_url: URL API
            api_id: Имя переменной окружения с API-ключом
            model_type: Тип модели (OpenAI, DeepSeek, Groq и т.д.)
            is_active: Активна ли модель (1 - да, 0 - нет)
            
        Returns:
            ID созданной модели
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO models (name, api_url, api_id, is_active, model_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, api_url, api_id, is_active, model_type, created_at, created_at))
        
        conn.commit()
        return cursor.lastrowid
    
    def get_models(self, active_only: bool = False) -> List[Dict]:
        """
        Получить список моделей.
        
        Args:
            active_only: Только активные модели
            
        Returns:
            Список словарей с данными моделей
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if active_only:
            cursor.execute("""
                SELECT id, name, api_url, api_id, is_active, model_type, created_at, updated_at
                FROM models
                WHERE is_active = 1
                ORDER BY name
            """)
        else:
            cursor.execute("""
                SELECT id, name, api_url, api_id, is_active, model_type, created_at, updated_at
                FROM models
                ORDER BY name
            """)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_model_by_id(self, model_id: int) -> Optional[Dict]:
        """
        Получить модель по ID.
        
        Args:
            model_id: ID модели
            
        Returns:
            Словарь с данными модели или None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, api_url, api_id, is_active, model_type, created_at, updated_at
            FROM models
            WHERE id = ?
        """, (model_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_model(self, model_id: int, name: Optional[str] = None,
                    api_url: Optional[str] = None, api_id: Optional[str] = None,
                    model_type: Optional[str] = None, is_active: Optional[int] = None) -> bool:
        """
        Обновить модель.
        
        Args:
            model_id: ID модели
            name: Новое название
            api_url: Новый URL API
            api_id: Новое имя переменной окружения
            model_type: Новый тип модели
            is_active: Новый статус активности
            
        Returns:
            True если обновление успешно
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        
        if api_url is not None:
            updates.append("api_url = ?")
            params.append(api_url)
        
        if api_id is not None:
            updates.append("api_id = ?")
            params.append(api_id)
        
        if model_type is not None:
            updates.append("model_type = ?")
            params.append(model_type)
        
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(is_active)
        
        if not updates:
            return False
        
        updates.append("updated_at = ?")
        params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        params.append(model_id)
        
        cursor.execute(f"""
            UPDATE models
            SET {', '.join(updates)}
            WHERE id = ?
        """, params)
        
        conn.commit()
        return cursor.rowcount > 0
    
    def set_model_active(self, model_id: int, is_active: int) -> bool:
        """
        Активировать/деактивировать модель.
        
        Args:
            model_id: ID модели
            is_active: 1 - активировать, 0 - деактивировать
            
        Returns:
            True если обновление успешно
        """
        return self.update_model(model_id, is_active=is_active)
    
    def search_models(self, query: str) -> List[Dict]:
        """
        Поиск моделей по названию или типу.
        
        Args:
            query: Поисковый запрос
            
        Returns:
            Список найденных моделей
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        search_pattern = f"%{query}%"
        
        cursor.execute("""
            SELECT id, name, api_url, api_id, is_active, model_type, created_at, updated_at
            FROM models
            WHERE name LIKE ? OR model_type LIKE ?
            ORDER BY name
        """, (search_pattern, search_pattern))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def delete_model(self, model_id: int) -> bool:
        """
        Удалить модель.
        
        Args:
            model_id: ID модели
            
        Returns:
            True если удаление успешно
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM models WHERE id = ?", (model_id,))
        conn.commit()
        
        return cursor.rowcount > 0
    
    # ==================== Работа с таблицей results ====================
    
    def save_result(self, prompt_id: int, model_id: int, response: str, 
                   notes: Optional[str] = None) -> int:
        """
        Сохранить результат ответа модели.
        
        Args:
            prompt_id: ID промта
            model_id: ID модели
            response: Текст ответа
            notes: Дополнительные заметки
            
        Returns:
            ID созданного результата
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        saved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Используем INSERT OR REPLACE для обновления существующего результата
        cursor.execute("""
            INSERT OR REPLACE INTO results (prompt_id, model_id, response, saved_at, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (prompt_id, model_id, response, saved_at, notes))
        
        conn.commit()
        return cursor.lastrowid
    
    def get_results(self, prompt_id: Optional[int] = None, 
                   model_id: Optional[int] = None,
                   order_by: str = "saved_at DESC") -> List[Dict]:
        """
        Получить сохраненные результаты.
        
        Args:
            prompt_id: Фильтр по ID промта (опционально)
            model_id: Фильтр по ID модели (опционально)
            order_by: Поле и направление сортировки
            
        Returns:
            Список словарей с данными результатов
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        conditions = []
        params = []
        
        if prompt_id is not None:
            conditions.append("prompt_id = ?")
            params.append(prompt_id)
        
        if model_id is not None:
            conditions.append("model_id = ?")
            params.append(model_id)
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        # Безопасная сортировка
        allowed_fields = ["id", "prompt_id", "model_id", "saved_at"]
        field, direction = order_by.split() if " " in order_by else (order_by, "ASC")
        
        if field not in allowed_fields:
            field = "saved_at"
            direction = "DESC"
        
        cursor.execute(f"""
            SELECT id, prompt_id, model_id, response, saved_at, notes
            FROM results
            {where_clause}
            ORDER BY {field} {direction}
        """, params)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_result_by_id(self, result_id: int) -> Optional[Dict]:
        """
        Получить результат по ID.
        
        Args:
            result_id: ID результата
            
        Returns:
            Словарь с данными результата или None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, prompt_id, model_id, response, saved_at, notes
            FROM results
            WHERE id = ?
        """, (result_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def search_results(self, query: str) -> List[Dict]:
        """
        Поиск результатов по тексту ответа или заметкам.
        
        Args:
            query: Поисковый запрос
            
        Returns:
            Список найденных результатов
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        search_pattern = f"%{query}%"
        
        cursor.execute("""
            SELECT id, prompt_id, model_id, response, saved_at, notes
            FROM results
            WHERE response LIKE ? OR notes LIKE ?
            ORDER BY saved_at DESC
        """, (search_pattern, search_pattern))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def delete_result(self, result_id: int) -> bool:
        """
        Удалить результат.
        
        Args:
            result_id: ID результата
            
        Returns:
            True если удаление успешно
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM results WHERE id = ?", (result_id,))
        conn.commit()
        
        return cursor.rowcount > 0
    
    # ==================== Работа с таблицей settings ====================
    
    def set_setting(self, key: str, value: Optional[str]) -> bool:
        """
        Сохранить настройку.
        
        Args:
            key: Ключ настройки
            value: Значение настройки
            
        Returns:
            True если сохранение успешно
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value, updated_at))
        
        conn.commit()
        return True
    
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Получить настройку.
        
        Args:
            key: Ключ настройки
            default: Значение по умолчанию, если настройка не найдена
            
        Returns:
            Значение настройки или default
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT value
            FROM settings
            WHERE key = ?
        """, (key,))
        
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else default
    
    def get_all_settings(self) -> Dict[str, str]:
        """
        Получить все настройки.
        
        Returns:
            Словарь с настройками (ключ -> значение)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        
        return {row[0]: row[1] for row in rows if row[1] is not None}
    
    def delete_setting(self, key: str) -> bool:
        """
        Удалить настройку.
        
        Args:
            key: Ключ настройки
            
        Returns:
            True если удаление успешно
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
        conn.commit()
        
        return cursor.rowcount > 0

