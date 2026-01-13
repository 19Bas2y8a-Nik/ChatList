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
    QFileDialog, QMenuBar, QMenu, QAction, QScrollArea, QRadioButton,
    QButtonGroup, QSpinBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from typing import List, Dict, Optional
import json

from db import Database
from models import ModelHandler, APIError
from logger import Logger
from prompt_improver import PromptImprover
from version import __version__


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


class ImprovePromptThread(QThread):
    """Поток для асинхронного улучшения промта."""
    
    result_received = pyqtSignal(dict)  # result dictionary
    error_occurred = pyqtSignal(str)  # error message
    finished = pyqtSignal()
    
    def __init__(self, db_path: str, model: Dict, original_prompt: str, 
                 improvement_type: str = "general", logger=None):
        super().__init__()
        self.db_path = db_path
        self.model = model
        self.original_prompt = original_prompt
        self.improvement_type = improvement_type
        self.logger = logger
    
    def run(self):
        """Запуск улучшения промта."""
        # Создаем новое соединение с БД в рабочем потоке
        from db import Database
        from prompt_improver import PromptImprover
        
        db = Database(self.db_path)
        improver = PromptImprover(db)
        
        try:
            result = improver.improve_prompt(
                self.original_prompt,
                self.model,
                self.improvement_type
            )
            self.result_received.emit(result)
            
            if self.logger:
                self.logger.log_info(
                    f"Промт улучшен с помощью модели {self.model.get('name', 'Unknown')}"
                )
        except Exception as e:
            error_msg = str(e)
            self.error_occurred.emit(error_msg)
            
            if self.logger:
                self.logger.log_error("Ошибка при улучшении промта", e)
        finally:
            improver.close()
            db.close()
            self.finished.emit()


class PromptImprovementDialog(QDialog):
    """Диалог для улучшения промтов."""
    
    def __init__(self, parent=None, original_prompt: str = "", db: Database = None, 
                 logger: Logger = None):
        super().__init__(parent)
        self.original_prompt = original_prompt
        self.db = db or Database()
        self.logger = logger
        self.improvement_thread = None
        self.selected_text = None
        self.db_path = self.db.db_path
        
        self.setWindowTitle("Улучшение промта с помощью AI")
        self.setModal(True)
        self.resize(800, 700)
        self.init_ui()
        self.load_models()
    
    def init_ui(self):
        """Инициализация интерфейса диалога."""
        layout = QVBoxLayout()
        
        # Выбор модели
        model_group = QGroupBox("Выбор модели для улучшения")
        model_layout = QVBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.setToolTip("Выберите модель для улучшения промта")
        model_layout.addWidget(QLabel("Модель:"))
        model_layout.addWidget(self.model_combo)
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)
        
        # Тип улучшения
        type_group = QGroupBox("Тип улучшения")
        type_layout = QVBoxLayout()
        self.type_button_group = QButtonGroup(self)
        
        self.type_general = QRadioButton("Общее улучшение")
        self.type_general.setChecked(True)
        self.type_general.setToolTip("Общее улучшение промта для любой задачи")
        self.type_button_group.addButton(self.type_general, 0)
        type_layout.addWidget(self.type_general)
        
        self.type_code = QRadioButton("Для программирования")
        self.type_code.setToolTip("Специализированное улучшение для задач программирования")
        self.type_button_group.addButton(self.type_code, 1)
        type_layout.addWidget(self.type_code)
        
        self.type_analysis = QRadioButton("Для анализа")
        self.type_analysis.setToolTip("Специализированное улучшение для аналитических задач")
        self.type_button_group.addButton(self.type_analysis, 2)
        type_layout.addWidget(self.type_analysis)
        
        self.type_creative = QRadioButton("Для творческих задач")
        self.type_creative.setToolTip("Специализированное улучшение для творческих задач")
        self.type_button_group.addButton(self.type_creative, 3)
        type_layout.addWidget(self.type_creative)
        
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # Исходный промт
        original_group = QGroupBox("Исходный промт")
        original_layout = QVBoxLayout()
        self.original_text = QTextEdit()
        self.original_text.setPlainText(self.original_prompt)
        self.original_text.setReadOnly(True)
        self.original_text.setMaximumHeight(100)
        self.original_text.setToolTip("Исходный промт (только для чтения)")
        original_layout.addWidget(self.original_text)
        original_group.setLayout(original_layout)
        layout.addWidget(original_group)
        
        # Кнопка улучшения
        improve_button = QPushButton("Улучшить промт")
        improve_button.clicked.connect(self.start_improvement)
        improve_button.setToolTip("Начать улучшение промта с помощью выбранной модели")
        layout.addWidget(improve_button)
        
        # Индикатор загрузки
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # Неопределенный прогресс
        layout.addWidget(self.progress_bar)
        
        # Результаты
        results_group = QGroupBox("Результаты улучшения")
        results_layout = QVBoxLayout()
        
        # Улучшенная версия
        improved_label = QLabel("Улучшенная версия:")
        results_layout.addWidget(improved_label)
        self.improved_text = QTextEdit()
        self.improved_text.setReadOnly(True)
        self.improved_text.setMaximumHeight(120)
        self.improved_text.setPlaceholderText("Здесь появится улучшенная версия промта...")
        results_layout.addWidget(self.improved_text)
        
        # Кнопка подстановки улучшенной версии
        self.use_improved_button = QPushButton("Подставить улучшенную версию")
        self.use_improved_button.clicked.connect(lambda: self.select_text("improved"))
        self.use_improved_button.setEnabled(False)
        self.use_improved_button.setToolTip("Подставить улучшенную версию в поле ввода")
        results_layout.addWidget(self.use_improved_button)
        
        # Кнопка копирования улучшенной версии
        copy_improved_button = QPushButton("Копировать")
        copy_improved_button.clicked.connect(lambda: self.copy_to_clipboard("improved"))
        copy_improved_button.setToolTip("Копировать улучшенную версию в буфер обмена")
        results_layout.addWidget(copy_improved_button)
        
        results_layout.addWidget(QLabel(""))  # Разделитель
        
        # Альтернативные варианты
        variants_label = QLabel("Альтернативные варианты:")
        results_layout.addWidget(variants_label)
        self.variants_widget = QWidget()
        self.variants_layout = QVBoxLayout()
        self.variants_widget.setLayout(self.variants_layout)
        self.variants_scroll = QScrollArea()
        self.variants_scroll.setWidget(self.variants_widget)
        self.variants_scroll.setWidgetResizable(True)
        self.variants_scroll.setMaximumHeight(200)
        results_layout.addWidget(self.variants_scroll)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # Объяснение
        explanation_label = QLabel("Объяснение улучшений:")
        layout.addWidget(explanation_label)
        self.explanation_text = QTextEdit()
        self.explanation_text.setReadOnly(True)
        self.explanation_text.setMaximumHeight(80)
        self.explanation_text.setPlaceholderText("Здесь появится объяснение улучшений...")
        layout.addWidget(self.explanation_text)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        ok_button.setText("Подставить выбранный")
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def load_models(self):
        """Загрузить список активных моделей."""
        models = self.db.get_models(active_only=True)
        self.model_combo.clear()
        
        for model in models:
            self.model_combo.addItem(model["name"], model)
        
        if self.model_combo.count() == 0:
            self.model_combo.addItem("Нет активных моделей", None)
    
    def get_improvement_type(self) -> str:
        """Получить выбранный тип улучшения."""
        if self.type_code.isChecked():
            return "code"
        elif self.type_analysis.isChecked():
            return "analysis"
        elif self.type_creative.isChecked():
            return "creative"
        else:
            return "general"
    
    def start_improvement(self):
        """Начать улучшение промта."""
        original = self.original_text.toPlainText().strip()
        if not original:
            QMessageBox.warning(self, "Ошибка", "Исходный промт не может быть пустым!")
            return
        
        model_data = self.model_combo.currentData()
        if not model_data:
            QMessageBox.warning(self, "Ошибка", "Выберите модель для улучшения!")
            return
        
        improvement_type = self.get_improvement_type()
        
        # Блокируем UI
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        # Очищаем предыдущие результаты
        self.improved_text.clear()
        self.explanation_text.clear()
        self.clear_variants()
        
        # Создаем поток
        self.improvement_thread = ImprovePromptThread(
            self.db_path,
            model_data,
            original,
            improvement_type,
            self.logger
        )
        self.improvement_thread.result_received.connect(self.on_result_received)
        self.improvement_thread.error_occurred.connect(self.on_error_occurred)
        self.improvement_thread.finished.connect(self.on_finished)
        self.improvement_thread.start()
    
    def on_result_received(self, result: Dict):
        """Обработчик получения результата."""
        # Улучшенная версия
        improved = result.get("improved", "")
        self.improved_text.setPlainText(improved)
        self.use_improved_button.setEnabled(True)
        
        # Объяснение
        explanation = result.get("explanation", "")
        self.explanation_text.setPlainText(explanation)
        
        # Варианты
        variants = result.get("variants", [])
        self.display_variants(variants)
    
    def display_variants(self, variants: List[str]):
        """Отобразить альтернативные варианты."""
        self.clear_variants()
        
        for i, variant in enumerate(variants, 1):
            variant_group = QGroupBox(f"Вариант {i}")
            variant_layout = QVBoxLayout()
            
            variant_text = QTextEdit()
            variant_text.setPlainText(variant)
            variant_text.setReadOnly(True)
            variant_text.setMaximumHeight(80)
            variant_layout.addWidget(variant_text)
            
            buttons_layout = QHBoxLayout()
            use_button = QPushButton("Подставить")
            use_button.clicked.connect(
                lambda checked, text=variant: self.select_text("variant", text)
            )
            use_button.setToolTip(f"Подставить вариант {i} в поле ввода")
            buttons_layout.addWidget(use_button)
            
            copy_button = QPushButton("Копировать")
            copy_button.clicked.connect(
                lambda checked, text=variant: self.copy_to_clipboard("variant", text)
            )
            copy_button.setToolTip(f"Копировать вариант {i} в буфер обмена")
            buttons_layout.addWidget(copy_button)
            
            variant_layout.addLayout(buttons_layout)
            variant_group.setLayout(variant_layout)
            self.variants_layout.addWidget(variant_group)
    
    def clear_variants(self):
        """Очистить список вариантов."""
        while self.variants_layout.count():
            item = self.variants_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def select_text(self, text_type: str, text: str = None):
        """Выбрать текст для подстановки."""
        if text_type == "improved":
            self.selected_text = self.improved_text.toPlainText()
        elif text_type == "variant" and text:
            self.selected_text = text
        else:
            return
        
        # Закрываем диалог с результатом
        self.accept()
    
    def copy_to_clipboard(self, text_type: str, text: str = None):
        """Копировать текст в буфер обмена."""
        from PyQt5.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        
        if text_type == "improved":
            clipboard.setText(self.improved_text.toPlainText())
        elif text_type == "variant" and text:
            clipboard.setText(text)
        else:
            return
        
        QMessageBox.information(self, "Скопировано", "Текст скопирован в буфер обмена!")
    
    def on_error_occurred(self, error_msg: str):
        """Обработчик ошибки."""
        QMessageBox.critical(self, "Ошибка", f"Не удалось улучшить промт:\n\n{error_msg}")
    
    def on_finished(self):
        """Обработчик завершения работы потока."""
        self.progress_bar.setVisible(False)
        self.improvement_thread = None
    
    def get_selected_text(self) -> Optional[str]:
        """Получить выбранный текст."""
        return self.selected_text


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
        # Изменяем текст кнопки OK на "Сохранить"
        ok_button = buttons.button(QDialogButtonBox.Ok)
        ok_button.setText("Сохранить")
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
        
        # Логирование версии при старте
        self.logger.log_info(f"ChatList v{__version__} запущен")
        
        self.init_ui()
        self.load_prompts()
        self.load_settings()
    
    def init_ui(self):
        """Инициализация интерфейса."""
        self.setWindowTitle(f"ChatList v{__version__} - Сравнение ответов нейросетей")
        self.setGeometry(100, 100, 1200, 800)
        
        # Установка иконки приложения
        try:
            icon = QIcon('app.ico')
            if not icon.isNull():
                self.setWindowIcon(icon)
        except Exception:
            # Если иконка не найдена, просто пропускаем
            pass
        
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
        
        # Кнопки отправки и улучшения
        buttons_layout = QHBoxLayout()
        self.send_button = QPushButton("Отправить запрос")
        self.send_button.clicked.connect(self.send_prompt)
        self.send_button.setToolTip("Отправить промт во все активные модели")
        buttons_layout.addWidget(self.send_button)
        
        self.improve_button = QPushButton("Улучшить промт")
        self.improve_button.clicked.connect(self.open_improve_dialog)
        self.improve_button.setToolTip("Улучшить промт с помощью AI-ассистента")
        buttons_layout.addWidget(self.improve_button)
        
        prompt_layout.addLayout(buttons_layout)
        
        prompt_group.setLayout(prompt_layout)
        left_layout.addWidget(prompt_group)
        
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
        self.view_saved_button = QPushButton("Просмотр сохраненных")
        self.view_saved_button.clicked.connect(self.view_saved_results)
        self.view_saved_button.setToolTip("Просмотреть сохраненные результаты из базы данных")
        result_buttons_layout.addWidget(self.save_button)
        result_buttons_layout.addWidget(self.new_request_button)
        result_buttons_layout.addWidget(self.open_button)
        result_buttons_layout.addWidget(self.view_saved_button)
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
        
        file_menu.addSeparator()
        
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Меню Промты
        prompts_menu = menubar.addMenu("Промты")
        view_prompts_action = QAction("Просмотр промтов", self)
        view_prompts_action.setShortcut("Ctrl+P")
        view_prompts_action.triggered.connect(self.view_prompts)
        prompts_menu.addAction(view_prompts_action)
        
        # Меню Модели
        models_menu = menubar.addMenu("Модели")
        view_models_action = QAction("Просмотр моделей", self)
        view_models_action.setShortcut("Ctrl+M")
        view_models_action.triggered.connect(self.view_models)
        models_menu.addAction(view_models_action)
        
        # Меню Результаты
        results_menu = menubar.addMenu("Результаты")
        view_results_action = QAction("Просмотр результатов", self)
        view_results_action.setShortcut("Ctrl+R")
        view_results_action.triggered.connect(self.view_saved_results)
        results_menu.addAction(view_results_action)
        
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
    
    def on_prompt_changed(self, text: str):
        """Обработчик изменения выбранного промта."""
        index = self.prompt_combo.currentIndex()
        if index >= 0:
            prompt_id = self.prompt_combo.itemData(index)
            if prompt_id:
                prompt = self.db.get_prompt_by_id(prompt_id)
                if prompt:
                    self.prompt_edit.setText(prompt["prompt"])
    
    def open_improve_dialog(self):
        """Открыть диалог улучшения промта."""
        original_prompt = self.prompt_edit.toPlainText().strip()
        
        if not original_prompt:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Поле промта пустое!\n\nВведите промт перед улучшением."
            )
            return
        
        # Проверяем наличие активных моделей
        active_models = self.db.get_models(active_only=True)
        if not active_models:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Нет активных моделей!\n\nДобавьте и активируйте хотя бы одну модель для улучшения промта."
            )
            return
        
        # Создаем и открываем диалог
        dialog = PromptImprovementDialog(
            parent=self,
            original_prompt=original_prompt,
            db=self.db,
            logger=self.logger
        )
        
        if dialog.exec_() == QDialog.Accepted:
            selected_text = dialog.get_selected_text()
            if selected_text:
                # Подставляем выбранный текст в поле ввода
                self.prompt_edit.setPlainText(selected_text)
                self.logger.log_info("Улучшенный промт подставлен в поле ввода")
    
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
                "Нет активных моделей!\n\nДобавьте и активируйте хотя бы одну модель через меню 'Модели'."
            )
            return
        
        # Очистка временной таблицы
        self.new_request()
        
        # Показ индикатора загрузки
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Неопределенный прогресс
        self.send_button.setEnabled(False)
        
        # Логирование начала запроса
        self.logger.log_info(f"Отправка промта в {len(active_models)} активных моделей")
        
        # Примечание: промт НЕ сохраняется автоматически при отправке.
        # Он будет сохранен только при явном сохранении через диалог "Промты"
        # или при сохранении результатов (в методе save_selected_results)
        
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
            # Создаем новый промт (без тегов, они будут добавлены позже в диалоге промтов)
            prompt_id = self.db.add_prompt(prompt_text, None)
        
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
    
    def load_settings(self):
        """Загрузить настройки из БД."""
        timeout = self.db.get_setting("timeout", "30")
        
        # Загрузка темы
        theme = self.db.get_setting("theme", "light")
        self.apply_theme(theme)
        
        # Загрузка размера шрифта
        font_size_str = self.db.get_setting("font_size", "10")
        try:
            font_size = int(font_size_str)
            self.apply_font_size(font_size)
        except (ValueError, TypeError):
            pass
    
    def apply_theme(self, theme: str):
        """
        Применить тему к приложению.
        
        Args:
            theme: Название темы ("light" или "dark")
        """
        app = QApplication.instance()
        if not app:
            return
        
        if theme == "dark":
            # Темная тема
            dark_stylesheet = """
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QTextEdit, QLineEdit, QComboBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
            }
            QPushButton {
                background-color: #404040;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #353535;
            }
            QTableWidget {
                background-color: #3c3c3c;
                color: #ffffff;
                gridline-color: #555555;
            }
            QHeaderView::section {
                background-color: #404040;
                color: #ffffff;
                padding: 5px;
                border: 1px solid #555555;
            }
            QGroupBox {
                color: #ffffff;
                border: 1px solid #555555;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QMenuBar {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QMenuBar::item:selected {
                background-color: #404040;
            }
            QMenu {
                background-color: #3c3c3c;
                color: #ffffff;
            }
            QMenu::item:selected {
                background-color: #505050;
            }
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 3px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
            QScrollBar:vertical {
                background-color: #3c3c3c;
                width: 12px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #666666;
            }
            """
            app.setStyleSheet(dark_stylesheet)
        else:
            # Светлая тема (по умолчанию)
            app.setStyleSheet("")
    
    def apply_font_size(self, font_size: int):
        """
        Применить размер шрифта к панелям интерфейса.
        
        Args:
            font_size: Размер шрифта в пунктах
        """
        font = QFont()
        font.setPointSize(font_size)
        
        # Применяем шрифт к основным виджетам
        self.prompt_edit.setFont(font)
        self.results_table.setFont(font)
        
        # Применяем к другим текстовым виджетам, если они есть
        for widget in self.findChildren(QTextEdit):
            widget.setFont(font)
        for widget in self.findChildren(QLineEdit):
            widget.setFont(font)
        for widget in self.findChildren(QComboBox):
            widget.setFont(font)
    
    def show_settings(self):
        """Показать диалог настроек."""
        dialog = SettingsDialog(self, self.db)
        if dialog.exec_() == QDialog.Accepted:
            # Перезагружаем настройки после сохранения
            self.load_settings()
    
    def show_about(self):
        """Показать информацию о программе."""
        about_text = f"""
        <h2>ChatList v{__version__}</h2>
        <p><b>Приложение для сравнения ответов различных нейросетей</b></p>
        <p>ChatList позволяет отправлять один и тот же промт в несколько нейросетей и сравнивать их ответы в удобном интерфейсе.</p>
        <hr>
        <p><b>Основные возможности:</b></p>
        <ul>
            <li>Отправка промта в несколько моделей одновременно</li>
            <li>Сравнение ответов в табличном виде</li>
            <li>Сохранение выбранных результатов в базу данных</li>
            <li>Улучшение промтов с помощью AI-ассистента</li>
            <li>Экспорт результатов в Markdown и JSON</li>
            <li>Настройка темы и размера шрифта</li>
        </ul>
        <hr>
        <p><b>Технологии:</b></p>
        <p>Python, PyQt5, SQLite</p>
        <hr>
        <p>© 2024 ChatList</p>
        """
        QMessageBox.about(self, "О программе ChatList", about_text)
    
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
    
    def view_prompts(self):
        """Просмотр промтов из базы данных."""
        dialog = PromptsDialog(self, self.db)
        dialog.exec_()
        # Обновляем список промтов после возможных изменений
        self.load_prompts()
    
    def view_models(self):
        """Просмотр моделей из базы данных."""
        dialog = ModelsDialog(self, self.db)
        dialog.exec_()
    
    def view_saved_results(self):
        """Просмотр сохраненных результатов из базы данных."""
        dialog = SavedResultsDialog(self, self.db)
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


class SavedResultsDialog(QDialog):
    """Диалог для просмотра сохраненных результатов."""
    
    def __init__(self, parent=None, db: Database = None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Сохраненные результаты")
        self.setModal(True)
        self.resize(900, 600)
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса диалога."""
        layout = QVBoxLayout()
        
        # Поиск
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по промтам или ответам...")
        self.search_edit.textChanged.connect(self.filter_results)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)
        
        # Таблица результатов
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Дата", "Промт", "Модель", "Ответ"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setWordWrap(True)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setSortingEnabled(True)
        self.results_table.verticalHeader().setDefaultSectionSize(100)
        self.results_table.verticalHeader().setMaximumSectionSize(250)
        self.results_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.results_table.itemDoubleClicked.connect(self.open_result)
        layout.addWidget(self.results_table)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        self.open_button = QPushButton("Открыть")
        self.open_button.clicked.connect(self.open_selected_result)
        self.open_button.setToolTip("Открыть выбранный результат в форматированном Markdown")
        self.delete_button = QPushButton("Удалить")
        self.delete_button.clicked.connect(self.delete_selected_result)
        self.delete_button.setToolTip("Удалить выбранный результат из базы данных")
        buttons_layout.addWidget(self.open_button)
        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addStretch()
        
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons_layout.addWidget(buttons)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        
        # Загружаем результаты
        self.load_results()
    
    def load_results(self):
        """Загрузить сохраненные результаты из базы данных."""
        results = self.db.get_results()
        self.all_results = results
        
        # Получаем информацию о промтах и моделях
        prompts = {p["id"]: p for p in self.db.get_prompts()}
        models = {m["id"]: m for m in self.db.get_models()}
        
        self.results_table.setRowCount(len(results))
        
        for row, result in enumerate(results):
            # Дата
            saved_at = result.get("saved_at", "")
            self.results_table.setItem(row, 0, QTableWidgetItem(saved_at))
            
            # Промт
            prompt_id = result.get("prompt_id")
            prompt_text = prompts.get(prompt_id, {}).get("prompt", "Неизвестный промт")
            prompt_display = prompt_text[:50] + ("..." if len(prompt_text) > 50 else "")
            prompt_item = QTableWidgetItem(prompt_display)
            prompt_item.setToolTip(prompt_text)
            prompt_item.setData(Qt.UserRole, result)  # Сохраняем полные данные результата
            self.results_table.setItem(row, 1, prompt_item)
            
            # Модель
            model_id = result.get("model_id")
            model_name = models.get(model_id, {}).get("name", "Неизвестная модель")
            self.results_table.setItem(row, 2, QTableWidgetItem(model_name))
            
            # Ответ
            response = result.get("response", "")
            response_display = response[:100] + ("..." if len(response) > 100 else "")
            response_item = QTableWidgetItem(response_display)
            response_item.setToolTip(response)
            response_item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
            self.results_table.setItem(row, 3, response_item)
    
    def filter_results(self):
        """Фильтрация результатов по поисковому запросу."""
        query = self.search_edit.text().lower()
        if not query:
            self.load_results()
            return
        
        # Фильтруем результаты
        filtered = []
        prompts = {p["id"]: p for p in self.db.get_prompts()}
        
        for result in self.all_results:
            prompt_id = result.get("prompt_id")
            prompt_text = prompts.get(prompt_id, {}).get("prompt", "").lower()
            response = result.get("response", "").lower()
            
            if query in prompt_text or query in response:
                filtered.append(result)
        
        # Обновляем таблицу
        models = {m["id"]: m for m in self.db.get_models()}
        self.results_table.setRowCount(len(filtered))
        
        for row, result in enumerate(filtered):
            saved_at = result.get("saved_at", "")
            self.results_table.setItem(row, 0, QTableWidgetItem(saved_at))
            
            prompt_id = result.get("prompt_id")
            prompt_text = prompts.get(prompt_id, {}).get("prompt", "Неизвестный промт")
            prompt_display = prompt_text[:50] + ("..." if len(prompt_text) > 50 else "")
            prompt_item = QTableWidgetItem(prompt_display)
            prompt_item.setToolTip(prompt_text)
            prompt_item.setData(Qt.UserRole, result)
            self.results_table.setItem(row, 1, prompt_item)
            
            model_id = result.get("model_id")
            model_name = models.get(model_id, {}).get("name", "Неизвестная модель")
            self.results_table.setItem(row, 2, QTableWidgetItem(model_name))
            
            response = result.get("response", "")
            response_display = response[:100] + ("..." if len(response) > 100 else "")
            response_item = QTableWidgetItem(response_display)
            response_item.setToolTip(response)
            response_item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
            self.results_table.setItem(row, 3, response_item)
    
    def open_result(self, item):
        """Открыть результат при двойном клике."""
        self.open_selected_result()
    
    def open_selected_result(self):
        """Открыть выбранный результат в форматированном Markdown."""
        current_row = self.results_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите строку с результатом!")
            return
        
        prompt_item = self.results_table.item(current_row, 1)
        if not prompt_item:
            return
        
        result = prompt_item.data(Qt.UserRole)
        if not result:
            return
        
        # Получаем информацию о модели
        models = {m["id"]: m for m in self.db.get_models()}
        model_id = result.get("model_id")
        model_name = models.get(model_id, {}).get("name", "Неизвестная модель")
        response_text = result.get("response", "")
        
        if not response_text:
            QMessageBox.warning(self, "Предупреждение", "Ответ пуст!")
            return
        
        # Открываем диалог с markdown
        dialog = MarkdownViewDialog(self, model_name, response_text)
        dialog.exec_()
    
    def delete_selected_result(self):
        """Удалить выбранный результат из базы данных."""
        current_row = self.results_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите строку с результатом для удаления!")
            return
        
        prompt_item = self.results_table.item(current_row, 1)
        if not prompt_item:
            return
        
        result = prompt_item.data(Qt.UserRole)
        if not result:
            return
        
        result_id = result.get("id")
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Удалить выбранный результат из базы данных?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_result(result_id)
                QMessageBox.information(self, "Успех", "Результат удален!")
                self.load_results()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить результат: {str(e)}")


class PromptsDialog(QDialog):
    """Диалог для просмотра и управления промтами."""
    
    def __init__(self, parent=None, db: Database = None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Промты")
        self.setModal(True)
        self.resize(900, 600)
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса диалога."""
        layout = QVBoxLayout()
        
        # Поиск
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по промтам или тегам...")
        self.search_edit.textChanged.connect(self.filter_prompts)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)
        
        # Таблица промтов
        self.prompts_table = QTableWidget()
        self.prompts_table.setColumnCount(4)
        self.prompts_table.setHorizontalHeaderLabels(["ID", "Дата", "Промт", "Теги"])
        self.prompts_table.horizontalHeader().setStretchLastSection(True)
        self.prompts_table.setWordWrap(True)
        self.prompts_table.setAlternatingRowColors(True)
        self.prompts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.prompts_table.setSortingEnabled(True)
        self.prompts_table.verticalHeader().setDefaultSectionSize(100)
        self.prompts_table.verticalHeader().setMaximumSectionSize(250)
        self.prompts_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        header = self.prompts_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.prompts_table.itemDoubleClicked.connect(self.edit_selected_prompt)
        layout.addWidget(self.prompts_table)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        self.add_button = QPushButton("Добавить промт")
        self.add_button.clicked.connect(self.add_new_prompt)
        self.add_button.setToolTip("Добавить новый промт в базу данных")
        self.edit_button = QPushButton("Редактировать")
        self.edit_button.clicked.connect(self.edit_selected_prompt)
        self.edit_button.setToolTip("Редактировать выбранный промт")
        self.delete_button = QPushButton("Удалить")
        self.delete_button.clicked.connect(self.delete_selected_prompt)
        self.delete_button.setToolTip("Удалить выбранный промт из базы данных")
        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.edit_button)
        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addStretch()
        
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons_layout.addWidget(buttons)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        
        # Загружаем промты
        self.load_prompts()
    
    def load_prompts(self):
        """Загрузить промты из базы данных."""
        prompts = self.db.get_prompts()
        self.all_prompts = prompts
        
        self.prompts_table.setRowCount(len(prompts))
        
        for row, prompt in enumerate(prompts):
            # ID
            self.prompts_table.setItem(row, 0, QTableWidgetItem(str(prompt["id"])))
            
            # Дата
            self.prompts_table.setItem(row, 1, QTableWidgetItem(prompt.get("date", "")))
            
            # Промт
            prompt_text = prompt.get("prompt", "")
            prompt_item = QTableWidgetItem(prompt_text)
            prompt_item.setToolTip(prompt_text)
            prompt_item.setData(Qt.UserRole, prompt)  # Сохраняем полные данные промта
            self.prompts_table.setItem(row, 2, prompt_item)
            
            # Теги
            tags = prompt.get("tags", "") or ""
            self.prompts_table.setItem(row, 3, QTableWidgetItem(tags))
    
    def filter_prompts(self):
        """Фильтрация промтов по поисковому запросу."""
        query = self.search_edit.text().lower()
        if not query:
            self.load_prompts()
            return
        
        # Фильтруем промты
        filtered = []
        for prompt in self.all_prompts:
            prompt_text = prompt.get("prompt", "").lower()
            tags = (prompt.get("tags", "") or "").lower()
            
            if query in prompt_text or query in tags:
                filtered.append(prompt)
        
        # Обновляем таблицу
        self.prompts_table.setRowCount(len(filtered))
        
        for row, prompt in enumerate(filtered):
            self.prompts_table.setItem(row, 0, QTableWidgetItem(str(prompt["id"])))
            self.prompts_table.setItem(row, 1, QTableWidgetItem(prompt.get("date", "")))
            
            prompt_text = prompt.get("prompt", "")
            prompt_item = QTableWidgetItem(prompt_text)
            prompt_item.setToolTip(prompt_text)
            prompt_item.setData(Qt.UserRole, prompt)
            self.prompts_table.setItem(row, 2, prompt_item)
            
            tags = prompt.get("tags", "") or ""
            self.prompts_table.setItem(row, 3, QTableWidgetItem(tags))
    
    def add_new_prompt(self):
        """Добавить новый промт."""
        dialog = PromptEditDialog(self, self.db, None)
        if dialog.exec_() == QDialog.Accepted:
            self.load_prompts()
            # Обновляем список промтов в главном окне, если оно открыто
            if self.parent():
                try:
                    self.parent().load_prompts()
                except:
                    pass
    
    def edit_selected_prompt(self):
        """Редактировать выбранный промт."""
        current_row = self.prompts_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите промт для редактирования!")
            return
        
        prompt_item = self.prompts_table.item(current_row, 2)
        if not prompt_item:
            return
        
        prompt = prompt_item.data(Qt.UserRole)
        if not prompt:
            return
        
        # Создаем диалог редактирования
        dialog = PromptEditDialog(self, self.db, prompt)
        if dialog.exec_() == QDialog.Accepted:
            self.load_prompts()
            # Обновляем список промтов в главном окне, если оно открыто
            if self.parent():
                try:
                    self.parent().load_prompts()
                except:
                    pass
    
    def delete_selected_prompt(self):
        """Удалить выбранный промт из базы данных."""
        current_row = self.prompts_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите промт для удаления!")
            return
        
        prompt_item = self.prompts_table.item(current_row, 2)
        if not prompt_item:
            return
        
        prompt = prompt_item.data(Qt.UserRole)
        if not prompt:
            return
        
        prompt_id = prompt.get("id")
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить промт '{prompt.get('prompt', '')[:50]}...' из базы данных?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_prompt(prompt_id)
                QMessageBox.information(self, "Успех", "Промт удален!")
                self.load_prompts()
                # Обновляем список промтов в главном окне, если оно открыто
                if self.parent():
                    try:
                        self.parent().load_prompts()
                    except:
                        pass
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить промт: {str(e)}")


class PromptEditDialog(QDialog):
    """Диалог для редактирования промта."""
    
    def __init__(self, parent=None, db: Database = None, prompt_data: Dict = None):
        super().__init__(parent)
        self.db = db
        self.prompt_data = prompt_data
        title = "Добавить промт" if prompt_data is None else "Редактировать промт"
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(600, 400)
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса диалога."""
        layout = QFormLayout()
        
        self.prompt_edit = QTextEdit()
        if self.prompt_data:
            self.prompt_edit.setPlainText(self.prompt_data.get("prompt", ""))
        self.prompt_edit.setPlaceholderText("Введите текст промта...")
        layout.addRow("Промт:", self.prompt_edit)
        
        self.tags_edit = QLineEdit()
        if self.prompt_data:
            self.tags_edit.setText(self.prompt_data.get("tags", "") or "")
        self.tags_edit.setPlaceholderText("тег1, тег2, тег3")
        layout.addRow("Теги:", self.tags_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_prompt)
        buttons.rejected.connect(self.reject)
        # Изменяем текст кнопки OK на "Сохранить"
        ok_button = buttons.button(QDialogButtonBox.Ok)
        ok_button.setText("Сохранить")
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def save_prompt(self):
        """Сохранить промт (создать новый или обновить существующий)."""
        prompt_text = self.prompt_edit.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(self, "Ошибка", "Промт не может быть пустым!")
            return
        
        if len(prompt_text) < 3:
            QMessageBox.warning(
                self,
                "Ошибка валидации",
                "Промт слишком короткий!\n\nМинимальная длина промта - 3 символа."
            )
            return
        
        tags = self.tags_edit.text().strip() or None
        
        try:
            if self.prompt_data is None:
                # Создание нового промта
                self.db.add_prompt(prompt_text, tags)
                QMessageBox.information(self, "Успех", "Промт добавлен!")
            else:
                # Обновление существующего промта
                self.db.update_prompt(
                    self.prompt_data["id"],
                    prompt=prompt_text,
                    tags=tags
                )
                QMessageBox.information(self, "Успех", "Промт обновлен!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить промт: {str(e)}")


class ModelsDialog(QDialog):
    """Диалог для просмотра и управления моделями."""
    
    def __init__(self, parent=None, db: Database = None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Модели")
        self.setModal(True)
        self.resize(1000, 600)
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса диалога."""
        layout = QVBoxLayout()
        
        # Поиск
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по названию или типу модели...")
        self.search_edit.textChanged.connect(self.filter_models)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)
        
        # Таблица моделей
        self.models_table = QTableWidget()
        self.models_table.setColumnCount(5)
        self.models_table.setHorizontalHeaderLabels(["Активна", "Название", "Тип", "API URL", "Дата создания"])
        self.models_table.horizontalHeader().setStretchLastSection(False)
        self.models_table.setWordWrap(True)
        self.models_table.setAlternatingRowColors(True)
        self.models_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.models_table.setSortingEnabled(True)
        header = self.models_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.models_table.itemDoubleClicked.connect(self.edit_selected_model)
        layout.addWidget(self.models_table)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        self.add_button = QPushButton("Добавить модель")
        self.add_button.clicked.connect(self.add_model)
        self.add_button.setToolTip("Добавить новую модель нейросети")
        self.edit_button = QPushButton("Редактировать")
        self.edit_button.clicked.connect(self.edit_selected_model)
        self.edit_button.setToolTip("Редактировать выбранную модель")
        self.delete_button = QPushButton("Удалить")
        self.delete_button.clicked.connect(self.delete_selected_model)
        self.delete_button.setToolTip("Удалить выбранную модель из базы данных")
        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.edit_button)
        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addStretch()
        
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons_layout.addWidget(buttons)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        
        # Загружаем модели
        self.load_models()
    
    def load_models(self):
        """Загрузить модели из базы данных."""
        models = self.db.get_models()
        self.all_models = models
        
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
            name_item = QTableWidgetItem(model.get("name", ""))
            name_item.setData(Qt.UserRole, model)  # Сохраняем полные данные модели
            self.models_table.setItem(row, 1, name_item)
            
            # Тип
            self.models_table.setItem(row, 2, QTableWidgetItem(model.get("model_type", "")))
            
            # API URL (усеченный)
            api_url = model.get("api_url", "")
            api_url_display = api_url[:50] + ("..." if len(api_url) > 50 else "")
            url_item = QTableWidgetItem(api_url_display)
            url_item.setToolTip(api_url)
            self.models_table.setItem(row, 3, url_item)
            
            # Дата создания
            self.models_table.setItem(row, 4, QTableWidgetItem(model.get("created_at", "")))
    
    def filter_models(self):
        """Фильтрация моделей по поисковому запросу."""
        query = self.search_edit.text().lower()
        if not query:
            self.load_models()
            return
        
        # Фильтруем модели
        filtered = []
        for model in self.all_models:
            name = model.get("name", "").lower()
            model_type = (model.get("model_type", "") or "").lower()
            
            if query in name or query in model_type:
                filtered.append(model)
        
        # Обновляем таблицу
        self.models_table.setRowCount(len(filtered))
        
        for row, model in enumerate(filtered):
            # Чекбокс активности
            checkbox = QCheckBox()
            checkbox.setChecked(model["is_active"] == 1)
            checkbox.stateChanged.connect(
                lambda state, m_id=model["id"]: self.toggle_model_active(m_id, state)
            )
            self.models_table.setCellWidget(row, 0, checkbox)
            
            name_item = QTableWidgetItem(model.get("name", ""))
            name_item.setData(Qt.UserRole, model)
            self.models_table.setItem(row, 1, name_item)
            
            self.models_table.setItem(row, 2, QTableWidgetItem(model.get("model_type", "")))
            
            api_url = model.get("api_url", "")
            api_url_display = api_url[:50] + ("..." if len(api_url) > 50 else "")
            url_item = QTableWidgetItem(api_url_display)
            url_item.setToolTip(api_url)
            self.models_table.setItem(row, 3, url_item)
            
            self.models_table.setItem(row, 4, QTableWidgetItem(model.get("created_at", "")))
    
    def edit_selected_model(self):
        """Редактировать выбранную модель."""
        current_row = self.models_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите модель для редактирования!")
            return
        
        name_item = self.models_table.item(current_row, 1)
        if not name_item:
            return
        
        model = name_item.data(Qt.UserRole)
        if not model:
            return
        
        # Используем существующий ModelDialog
        dialog = ModelDialog(self, model)
        if dialog.exec_() == QDialog.Accepted:
            model_data = dialog.get_data()
            try:
                self.db.update_model(
                    model["id"],
                    name=model_data["name"],
                    api_url=model_data["api_url"],
                    api_id=model_data["api_id"],
                    model_type=model_data["model_type"],
                    is_active=model_data["is_active"]
                )
                QMessageBox.information(self, "Успех", "Модель обновлена!")
                self.load_models()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось обновить модель: {str(e)}")
    
    def delete_selected_model(self):
        """Удалить выбранную модель из базы данных."""
        current_row = self.models_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите модель для удаления!")
            return
        
        name_item = self.models_table.item(current_row, 1)
        if not name_item:
            return
        
        model = name_item.data(Qt.UserRole)
        if not model:
            return
        
        model_id = model.get("id")
        model_name = model.get("name", "")
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить модель '{model_name}' из базы данных?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_model(model_id)
                QMessageBox.information(self, "Успех", "Модель удалена!")
                self.load_models()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить модель: {str(e)}")
    
    def toggle_model_active(self, model_id: int, state: int):
        """Переключить активность модели."""
        is_active = 1 if state == Qt.Checked else 0
        self.db.set_model_active(model_id, is_active)
    
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
                QMessageBox.information(self, "Успех", "Модель добавлена!")
                self.load_models()
            except Exception as e:
                error_msg = f"Не удалось добавить модель: {str(e)}"
                QMessageBox.critical(self, "Ошибка", error_msg)


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
        
        # Таймаут запросов
        self.timeout_edit = QLineEdit()
        timeout_value = self.db.get_setting("timeout", "30")
        self.timeout_edit.setText(timeout_value)
        self.timeout_edit.setToolTip("Таймаут для HTTP-запросов в секундах")
        layout.addRow("Таймаут запросов (сек):", self.timeout_edit)
        
        # Тема приложения
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Светлая", "light")
        self.theme_combo.addItem("Темная", "dark")
        theme_value = self.db.get_setting("theme", "light")
        index = self.theme_combo.findData(theme_value)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        self.theme_combo.setToolTip("Выберите цветовую тему интерфейса")
        layout.addRow("Тема:", self.theme_combo)
        
        # Размер шрифта
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setMinimum(8)
        self.font_size_spin.setMaximum(24)
        self.font_size_spin.setSuffix(" пт")
        font_size_value = self.db.get_setting("font_size", "10")
        try:
            self.font_size_spin.setValue(int(font_size_value))
        except (ValueError, TypeError):
            self.font_size_spin.setValue(10)
        self.font_size_spin.setToolTip("Размер шрифта для панелей интерфейса")
        layout.addRow("Размер шрифта панелей:", self.font_size_spin)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        # Изменяем текст кнопки OK на "Сохранить"
        ok_button = buttons.button(QDialogButtonBox.Ok)
        ok_button.setText("Сохранить")
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def save_settings(self):
        """Сохранить настройки."""
        try:
            # Сохранение таймаута
            timeout = int(self.timeout_edit.text())
            if timeout < 1:
                raise ValueError("Таймаут должен быть больше 0")
            self.db.set_setting("timeout", str(timeout))
            
            # Сохранение темы
            theme = self.theme_combo.currentData()
            self.db.set_setting("theme", theme)
            
            # Сохранение размера шрифта
            font_size = self.font_size_spin.value()
            self.db.set_setting("font_size", str(font_size))
            
            QMessageBox.information(self, "Успех", "Настройки сохранены!\n\nПрименение некоторых настроек может потребовать перезапуска приложения.")
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
