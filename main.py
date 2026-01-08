"""
Основной модуль приложения ChatList.
Реализует пользовательский интерфейс на PyQt5.
"""

import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QLineEdit, QMessageBox, QHeaderView, QProgressBar,
    QSplitter, QGroupBox, QDialog, QFormLayout, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from typing import List, Dict, Optional
import json

from db import Database
from models import ModelHandler, APIError


class SendPromptThread(QThread):
    """Поток для асинхронной отправки промтов в модели."""
    
    result_received = pyqtSignal(dict, str, str)  # model, response, error
    finished = pyqtSignal()
    
    def __init__(self, model_handler: ModelHandler, prompt: str):
        super().__init__()
        self.model_handler = model_handler
        self.prompt = prompt
    
    def run(self):
        """Запуск отправки промтов."""
        def callback(model, response, error):
            self.result_received.emit(model, response or "", error or "")
        
        self.model_handler.send_prompt_to_all_active(self.prompt, callback)
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
        self.api_url_edit = QLineEdit()
        self.api_id_edit = QLineEdit()
        self.model_type_edit = QLineEdit()
        self.is_active_checkbox = QCheckBox()
        self.is_active_checkbox.setChecked(True)
        
        layout.addRow("Название:", self.name_edit)
        layout.addRow("API URL:", self.api_url_edit)
        layout.addRow("API ID (имя переменной .env):", self.api_id_edit)
        layout.addRow("Тип модели:", self.model_type_edit)
        layout.addRow("Активна:", self.is_active_checkbox)
        
        if self.model_data:
            self.name_edit.setText(self.model_data.get("name", ""))
            self.api_url_edit.setText(self.model_data.get("api_url", ""))
            self.api_id_edit.setText(self.model_data.get("api_id", ""))
            self.model_type_edit.setText(self.model_data.get("model_type", ""))
            self.is_active_checkbox.setChecked(self.model_data.get("is_active", 1) == 1)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
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
        self.temp_results = []  # Временная таблица результатов в памяти
        self.send_thread = None
        
        self.init_ui()
        self.load_prompts()
        self.load_models()
    
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
        prompt_layout.addWidget(self.prompt_edit)
        
        # Поле для тегов
        tags_layout = QHBoxLayout()
        tags_layout.addWidget(QLabel("Теги:"))
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("тег1, тег2, тег3")
        tags_layout.addWidget(self.tags_edit)
        prompt_layout.addLayout(tags_layout)
        
        # Кнопка отправки
        self.send_button = QPushButton("Отправить запрос")
        self.send_button.clicked.connect(self.send_prompt)
        prompt_layout.addWidget(self.send_button)
        
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
        models_layout.addWidget(self.models_table)
        
        # Кнопки управления моделями
        model_buttons_layout = QHBoxLayout()
        self.add_model_button = QPushButton("Добавить модель")
        self.add_model_button.clicked.connect(self.add_model)
        self.edit_model_button = QPushButton("Редактировать")
        self.edit_model_button.clicked.connect(self.edit_model)
        self.delete_model_button = QPushButton("Удалить")
        self.delete_model_button.clicked.connect(self.delete_model)
        model_buttons_layout.addWidget(self.add_model_button)
        model_buttons_layout.addWidget(self.edit_model_button)
        model_buttons_layout.addWidget(self.delete_model_button)
        models_layout.addLayout(model_buttons_layout)
        
        models_group.setLayout(models_layout)
        left_layout.addWidget(models_group)
        
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
        self.results_table.setWordWrap(True)
        self.results_table.setAlternatingRowColors(True)
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        results_layout.addWidget(self.results_table)
        
        # Кнопки управления результатами
        result_buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Сохранить выбранные")
        self.save_button.clicked.connect(self.save_selected_results)
        self.new_request_button = QPushButton("Новый запрос")
        self.new_request_button.clicked.connect(self.new_request)
        self.export_button = QPushButton("Экспорт")
        self.export_button.clicked.connect(self.export_results)
        result_buttons_layout.addWidget(self.save_button)
        result_buttons_layout.addWidget(self.new_request_button)
        result_buttons_layout.addWidget(self.export_button)
        results_layout.addLayout(result_buttons_layout)
        
        results_group.setLayout(results_layout)
        right_layout.addWidget(results_group)
        
        splitter.addWidget(right_panel)
        
        # Установка пропорций сплиттера
        splitter.setSizes([400, 800])
    
    def load_prompts(self):
        """Загрузить список промтов в выпадающий список."""
        self.prompt_combo.clear()
        prompts = self.db.get_prompts()
        for prompt in prompts:
            # Показываем первые 50 символов промта
            display_text = prompt["prompt"][:50] + ("..." if len(prompt["prompt"]) > 50 else "")
            self.prompt_combo.addItem(display_text, prompt["id"])
    
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
        
        if not prompt_text:
            QMessageBox.warning(self, "Ошибка", "Введите промт для отправки!")
            return
        
        active_models = self.db.get_models(active_only=True)
        if not active_models:
            QMessageBox.warning(self, "Ошибка", "Нет активных моделей!")
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
        
        # Запуск потока для отправки запросов
        self.send_thread = SendPromptThread(self.model_handler, prompt_text)
        self.send_thread.result_received.connect(self.on_result_received)
        self.send_thread.finished.connect(self.on_send_finished)
        self.send_thread.start()
    
    def on_result_received(self, model: Dict, response: str, error: str):
        """Обработчик получения результата от модели."""
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
        
        # Ответ или ошибка
        text = error if error else response
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.results_table.setItem(row, 2, item)
        
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
            QMessageBox.information(self, "Информация", "Нет результатов для сохранения!")
            return
        
        # Получаем текущий промт
        prompt_text = self.prompt_edit.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(self, "Ошибка", "Не найден промт для сохранения результатов!")
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
    
    def export_results(self):
        """Экспорт результатов в Markdown или JSON."""
        if not self.temp_results:
            QMessageBox.information(self, "Информация", "Нет результатов для экспорта!")
            return
        
        # Простой экспорт в JSON (можно расширить для Markdown)
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
        
        # Просто показываем в сообщении (в реальном приложении можно сохранить в файл)
        json_str = json.dumps(selected_results, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "Экспорт", f"Выбранные результаты:\n\n{json_str[:500]}...")
    
    def add_model(self):
        """Добавить новую модель."""
        dialog = ModelDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            try:
                self.db.add_model(
                    data["name"],
                    data["api_url"],
                    data["api_id"],
                    data["model_type"] if data["model_type"] else None,
                    data["is_active"]
                )
                self.load_models()
                QMessageBox.information(self, "Успех", "Модель добавлена!")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось добавить модель: {str(e)}")
    
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
    
    def closeEvent(self, event):
        """Обработчик закрытия окна."""
        if self.send_thread and self.send_thread.isRunning():
            self.send_thread.terminate()
            self.send_thread.wait()
        
        self.model_handler.close()
        self.db.close()
        event.accept()


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
