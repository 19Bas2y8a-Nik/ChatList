"""
Основной модуль приложения ChatList.
Реализует пользовательский интерфейс на PyQt5.
"""

import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QLineEdit, QMessageBox, QHeaderView, QProgressBar,
    QSplitter, QGroupBox, QDialog, QFormLayout, QDialogButtonBox,
    QFileDialog, QMenuBar, QMenu, QAction, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from typing import List, Dict, Optional
import json

from db import Database
from models import ModelHandler, APIError
from logger import Logger


class SendPromptThread(QThread):
    """Поток для асинхронной отправки промтов в модели."""
    
    result_received = pyqtSignal(dict, str, str)  # model, response, error
    finished = pyqtSignal()
    
    def __init__(self, db_path: str, active_models: List[Dict], prompt: str, logger=None):
        super().__init__()
        self.db_path = db_path
        self.active_models = active_models
        self.prompt = prompt
        self.logger = logger
    
    def run(self):
        """Запуск отправки промтов."""
        # Создаем новое соединение с БД в рабочем потоке
        from db import Database
        from models import ModelHandler
        
        db = Database(self.db_path)
        model_handler = ModelHandler(db)
        
        def callback(model, response, error):
            self.result_received.emit(model, response or "", error or "")
        
        # Отправляем промт во все активные модели
        for model in self.active_models:
            result = {
                "model": model,
                "response": None,
                "error": None
            }
            
            try:
                response = model_handler.send_prompt_to_model(model, self.prompt)
                result["response"] = response
                callback(model, response, None)
            except Exception as e:
                error_msg = str(e)
                result["error"] = error_msg
                if self.logger:
                    self.logger.log_error(f"Ошибка при запросе к {model.get('name', 'Unknown')}", e)
                callback(model, None, error_msg)
        
        # Закрываем соединения
        model_handler.close()
        db.close()
        
        self.finished.emit()


class ModelDialog(QDialog):
    """Диалог для добавления/редактирования модели."""
    
    def __init__(self, parent=None, model_data: Optional[Dict] = None):
        super().__init__(parent)
        self.model_data = model_data
        self.setWindowTitle("Редактировать модель" if model_data else "Добавить модель")
        self.setModal(True)
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса диалога."""
        layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: GPT-4 или meta-llama/llama-3.3-70b-instruct")
        self.name_edit.setToolTip(
            "Название модели для отображения в интерфейсе.\n\n"
            "Для OpenRouter: укажите полный идентификатор модели в формате provider/model-name\n"
            "Примеры: meta-llama/llama-3.3-70b-instruct, openai/gpt-4, mistralai/mistral-large\n\n"
            "Для других API: можно указать просто название (например, GPT-4)"
        )
        
        self.api_url_edit = QLineEdit()
        self.api_url_edit.setPlaceholderText("https://api.openrouter.ai/api/v1/chat/completions")
        self.api_url_edit.setToolTip("Полный URL API для отправки запросов")
        
        self.api_id_edit = QLineEdit()
        self.api_id_edit.setPlaceholderText("OPENROUTER_API_KEY")
        self.api_id_edit.setToolTip("Имя переменной окружения из файла .env, содержащей API-ключ.\nПримеры: OPENROUTER_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY")
        
        self.model_type_edit = QLineEdit()
        self.model_type_edit.setPlaceholderText("OpenRouter, OpenAI, DeepSeek, Groq")
        self.model_type_edit.setToolTip(
            "Тип API провайдера для правильной обработки запросов.\n\n"
            "Важно: Для OpenRouter в поле 'Название' нужно указать полный идентификатор модели!\n"
            "Например: meta-llama/llama-3.3-70b-instruct (а не просто 'Llama 3.3 70B')"
        )
        self.model_type_edit.textChanged.connect(self.on_model_type_changed)
        
        self.is_active_checkbox = QCheckBox()
        self.is_active_checkbox.setChecked(True)
        self.is_active_checkbox.setToolTip("Активные модели будут использоваться при отправке запросов")
        
        # Добавляем подсказку под полем API ID
        api_id_label = QLabel("API ID (имя переменной .env):")
        api_id_label.setToolTip("Это НЕ имя модели! Это имя переменной из файла .env")
        api_id_hint = QLabel("⚠ Это должно быть имя переменной из .env файла (например, OPENROUTER_API_KEY),\nа не имя модели (например, meta-llama/llama-3.3-70b-instruct)")
        api_id_hint.setStyleSheet("color: #d97706; font-size: 9pt;")
        api_id_hint.setWordWrap(True)
        
        layout.addRow("Название:", self.name_edit)
        layout.addRow("API URL:", self.api_url_edit)
        layout.addRow(api_id_label, self.api_id_edit)
        layout.addRow("", api_id_hint)
        layout.addRow("Тип модели:", self.model_type_edit)
        layout.addRow("Активна:", self.is_active_checkbox)
        
        if self.model_data:
            self.name_edit.setText(self.model_data.get("name", ""))
            self.api_url_edit.setText(self.model_data.get("api_url", ""))
            self.api_id_edit.setText(self.model_data.get("api_id", ""))
            self.model_type_edit.setText(self.model_data.get("model_type", ""))
            self.is_active_checkbox.setChecked(self.model_data.get("is_active", 1) == 1)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def validate_and_accept(self):
        """Валидация перед принятием формы."""
        data = self.get_data()
        
        # Проверка имени переменной окружения
        api_id = data["api_id"].strip()
        if not api_id:
            QMessageBox.warning(self, "Ошибка валидации", "Поле 'API ID' не может быть пустым!")
            return
        
        # Проверка формата имени переменной (должно быть в верхнем регистре, без слэшей)
        if "/" in api_id or "\\" in api_id:
            QMessageBox.warning(
                self,
                "Ошибка валидации",
                "API ID не должен содержать слэши!\n\n"
                "API ID - это имя переменной окружения из файла .env,\n"
                "а не имя модели.\n\n"
                "Примеры правильных значений:\n"
                "• OPENROUTER_API_KEY\n"
                "• OPENAI_API_KEY\n"
                "• DEEPSEEK_API_KEY\n\n"
                "Неправильно: meta-llama/llama-3.3-70b-instruct"
            )
            return
        
        # Проверка существования переменной окружения
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv(api_id)
        if not api_key:
            reply = QMessageBox.warning(
                self,
                "Предупреждение",
                f"Переменная окружения '{api_id}' не найдена в файле .env!\n\n"
                "Убедитесь, что:\n"
                "1. Файл .env существует в корне проекта\n"
                "2. В файле .env есть строка: {api_id}=ваш_ключ\n\n"
                "Продолжить добавление модели?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        else:
            QMessageBox.information(
                self,
                "Проверка пройдена",
                f"Переменная окружения '{api_id}' найдена в .env файле."
            )
        
        self.accept()
    
    def on_model_type_changed(self, text: str):
        """Обработчик изменения типа модели."""
        if "openrouter" in text.lower():
            # Для OpenRouter обновляем подсказку
            self.name_edit.setPlaceholderText("meta-llama/llama-3.3-70b-instruct (полный ID модели)")
            hint_text = (
                "⚠ Для OpenRouter в поле 'Название' нужно указать ПОЛНЫЙ идентификатор модели!\n"
                "Формат: provider/model-name\n"
                "Примеры:\n"
                "• meta-llama/llama-3.3-70b-instruct\n"
                "• openai/gpt-4\n"
                "• mistralai/mistral-large\n"
                "• qwen/qwen2.5-72b-instruct\n\n"
                "Список моделей: https://openrouter.ai/models"
            )
            # Можно добавить визуальную подсказку
        else:
            self.name_edit.setPlaceholderText("Например: GPT-4")
    
    def get_data(self) -> Dict:
        """Получить данные модели из формы."""
        return {
            "name": self.name_edit.text(),
            "api_url": self.api_url_edit.text(),
            "api_id": self.api_id_edit.text(),
            "model_type": self.model_type_edit.text(),
            "is_active": 1 if self.is_active_checkbox.isChecked() else 0
        }


class MainWindow(QMainWindow):
    """Главное окно приложения."""
    
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.model_handler = ModelHandler(self.db)
        self.logger = Logger()
        self.temp_results = []  # Временная таблица результатов в памяти
        self.send_thread = None
        
        self.init_ui()
        self.load_prompts()
        self.load_models()
        self.load_settings()
    
    def init_ui(self):
        """Инициализация интерфейса."""
        self.setWindowTitle("ChatList - Сравнение ответов нейросетей")
        self.setGeometry(100, 100, 1200, 800)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Создаем сплиттер для разделения на панели
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Левая панель: ввод промта и управление моделями
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        
        # Панель ввода промта
        prompt_group = QGroupBox("Ввод промта")
        prompt_layout = QVBoxLayout()
        
        # Поиск промтов
        search_prompt_layout = QHBoxLayout()
        search_prompt_layout.addWidget(QLabel("Поиск промтов:"))
        self.prompt_search_edit = QLineEdit()
        self.prompt_search_edit.setPlaceholderText("Поиск по промтам...")
        self.prompt_search_edit.textChanged.connect(self.filter_prompts)
        search_prompt_layout.addWidget(self.prompt_search_edit)
        prompt_layout.addLayout(search_prompt_layout)
        
        # Выбор сохраненного промта
        self.prompt_combo = QComboBox()
        self.prompt_combo.setEditable(True)
        self.prompt_combo.currentTextChanged.connect(self.on_prompt_changed)
        prompt_layout.addWidget(QLabel("Выбрать сохраненный промт:"))
        prompt_layout.addWidget(self.prompt_combo)
        
        # Поле ввода нового промта
        prompt_layout.addWidget(QLabel("Или ввести новый промт:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Введите ваш промт здесь...")
        self.prompt_edit.setMaximumHeight(150)
        self.prompt_edit.setToolTip("Введите текст запроса, который будет отправлен во все активные модели")
        prompt_layout.addWidget(self.prompt_edit)
        
        # Поле для тегов
        tags_layout = QHBoxLayout()
        tags_layout.addWidget(QLabel("Теги:"))
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("тег1, тег2, тег3")
        self.tags_edit.setToolTip("Введите теги через запятую для категоризации промта")
        tags_layout.addWidget(self.tags_edit)
        prompt_layout.addLayout(tags_layout)
        
        # Кнопки управления промтами
        prompt_buttons_layout = QHBoxLayout()
        self.send_button = QPushButton("Отправить запрос")
        self.send_button.clicked.connect(self.send_prompt)
        self.send_button.setToolTip("Отправить промт во все активные модели")
        self.save_prompt_button = QPushButton("Сохранить промт")
        self.save_prompt_button.clicked.connect(self.save_current_prompt)
        self.save_prompt_button.setToolTip("Сохранить текущий промт в базу данных")
        prompt_buttons_layout.addWidget(self.send_button)
        prompt_buttons_layout.addWidget(self.save_prompt_button)
        prompt_layout.addLayout(prompt_buttons_layout)
        
        prompt_group.setLayout(prompt_layout)
        left_layout.addWidget(prompt_group)
        
        # Панель управления моделями
        models_group = QGroupBox("Управление моделями")
        models_layout = QVBoxLayout()
        
        # Поиск моделей
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Поиск:"))
        self.model_search_edit = QLineEdit()
        self.model_search_edit.setPlaceholderText("Поиск по моделям...")
        self.model_search_edit.textChanged.connect(self.filter_models)
        search_layout.addWidget(self.model_search_edit)
        models_layout.addLayout(search_layout)
        
        # Таблица моделей
        self.models_table = QTableWidget()
        self.models_table.setColumnCount(4)
        self.models_table.setHorizontalHeaderLabels(["Активна", "Название", "Тип", "Действия"])
        self.models_table.horizontalHeader().setStretchLastSection(True)
        self.models_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.models_table.setSortingEnabled(True)  # Включить сортировку
        models_layout.addWidget(self.models_table)
        
        # Кнопки управления моделями
        model_buttons_layout = QHBoxLayout()
        self.add_model_button = QPushButton("Добавить модель")
        self.add_model_button.clicked.connect(self.add_model)
        self.add_model_button.setToolTip("Добавить новую модель нейросети")
        self.edit_model_button = QPushButton("Редактировать")
        self.edit_model_button.clicked.connect(self.edit_model)
        self.edit_model_button.setToolTip("Редактировать выбранную модель")
        self.delete_model_button = QPushButton("Удалить")
        self.delete_model_button.clicked.connect(self.delete_model)
        self.delete_model_button.setToolTip("Удалить выбранную модель")
        model_buttons_layout.addWidget(self.add_model_button)
        model_buttons_layout.addWidget(self.edit_model_button)
        model_buttons_layout.addWidget(self.delete_model_button)
        models_layout.addLayout(model_buttons_layout)
        
        models_group.setLayout(models_layout)
        left_layout.addWidget(models_group)
        
        # Кнопка настроек
        settings_button = QPushButton("Настройки")
        settings_button.clicked.connect(self.show_settings)
        left_layout.addWidget(settings_button)
        
        left_layout.addStretch()
        splitter.addWidget(left_panel)
        
        # Правая панель: результаты
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        
        results_group = QGroupBox("Результаты")
        results_layout = QVBoxLayout()
        
        # Индикатор загрузки
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        results_layout.addWidget(self.progress_bar)
        
        # Таблица результатов
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Выбрать", "Модель", "Ответ"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setWordWrap(True)  # Включить перенос текста
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)  # Включить сортировку
        # Настройка для многострочного отображения (максимум 10 строк)
        # Примерно 25 пикселей на строку, для 10 строк = 250 пикселей
        self.results_table.verticalHeader().setDefaultSectionSize(100)  # Минимальная высота строки
        self.results_table.verticalHeader().setMaximumSectionSize(250)  # Максимальная высота (10 строк)
        self.results_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)  # Автоматическая высота
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        results_layout.addWidget(self.results_table)
        
        # Кнопки управления результатами
        result_buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Сохранить выбранные")
        self.save_button.clicked.connect(self.save_selected_results)
        self.save_button.setToolTip("Сохранить отмеченные результаты в базу данных")
        self.new_request_button = QPushButton("Новый запрос")
        self.new_request_button.clicked.connect(self.new_request)
        self.new_request_button.setToolTip("Очистить текущие результаты и начать новый запрос")
        self.export_md_button = QPushButton("Экспорт Markdown")
        self.export_md_button.clicked.connect(lambda: self.export_results("md"))
        self.export_md_button.setToolTip("Экспортировать выбранные результаты в Markdown файл")
        self.export_json_button = QPushButton("Экспорт JSON")
        self.export_json_button.clicked.connect(lambda: self.export_results("json"))
        self.export_json_button.setToolTip("Экспортировать выбранные результаты в JSON файл")
        self.open_button = QPushButton("Открыть")
        self.open_button.clicked.connect(self.open_selected_result)
        self.open_button.setToolTip("Открыть выбранный ответ в форматированном Markdown")
        result_buttons_layout.addWidget(self.save_button)
        result_buttons_layout.addWidget(self.new_request_button)
        result_buttons_layout.addWidget(self.open_button)
        result_buttons_layout.addWidget(self.export_md_button)
        result_buttons_layout.addWidget(self.export_json_button)
        results_layout.addLayout(result_buttons_layout)
        
        results_group.setLayout(results_layout)
        right_layout.addWidget(results_group)
        
        splitter.addWidget(right_panel)
        
        # Установка пропорций сплиттера
        splitter.setSizes([400, 800])
        
        # Создание меню
        self.create_menu()
    
    def create_menu(self):
        """Создать меню приложения."""
        menubar = self.menuBar()
        
        # Меню Файл
        file_menu = menubar.addMenu("Файл")
        export_action = QAction("Экспорт результатов", self)
        export_action.triggered.connect(lambda: self.export_results("md"))
        file_menu.addAction(export_action)
        
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Меню Настройки
        settings_menu = menubar.addMenu("Настройки")
        settings_action = QAction("Настройки программы", self)
        settings_action.triggered.connect(self.show_settings)
        settings_menu.addAction(settings_action)
        
        # Меню Справка
        help_menu = menubar.addMenu("Справка")
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def load_prompts(self):
        """Загрузить список промтов в выпадающий список."""
        self.prompt_combo.clear()
        prompts = self.db.get_prompts()
        self.all_prompts = prompts  # Сохраняем для фильтрации
        for prompt in prompts:
            # Показываем первые 50 символов промта
            display_text = prompt["prompt"][:50] + ("..." if len(prompt["prompt"]) > 50 else "")
            self.prompt_combo.addItem(display_text, prompt["id"])
    
    def filter_prompts(self):
        """Фильтрация промтов по поисковому запросу."""
        query = self.prompt_search_edit.text()
        if not query:
            self.load_prompts()
            return
        
        prompts = self.db.search_prompts(query)
        self.prompt_combo.clear()
        for prompt in prompts:
            display_text = prompt["prompt"][:50] + ("..." if len(prompt["prompt"]) > 50 else "")
            self.prompt_combo.addItem(display_text, prompt["id"])
    
    def save_current_prompt(self):
        """Сохранить текущий промт в БД."""
        prompt_text = self.prompt_edit.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(
                self, 
                "Ошибка валидации", 
                "Введите промт для сохранения!\n\nПоле промта не может быть пустым."
            )
            return
        
        if len(prompt_text) < 3:
            QMessageBox.warning(
                self,
                "Ошибка валидации",
                "Промт слишком короткий!\n\nМинимальная длина промта - 3 символа."
            )
            return
        
        tags = self.tags_edit.text().strip()
        try:
            self.db.add_prompt(prompt_text, tags if tags else None)
            self.load_prompts()
            QMessageBox.information(self, "Успех", "Промт сохранен!")
            self.logger.log_info(f"Промт сохранен: {prompt_text[:50]}...")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить промт: {str(e)}")
            self.logger.log_error("Ошибка сохранения промта", e)
    
    def load_models(self):
        """Загрузить список моделей в таблицу."""
        models = self.db.get_models()
        self.models_table.setRowCount(len(models))
        
        for row, model in enumerate(models):
            # Чекбокс активности
            checkbox = QCheckBox()
            checkbox.setChecked(model["is_active"] == 1)
            checkbox.stateChanged.connect(
                lambda state, m_id=model["id"]: self.toggle_model_active(m_id, state)
            )
            self.models_table.setCellWidget(row, 0, checkbox)
            
            # Название
            self.models_table.setItem(row, 1, QTableWidgetItem(model["name"]))
            
            # Тип
            self.models_table.setItem(row, 2, QTableWidgetItem(model.get("model_type", "")))
            
            # Действия (заглушка, реальные действия через кнопки)
            self.models_table.setItem(row, 3, QTableWidgetItem(""))
    
    def filter_models(self):
        """Фильтрация моделей по поисковому запросу."""
        query = self.model_search_edit.text()
        if not query:
            self.load_models()
            return
        
        models = self.db.search_models(query)
        self.models_table.setRowCount(len(models))
        
        for row, model in enumerate(models):
            checkbox = QCheckBox()
            checkbox.setChecked(model["is_active"] == 1)
            checkbox.stateChanged.connect(
                lambda state, m_id=model["id"]: self.toggle_model_active(m_id, state)
            )
            self.models_table.setCellWidget(row, 0, checkbox)
            self.models_table.setItem(row, 1, QTableWidgetItem(model["name"]))
            self.models_table.setItem(row, 2, QTableWidgetItem(model.get("model_type", "")))
            self.models_table.setItem(row, 3, QTableWidgetItem(""))
    
    def toggle_model_active(self, model_id: int, state: int):
        """Переключить активность модели."""
        is_active = 1 if state == Qt.Checked else 0
        self.db.set_model_active(model_id, is_active)
    
    def on_prompt_changed(self, text: str):
        """Обработчик изменения выбранного промта."""
        index = self.prompt_combo.currentIndex()
        if index >= 0:
            prompt_id = self.prompt_combo.itemData(index)
            if prompt_id:
                prompt = self.db.get_prompt_by_id(prompt_id)
                if prompt:
                    self.prompt_edit.setText(prompt["prompt"])
                    self.tags_edit.setText(prompt.get("tags", ""))
    
    def send_prompt(self):
        """Отправить промт во все активные модели."""
        prompt_text = self.prompt_edit.toPlainText().strip()
        
        # Валидация ввода
        if not prompt_text:
            QMessageBox.warning(
                self, 
                "Ошибка валидации", 
                "Введите промт для отправки!\n\nПоле промта не может быть пустым."
            )
            return
        
        if len(prompt_text) < 3:
            QMessageBox.warning(
                self,
                "Ошибка валидации",
                "Промт слишком короткий!\n\nМинимальная длина промта - 3 символа."
            )
            return
        
        active_models = self.db.get_models(active_only=True)
        if not active_models:
            QMessageBox.warning(
                self, 
                "Ошибка", 
                "Нет активных моделей!\n\nДобавьте и активируйте хотя бы одну модель в панели управления моделями."
            )
            return
        
        # Очистка временной таблицы
        self.new_request()
        
        # Сохранение промта в БД
        tags = self.tags_edit.text().strip()
        prompt_id = self.db.add_prompt(prompt_text, tags if tags else None)
        
        # Обновление списка промтов
        self.load_prompts()
        
        # Показ индикатора загрузки
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Неопределенный прогресс
        self.send_button.setEnabled(False)
        
        # Логирование начала запроса
        self.logger.log_info(f"Отправка промта в {len(active_models)} активных моделей")
        
        # Запуск потока для отправки запросов
        # Передаем путь к БД и список моделей, чтобы создать новое соединение в потоке
        self.send_thread = SendPromptThread(self.db.db_path, active_models, prompt_text, self.logger)
        self.send_thread.result_received.connect(self.on_result_received)
        self.send_thread.finished.connect(self.on_send_finished)
        self.send_thread.start()
    
    def on_result_received(self, model: Dict, response: str, error: str):
        """Обработчик получения результата от модели."""
        # Логирование результата
        prompt_text = self.prompt_edit.toPlainText().strip()
        self.logger.log_request(model["name"], prompt_text, response, error)
        
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        # Чекбокс выбора
        checkbox = QCheckBox()
        self.results_table.setCellWidget(row, 0, checkbox)
        
        # Название модели
        model_name = model["name"]
        if error:
            model_name += " (ОШИБКА)"
        self.results_table.setItem(row, 1, QTableWidgetItem(model_name))
        
        # Ответ или ошибка (многострочный, максимум 10 строк)
        text = error if error else response
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        # Настройка для многострочного отображения
        item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        # Устанавливаем перенос текста для ячейки
        self.results_table.setItem(row, 2, item)
        # Автоматически подстраиваем высоту строки под содержимое (но не более 10 строк)
        self.results_table.resizeRowToContents(row)
        # Ограничиваем максимальную высоту строки до 250 пикселей (примерно 10 строк)
        if self.results_table.rowHeight(row) > 250:
            self.results_table.setRowHeight(row, 250)
        
        # Сохранение во временную таблицу
        self.temp_results.append({
            "model": model,
            "response": response,
            "error": error,
            "selected": False
        })
    
    def on_send_finished(self):
        """Обработчик завершения отправки запросов."""
        self.progress_bar.setVisible(False)
        self.send_button.setEnabled(True)
    
    def save_selected_results(self):
        """Сохранить выбранные результаты в БД."""
        if not self.temp_results:
            QMessageBox.information(
                self, 
                "Информация", 
                "Нет результатов для сохранения!\n\nСначала отправьте запрос и получите ответы от моделей."
            )
            return
        
        # Получаем текущий промт
        prompt_text = self.prompt_edit.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(
                self, 
                "Ошибка", 
                "Не найден промт для сохранения результатов!\n\nПромт должен быть введен или выбран из списка."
            )
            return
        
        # Находим ID промта
        prompts = self.db.get_prompts()
        prompt_id = None
        for prompt in prompts:
            if prompt["prompt"] == prompt_text:
                prompt_id = prompt["id"]
                break
        
        if not prompt_id:
            # Создаем новый промт
            tags = self.tags_edit.text().strip()
            prompt_id = self.db.add_prompt(prompt_text, tags if tags else None)
        
        # Сохраняем выбранные результаты
        saved_count = 0
        for row in range(self.results_table.rowCount()):
            checkbox = self.results_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                result_data = self.temp_results[row]
                if not result_data["error"]:
                    self.db.save_result(
                        prompt_id,
                        result_data["model"]["id"],
                        result_data["response"]
                    )
                    saved_count += 1
        
        if saved_count > 0:
            QMessageBox.information(self, "Успех", f"Сохранено результатов: {saved_count}")
        else:
            QMessageBox.warning(self, "Предупреждение", "Не выбрано ни одного результата!")
    
    def new_request(self):
        """Очистить временную таблицу результатов."""
        self.temp_results = []
        self.results_table.setRowCount(0)
        self.prompt_edit.clear()
        self.tags_edit.clear()
    
    def export_results(self, format_type: str = "md"):
        """Экспорт результатов в Markdown или JSON."""
        if not self.temp_results:
            QMessageBox.information(self, "Информация", "Нет результатов для экспорта!")
            return
        
        # Собираем выбранные результаты
        selected_results = []
        for row in range(self.results_table.rowCount()):
            checkbox = self.results_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                result_data = self.temp_results[row]
                selected_results.append({
                    "model": result_data["model"]["name"],
                    "response": result_data["response"],
                    "error": result_data["error"]
                })
        
        if not selected_results:
            QMessageBox.warning(self, "Предупреждение", "Не выбрано ни одного результата!")
            return
        
        # Выбор файла для сохранения
        if format_type == "md":
            filename, _ = QFileDialog.getSaveFileName(
                self, "Сохранить как Markdown", "", "Markdown Files (*.md);;All Files (*)"
            )
            if filename:
                self._export_to_markdown(selected_results, filename)
        else:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Сохранить как JSON", "", "JSON Files (*.json);;All Files (*)"
            )
            if filename:
                self._export_to_json(selected_results, filename)
    
    def _export_to_markdown(self, results: List[Dict], filename: str):
        """Экспорт результатов в Markdown."""
        prompt_text = self.prompt_edit.toPlainText().strip()
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"# Результаты сравнения моделей\n\n")
                f.write(f"**Промт:** {prompt_text}\n\n")
                f.write(f"**Дата:** {self.db.get_prompts()[0]['date'] if self.db.get_prompts() else 'N/A'}\n\n")
                f.write("---\n\n")
                
                for i, result in enumerate(results, 1):
                    f.write(f"## {i}. {result['model']}\n\n")
                    if result['error']:
                        f.write(f"**Ошибка:** {result['error']}\n\n")
                    else:
                        f.write(f"{result['response']}\n\n")
                    f.write("---\n\n")
            
            QMessageBox.information(self, "Успех", f"Результаты экспортированы в {filename}")
            self.logger.log_info(f"Экспорт результатов в Markdown: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать: {str(e)}")
            self.logger.log_error("Ошибка экспорта в Markdown", e)
    
    def _export_to_json(self, results: List[Dict], filename: str):
        """Экспорт результатов в JSON."""
        prompt_text = self.prompt_edit.toPlainText().strip()
        
        export_data = {
            "prompt": prompt_text,
            "results": results
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "Успех", f"Результаты экспортированы в {filename}")
            self.logger.log_info(f"Экспорт результатов в JSON: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать: {str(e)}")
            self.logger.log_error("Ошибка экспорта в JSON", e)
    
    def add_model(self):
        """Добавить новую модель."""
        dialog = ModelDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            
            # Валидация данных
            if not data["name"].strip():
                QMessageBox.warning(self, "Ошибка валидации", "Название модели не может быть пустым!")
                return
            
            if not data["api_url"].strip():
                QMessageBox.warning(self, "Ошибка валидации", "API URL не может быть пустым!")
                return
            
            if not data["api_id"].strip():
                QMessageBox.warning(self, "Ошибка валидации", "API ID (имя переменной .env) не может быть пустым!")
                return
            
            # Проверка формата URL
            api_url = data["api_url"].strip()
            if not (api_url.startswith("http://") or api_url.startswith("https://")):
                QMessageBox.warning(
                    self, 
                    "Ошибка валидации", 
                    "API URL должен начинаться с http:// или https://"
                )
                return
            
            # Специальная проверка для OpenRouter
            model_type = data["model_type"].strip().lower()
            if "openrouter" in model_type:
                correct_url = "https://openrouter.ai/api/v1/chat/completions"
                if api_url != correct_url and not api_url.endswith("/api/v1/chat/completions"):
                    reply = QMessageBox.warning(
                        self,
                        "Предупреждение",
                        f"Для OpenRouter рекомендуется использовать правильный API URL:\n\n"
                        f"{correct_url}\n\n"
                        f"Текущий URL: {api_url}\n\n"
                        f"Продолжить с текущим URL?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        return
            
            # Проверка формата API ID (не должно быть слэшей - это не имя модели)
            api_id = data["api_id"].strip()
            if "/" in api_id or "\\" in api_id:
                QMessageBox.warning(
                    self,
                    "Ошибка валидации",
                    "API ID не должен содержать слэши!\n\n"
                    "API ID - это имя переменной окружения из файла .env,\n"
                    "а не имя модели.\n\n"
                    "Примеры правильных значений:\n"
                    "• OPENROUTER_API_KEY\n"
                    "• OPENAI_API_KEY\n"
                    "• DEEPSEEK_API_KEY\n\n"
                    "Неправильно: meta-llama/llama-3.3-70b-instruct\n"
                    "Правильно: OPENROUTER_API_KEY (и в .env должно быть: OPENROUTER_API_KEY=ваш_ключ)"
                )
                return
            
            # Проверка для OpenRouter: название должно содержать слэш
            model_type = data["model_type"].strip().lower()
            model_name = data["name"].strip()
            if "openrouter" in model_type:
                if "/" not in model_name:
                    reply = QMessageBox.warning(
                        self,
                        "Предупреждение",
                        "Для OpenRouter в поле 'Название' нужно указать ПОЛНЫЙ идентификатор модели!\n\n"
                        "Формат: provider/model-name\n"
                        "Примеры:\n"
                        "• meta-llama/llama-3.3-70b-instruct\n"
                        "• openai/gpt-4\n"
                        "• mistralai/mistral-large\n\n"
                        "Если вы указали просто название (например, 'Llama 3.3 70B'),\n"
                        "замените его на полный идентификатор модели.\n\n"
                        "Список моделей: https://openrouter.ai/models\n\n"
                        "Продолжить с текущим названием?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        return
            
            # Проверка существования переменной окружения
            import os
            from dotenv import load_dotenv
            load_dotenv()
            
            api_key = os.getenv(api_id)
            if not api_key:
                reply = QMessageBox.warning(
                    self,
                    "Предупреждение",
                    f"Переменная окружения '{api_id}' не найдена в файле .env!\n\n"
                    "Убедитесь, что:\n"
                    f"1. Файл .env существует в корне проекта\n"
                    f"2. В файле .env есть строка: {api_id}=ваш_ключ\n\n"
                    "Продолжить добавление модели?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
            
            try:
                self.db.add_model(
                    data["name"].strip(),
                    data["api_url"].strip(),
                    data["api_id"].strip(),
                    data["model_type"].strip() if data["model_type"].strip() else None,
                    data["is_active"]
                )
                self.load_models()
                QMessageBox.information(self, "Успех", "Модель добавлена!")
                self.logger.log_info(f"Модель добавлена: {data['name']}")
            except Exception as e:
                error_msg = f"Не удалось добавить модель: {str(e)}"
                QMessageBox.critical(self, "Ошибка", error_msg)
                self.logger.log_error("Ошибка добавления модели", e)
    
    def edit_model(self):
        """Редактировать выбранную модель."""
        current_row = self.models_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите модель для редактирования!")
            return
        
        model_name = self.models_table.item(current_row, 1).text()
        models = self.db.get_models()
        model_data = None
        for model in models:
            if model["name"] == model_name:
                model_data = model
                break
        
        if not model_data:
            QMessageBox.warning(self, "Ошибка", "Модель не найдена!")
            return
        
        dialog = ModelDialog(self, model_data)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            try:
                self.db.update_model(
                    model_data["id"],
                    name=data["name"],
                    api_url=data["api_url"],
                    api_id=data["api_id"],
                    model_type=data["model_type"] if data["model_type"] else None,
                    is_active=data["is_active"]
                )
                self.load_models()
                QMessageBox.information(self, "Успех", "Модель обновлена!")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось обновить модель: {str(e)}")
    
    def delete_model(self):
        """Удалить выбранную модель."""
        current_row = self.models_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите модель для удаления!")
            return
        
        model_name = self.models_table.item(current_row, 1).text()
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить модель '{model_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            models = self.db.get_models()
            for model in models:
                if model["name"] == model_name:
                    try:
                        self.db.delete_model(model["id"])
                        self.load_models()
                        QMessageBox.information(self, "Успех", "Модель удалена!")
                    except Exception as e:
                        QMessageBox.critical(self, "Ошибка", f"Не удалось удалить модель: {str(e)}")
                    break
    
    def load_settings(self):
        """Загрузить настройки из БД."""
        timeout = self.db.get_setting("timeout", "30")
        # Можно добавить применение настроек к интерфейсу
    
    def show_settings(self):
        """Показать диалог настроек."""
        dialog = SettingsDialog(self, self.db)
        dialog.exec_()
    
    def show_about(self):
        """Показать информацию о программе."""
        QMessageBox.about(
            self,
            "О программе ChatList",
            "ChatList v1.0\n\n"
            "Приложение для сравнения ответов различных нейросетей.\n\n"
            "Позволяет отправлять один промт в несколько моделей\n"
            "и сравнивать их ответы."
        )
    
    def open_selected_result(self):
        """Открыть выбранный ответ в форматированном Markdown."""
        current_row = self.results_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите строку с результатом для просмотра!")
            return
        
        if current_row >= len(self.temp_results):
            QMessageBox.warning(self, "Ошибка", "Результат не найден!")
            return
        
        result_data = self.temp_results[current_row]
        model_name = result_data["model"]["name"]
        response_text = result_data["response"] if not result_data["error"] else result_data["error"]
        
        if not response_text:
            QMessageBox.warning(self, "Предупреждение", "Ответ пуст!")
            return
        
        # Открываем диалог с markdown
        dialog = MarkdownViewDialog(self, model_name, response_text)
        dialog.exec_()
    
    def closeEvent(self, event):
        """Обработчик закрытия окна."""
        if self.send_thread and self.send_thread.isRunning():
            self.send_thread.terminate()
            self.send_thread.wait()
        
        self.model_handler.close()
        self.db.close()
        event.accept()


class MarkdownViewDialog(QDialog):
    """Диалог для просмотра ответа в форматированном Markdown."""
    
    def __init__(self, parent=None, model_name: str = "", content: str = ""):
        super().__init__(parent)
        self.setWindowTitle(f"Ответ: {model_name}")
        self.setModal(True)
        self.resize(800, 600)
        self.init_ui(model_name, content)
    
    def init_ui(self, model_name: str, content: str):
        """Инициализация интерфейса диалога."""
        layout = QVBoxLayout()
        
        # Заголовок с названием модели
        header_label = QLabel(f"<h2>Ответ от: {model_name}</h2>")
        layout.addWidget(header_label)
        
        # Текстовое поле с поддержкой Markdown
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        # Устанавливаем markdown контент
        self.text_edit.setMarkdown(content)
        # Настройка шрифта для лучшей читаемости
        font = self.text_edit.font()
        font.setPointSize(10)
        self.text_edit.setFont(font)
        layout.addWidget(self.text_edit)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        copy_button = QPushButton("Копировать")
        copy_button.clicked.connect(self.copy_to_clipboard)
        buttons_layout.addWidget(copy_button)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        buttons_layout.addWidget(buttons)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def copy_to_clipboard(self):
        """Копировать содержимое в буфер обмена."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        QMessageBox.information(self, "Успех", "Текст скопирован в буфер обмена!")


class SettingsDialog(QDialog):
    """Диалог настроек программы."""
    
    def __init__(self, parent=None, db: Database = None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса диалога."""
        layout = QFormLayout()
        
        self.timeout_edit = QLineEdit()
        timeout_value = self.db.get_setting("timeout", "30")
        self.timeout_edit.setText(timeout_value)
        layout.addRow("Таймаут запросов (сек):", self.timeout_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def save_settings(self):
        """Сохранить настройки."""
        try:
            timeout = int(self.timeout_edit.text())
            if timeout < 1:
                raise ValueError("Таймаут должен быть больше 0")
            
            self.db.set_setting("timeout", str(timeout))
            QMessageBox.information(self, "Успех", "Настройки сохранены!")
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", f"Неверное значение: {str(e)}")


def main():
    """Главная функция приложения."""
    app = QApplication(sys.argv)
    
    # Установка стиля приложения
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
