"""
Тестовая программа для просмотра и редактирования SQLite баз данных.
Отображает список таблиц, позволяет просматривать данные с пагинацией
и выполнять CRUD операции.
"""

import sys
import sqlite3
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QFileDialog,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QTextEdit, QDialogButtonBox,
    QComboBox, QSpinBox, QHeaderView, QGroupBox, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt
from typing import Optional, List, Dict, Tuple


class TableViewDialog(QDialog):
    """Диалог для просмотра и редактирования таблицы с пагинацией."""
    
    def __init__(self, parent, db_path: str, table_name: str):
        super().__init__(parent)
        self.db_path = db_path
        self.table_name = table_name
        self.current_page = 1
        self.rows_per_page = 50
        self.conn = None
        self.total_rows = 0
        self.column_info = []
        
        self.setWindowTitle(f"Таблица: {table_name}")
        self.setMinimumSize(900, 600)
        self.init_ui()
        self.load_table_info()
        self.load_data()
    
    def init_ui(self):
        """Инициализация интерфейса."""
        layout = QVBoxLayout()
        
        # Информация о таблице
        info_label = QLabel(f"Таблица: <b>{self.table_name}</b> | Всего записей: <b id='total-rows'>0</b>")
        layout.addWidget(info_label)
        self.total_rows_label = info_label
        
        # Таблица данных
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)
        
        # Пагинация
        pagination_layout = QHBoxLayout()
        
        pagination_layout.addWidget(QLabel("Строк на странице:"))
        self.rows_spinbox = QSpinBox()
        self.rows_spinbox.setMinimum(10)
        self.rows_spinbox.setMaximum(500)
        self.rows_spinbox.setValue(self.rows_per_page)
        self.rows_spinbox.valueChanged.connect(self.on_rows_per_page_changed)
        pagination_layout.addWidget(self.rows_spinbox)
        
        pagination_layout.addStretch()
        
        self.prev_btn = QPushButton("◄ Предыдущая")
        self.prev_btn.clicked.connect(self.prev_page)
        pagination_layout.addWidget(self.prev_btn)
        
        self.page_label = QLabel("Страница 1 из 1")
        pagination_layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("Следующая ►")
        self.next_btn.clicked.connect(self.next_page)
        pagination_layout.addWidget(self.next_btn)
        
        pagination_layout.addStretch()
        
        layout.addLayout(pagination_layout)
        
        # Кнопки CRUD
        crud_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ Добавить")
        self.add_btn.clicked.connect(self.add_record)
        crud_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("✏️ Редактировать")
        self.edit_btn.clicked.connect(self.edit_record)
        crud_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self.delete_record)
        crud_layout.addWidget(self.delete_btn)
        
        crud_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.clicked.connect(self.load_data)
        crud_layout.addWidget(refresh_btn)
        
        layout.addLayout(crud_layout)
        
        self.setLayout(layout)
    
    def get_connection(self) -> sqlite3.Connection:
        """Получить соединение с базой данных."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def closeEvent(self, event):
        """Закрытие соединения при закрытии окна."""
        if self.conn:
            self.conn.close()
        event.accept()
    
    def load_table_info(self):
        """Загрузка информации о структуре таблицы."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Получаем информацию о колонках
        cursor.execute(f"PRAGMA table_info({self.table_name})")
        self.column_info = cursor.fetchall()
        
        # Получаем общее количество строк
        cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
        self.total_rows = cursor.fetchone()[0]
        self.total_rows_label.setText(
            f"Таблица: <b>{self.table_name}</b> | Всего записей: <b>{self.total_rows}</b>"
        )
    
    def load_data(self):
        """Загрузка данных текущей страницы."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Получаем названия колонок
        column_names = [col[1] for col in self.column_info]
        pk_column = None
        has_rowid = False
        
        for col in self.column_info:
            if col[5]:  # pk flag
                pk_column = col[1]
                break
        
        # Проверяем, нужен ли rowid (для таблиц без явного PK)
        if not pk_column:
            # Если нет первичного ключа, используем rowid
            pk_column = "rowid"
            has_rowid = True
            column_names.insert(0, "rowid")
        
        # Вычисляем offset
        offset = (self.current_page - 1) * self.rows_per_page
        
        # Загружаем данные с пагинацией (включая rowid если нужно)
        if has_rowid:
            query = f"SELECT rowid, * FROM {self.table_name} LIMIT ? OFFSET ?"
        else:
            query = f"SELECT * FROM {self.table_name} LIMIT ? OFFSET ?"
        cursor.execute(query, (self.rows_per_page, offset))
        rows = cursor.fetchall()
        
        # Настраиваем таблицу
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(len(column_names))
        self.table.setHorizontalHeaderLabels(column_names)
        
        # Скрываем колонку rowid, если она используется как PK
        if has_rowid:
            self.table.setColumnHidden(0, True)
        
        # Заполняем таблицу
        for row_idx, row in enumerate(rows):
            # Если используем rowid, данные начинаются со второго элемента (после rowid)
            start_idx = 1 if has_rowid else 0
            col_idx = 0
            
            # Добавляем rowid в первую колонку, если он используется
            if has_rowid:
                rowid_item = QTableWidgetItem(str(row[0]))
                rowid_item.setFlags(rowid_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row_idx, 0, rowid_item)
                col_idx = 1
            
            # Заполняем остальные колонки
            for i, col_name in enumerate(column_names[start_idx:]):
                value = row[i + start_idx] if (i + start_idx) < len(row) else ""
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Не редактируем напрямую
                self.table.setItem(row_idx, col_idx, item)
                col_idx += 1
        
        # Обновляем информацию о пагинации
        total_pages = max(1, (self.total_rows + self.rows_per_page - 1) // self.rows_per_page)
        self.page_label.setText(f"Страница {self.current_page} из {total_pages}")
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < total_pages)
    
    def on_rows_per_page_changed(self, value):
        """Обработка изменения количества строк на странице."""
        self.rows_per_page = value
        self.current_page = 1
        self.load_data()
    
    def prev_page(self):
        """Переход на предыдущую страницу."""
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()
    
    def next_page(self):
        """Переход на следующую страницу."""
        total_pages = max(1, (self.total_rows + self.rows_per_page - 1) // self.rows_per_page)
        if self.current_page < total_pages:
            self.current_page += 1
            self.load_data()
    
    def get_selected_row_data(self) -> Optional[Dict]:
        """Получить данные выбранной строки."""
        current_row = self.table.currentRow()
        if current_row < 0:
            return None
        
        data = {}
        pk_column = None
        pk_value = None
        
        # Проверяем, есть ли явный PK
        has_explicit_pk = any(col[5] for col in self.column_info)
        has_rowid = not has_explicit_pk
        
        col_offset = 1 if has_rowid else 0  # Смещение из-за rowid
        
        for col_idx, col_info in enumerate(self.column_info):
            col_name = col_info[1]
            table_col_idx = col_idx + col_offset
            item = self.table.item(current_row, table_col_idx)
            value = item.text() if item else ""
            data[col_name] = value
            
            if col_info[5]:  # primary key
                pk_column = col_name
                pk_value = value
        
        # Если нет явного PK, используем rowid
        if has_rowid:
            pk_column = "rowid"
            item = self.table.item(current_row, 0)
            pk_value = item.text() if item else None
        
        data["_pk_column"] = pk_column
        data["_pk_value"] = pk_value
        
        return data
    
    def add_record(self):
        """Добавить новую запись."""
        dialog = RecordEditDialog(self, self.db_path, self.table_name, None)
        if dialog.exec_() == QDialog.Accepted:
            self.load_table_info()  # Обновляем общее количество строк
            self.load_data()
    
    def edit_record(self):
        """Редактировать выбранную запись."""
        row_data = self.get_selected_row_data()
        if not row_data:
            QMessageBox.warning(self, "Предупреждение", "Выберите строку для редактирования.")
            return
        
        # Загружаем полные данные записи из БД для редактирования
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            pk_column = row_data["_pk_column"]
            pk_value = row_data["_pk_value"]
            
            if pk_column == "rowid":
                query = f"SELECT * FROM {self.table_name} WHERE rowid = ?"
            else:
                query = f"SELECT * FROM {self.table_name} WHERE {pk_column} = ?"
            
            cursor.execute(query, (pk_value,))
            db_row = cursor.fetchone()
            
            if db_row:
                # Преобразуем Row в словарь
                full_data = dict(db_row)
                full_data["_pk_column"] = pk_column
                full_data["_pk_value"] = pk_value
                
                dialog = RecordEditDialog(self, self.db_path, self.table_name, full_data)
                if dialog.exec_() == QDialog.Accepted:
                    self.load_data()
            else:
                QMessageBox.warning(self, "Предупреждение", "Запись не найдена в базе данных.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при загрузке записи:\n{str(e)}")
    
    def delete_record(self):
        """Удалить выбранную запись."""
        row_data = self.get_selected_row_data()
        if not row_data:
            QMessageBox.warning(self, "Предупреждение", "Выберите строку для удаления.")
            return
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Вы уверены, что хотите удалить эту запись?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                pk_column = row_data["_pk_column"]
                pk_value = row_data["_pk_value"]
                
                # Если это rowid, используем специальный синтаксис
                if pk_column == "rowid":
                    cursor.execute(f"DELETE FROM {self.table_name} WHERE rowid = ?", (pk_value,))
                else:
                    cursor.execute(f"DELETE FROM {self.table_name} WHERE {pk_column} = ?", (pk_value,))
                
                conn.commit()
                QMessageBox.information(self, "Успех", "Запись успешно удалена.")
                self.load_table_info()
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при удалении записи:\n{str(e)}")


class RecordEditDialog(QDialog):
    """Диалог для добавления/редактирования записи."""
    
    def __init__(self, parent, db_path: str, table_name: str, row_data: Optional[Dict]):
        super().__init__(parent)
        self.db_path = db_path
        self.table_name = table_name
        self.row_data = row_data
        self.conn = None
        
        title = "Редактировать запись" if row_data else "Добавить запись"
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self.init_ui()
    
    def get_connection(self) -> sqlite3.Connection:
        """Получить соединение с базой данных."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
        return self.conn
    
    def closeEvent(self, event):
        """Закрытие соединения при закрытии окна."""
        if self.conn:
            self.conn.close()
        event.accept()
    
    def init_ui(self):
        """Инициализация интерфейса."""
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        self.fields = {}
        
        # Получаем информацию о колонках
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({self.table_name})")
        columns = cursor.fetchall()
        
        pk_column = None
        for col in columns:
            if col[5]:  # pk flag
                pk_column = col[1]
                break
        
        for col_info in columns:
            col_name = col_info[1]
            col_type = col_info[2]
            not_null = col_info[3]
            default_value = col_info[4]
            is_pk = col_info[5]
            
            # Пропускаем первичный ключ при добавлении (если AUTOINCREMENT)
            if is_pk and not self.row_data:
                continue
            
            # Определяем тип виджета
            if "TEXT" in col_type.upper():
                widget = QTextEdit()
                widget.setMaximumHeight(100)
                widget.setPlaceholderText(default_value if default_value else "")
            else:
                widget = QLineEdit()
                widget.setPlaceholderText(default_value if default_value else "")
            
            if self.row_data and col_name in self.row_data and col_name not in ["_pk_column", "_pk_value"]:
                value = str(self.row_data[col_name])
                if isinstance(widget, QTextEdit):
                    widget.setPlainText(value)
                else:
                    widget.setText(value)
            
            if is_pk:
                widget.setEnabled(False)  # Нельзя редактировать PK
            
            label_text = col_name
            if not_null and not default_value:
                label_text += " *"
            
            form_layout.addRow(f"{label_text}:", widget)
            self.fields[col_name] = {
                "widget": widget,
                "is_pk": is_pk,
                "not_null": not_null,
                "type": col_type
            }
        
        layout.addLayout(form_layout)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept_record)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def accept_record(self):
        """Сохранить запись."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Собираем данные из полей
            data = {}
            pk_column = None
            pk_value = None
            
            for col_name, field_info in self.fields.items():
                widget = field_info["widget"]
                
                if isinstance(widget, QTextEdit):
                    value = widget.toPlainText()
                else:
                    value = widget.text()
                
                # Проверка обязательных полей
                if field_info["not_null"] and not value and not self.row_data:
                    QMessageBox.warning(self, "Ошибка", f"Поле '{col_name}' обязательно для заполнения.")
                    return
                
                if field_info["is_pk"]:
                    pk_column = col_name
                    pk_value = value
                
                # Преобразуем пустые строки в None для необязательных полей
                if not value and not field_info["not_null"]:
                    value = None
                
                data[col_name] = value
            
            if self.row_data:
                # Обновление записи
                pk_column = self.row_data.get("_pk_column")
                pk_value = self.row_data.get("_pk_value")
                
                set_clause = ", ".join([f"{k} = ?" for k in data.keys() if k != pk_column])
                values = [v for k, v in data.items() if k != pk_column]
                values.append(pk_value)
                
                if pk_column == "rowid":
                    query = f"UPDATE {self.table_name} SET {set_clause} WHERE rowid = ?"
                else:
                    query = f"UPDATE {self.table_name} SET {set_clause} WHERE {pk_column} = ?"
            else:
                # Вставка новой записи
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?" for _ in data])
                values = list(data.values())
                
                query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
            
            cursor.execute(query, values)
            conn.commit()
            
            QMessageBox.information(self, "Успех", "Запись успешно сохранена.")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сохранении записи:\n{str(e)}")


class MainWindow(QMainWindow):
    """Главное окно приложения."""
    
    def __init__(self):
        super().__init__()
        self.db_path = None
        self.conn = None
        self.setWindowTitle("Просмотр SQLite базы данных")
        self.setMinimumSize(400, 500)
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        
        # Кнопка выбора файла
        file_layout = QHBoxLayout()
        self.file_label = QLabel("Файл не выбран")
        file_layout.addWidget(self.file_label)
        
        select_btn = QPushButton("Выбрать файл")
        select_btn.clicked.connect(self.select_file)
        file_layout.addWidget(select_btn)
        
        layout.addLayout(file_layout)
        
        # Список таблиц
        tables_group = QGroupBox("Таблицы базы данных")
        tables_layout = QVBoxLayout()
        
        self.tables_list = QListWidget()
        self.tables_list.itemDoubleClicked.connect(self.open_table)
        tables_layout.addWidget(self.tables_list)
        
        open_btn = QPushButton("Открыть")
        open_btn.clicked.connect(self.open_selected_table)
        tables_layout.addWidget(open_btn)
        
        tables_group.setLayout(tables_layout)
        layout.addWidget(tables_group)
        
        layout.addStretch()
        
        central_widget.setLayout(layout)
    
    def get_connection(self) -> Optional[sqlite3.Connection]:
        """Получить соединение с базой данных."""
        if not self.db_path:
            return None
        if self.conn is None:
            try:
                self.conn = sqlite3.connect(self.db_path)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось открыть базу данных:\n{str(e)}")
                return None
        return self.conn
    
    def select_file(self):
        """Выбрать файл базы данных."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл базы данных SQLite",
            "",
            "SQLite Database (*.db *.sqlite *.sqlite3);;All Files (*)"
        )
        
        if file_path:
            self.db_path = file_path
            self.file_label.setText(f"Файл: {file_path}")
            
            # Закрываем предыдущее соединение
            if self.conn:
                self.conn.close()
                self.conn = None
            
            # Загружаем список таблиц
            self.load_tables()
    
    def load_tables(self):
        """Загрузить список таблиц из базы данных."""
        self.tables_list.clear()
        
        conn = self.get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            
            tables = cursor.fetchall()
            for table in tables:
                self.tables_list.addItem(table[0])
            
            if not tables:
                QMessageBox.information(self, "Информация", "В базе данных нет таблиц.")
        
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при загрузке таблиц:\n{str(e)}")
    
    def open_selected_table(self):
        """Открыть выбранную таблицу."""
        current_item = self.tables_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Предупреждение", "Выберите таблицу для открытия.")
            return
        
        table_name = current_item.text()
        self.open_table_by_name(table_name)
    
    def open_table(self, item: QListWidgetItem):
        """Открыть таблицу по двойному клику."""
        table_name = item.text()
        self.open_table_by_name(table_name)
    
    def open_table_by_name(self, table_name: str):
        """Открыть диалог просмотра таблицы."""
        if not self.db_path:
            QMessageBox.warning(self, "Предупреждение", "Сначала выберите файл базы данных.")
            return
        
        dialog = TableViewDialog(self, self.db_path, table_name)
        dialog.exec_()
    
    def closeEvent(self, event):
        """Закрытие соединения при закрытии приложения."""
        if self.conn:
            self.conn.close()
        event.accept()


def main():
    """Главная функция приложения."""
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
