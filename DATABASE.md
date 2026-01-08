# Схема базы данных ChatList

## Общая информация

База данных использует SQLite и состоит из четырех основных таблиц:
- `prompts` - хранение промтов (запросов)
- `models` - хранение информации о нейросетях
- `results` - хранение сохраненных результатов
- `settings` - хранение настроек программы

## Таблица: prompts

Хранит промты (запросы), которые пользователь отправляет в нейросети.

### Структура таблицы:

| Поле | Тип | Описание | Ограничения |
|------|-----|----------|-------------|
| `id` | INTEGER | Первичный ключ, автоинкремент | PRIMARY KEY, AUTOINCREMENT |
| `date` | TEXT | Дата и время создания промта | NOT NULL, формат: ISO 8601 (YYYY-MM-DD HH:MM:SS) |
| `prompt` | TEXT | Текст промта | NOT NULL |
| `tags` | TEXT | Теги для категоризации (через запятую или JSON) | NULL |

### Индексы:
- Индекс на поле `date` для быстрой сортировки по дате
- Индекс на поле `tags` для быстрого поиска по тегам

### Пример данных:
```
id: 1
date: "2024-01-15 10:30:00"
prompt: "Объясни квантовую физику простыми словами"
tags: "физика, наука, объяснение"
```

## Таблица: models

Хранит информацию о нейросетях (моделях), к которым можно отправлять запросы.

### Структура таблицы:

| Поле | Тип | Описание | Ограничения |
|------|-----|----------|-------------|
| `id` | INTEGER | Первичный ключ, автоинкремент | PRIMARY KEY, AUTOINCREMENT |
| `name` | TEXT | Название модели | NOT NULL, UNIQUE |
| `api_url` | TEXT | URL API для отправки запросов | NOT NULL |
| `api_id` | TEXT | Имя переменной окружения, содержащей API-ключ | NOT NULL |
| `is_active` | INTEGER | Флаг активности модели (1 - активна, 0 - неактивна) | NOT NULL, DEFAULT 1, CHECK (is_active IN (0, 1)) |
| `model_type` | TEXT | Тип модели (OpenAI, DeepSeek, Groq и т.д.) | NULL |
| `created_at` | TEXT | Дата создания записи | NOT NULL, формат: ISO 8601 |
| `updated_at` | TEXT | Дата последнего обновления | NULL, формат: ISO 8601 |

### Примечания:
- API-ключи НЕ хранятся в базе данных, а находятся в файле `.env`
- Поле `api_id` содержит имя переменной окружения (например, "OPENAI_API_KEY")
- Значение этой переменной загружается из `.env` файла при работе с API

### Индексы:
- Индекс на поле `is_active` для быстрого получения активных моделей
- Индекс на поле `name` для быстрого поиска по имени

### Пример данных:
```
id: 1
name: "GPT-4"
api_url: "https://api.openai.com/v1/chat/completions"
api_id: "OPENAI_API_KEY"
is_active: 1
model_type: "OpenAI"
created_at: "2024-01-10 09:00:00"
updated_at: "2024-01-10 09:00:00"
```

## Таблица: results

Хранит сохраненные результаты ответов нейросетей.

### Структура таблицы:

| Поле | Тип | Описание | Ограничения |
|------|-----|----------|-------------|
| `id` | INTEGER | Первичный ключ, автоинкремент | PRIMARY KEY, AUTOINCREMENT |
| `prompt_id` | INTEGER | Ссылка на промт из таблицы prompts | NOT NULL, FOREIGN KEY REFERENCES prompts(id) |
| `model_id` | INTEGER | Ссылка на модель из таблицы models | NOT NULL, FOREIGN KEY REFERENCES models(id) |
| `response` | TEXT | Текст ответа от модели | NOT NULL |
| `saved_at` | TEXT | Дата и время сохранения результата | NOT NULL, формат: ISO 8601 |
| `notes` | TEXT | Дополнительные заметки пользователя | NULL |

### Индексы:
- Индекс на поле `prompt_id` для быстрого поиска результатов по промту
- Индекс на поле `model_id` для быстрого поиска результатов по модели
- Индекс на поле `saved_at` для сортировки по дате сохранения
- Составной индекс на `(prompt_id, model_id)` для уникальности комбинации

### Пример данных:
```
id: 1
prompt_id: 1
model_id: 1
response: "Квантовая физика изучает поведение частиц на атомном уровне..."
saved_at: "2024-01-15 10:35:00"
notes: "Хорошее объяснение"
```

## Таблица: settings

Хранит настройки программы.

### Структура таблицы:

| Поле | Тип | Описание | Ограничения |
|------|-----|----------|-------------|
| `id` | INTEGER | Первичный ключ, автоинкремент | PRIMARY KEY, AUTOINCREMENT |
| `key` | TEXT | Ключ настройки | NOT NULL, UNIQUE |
| `value` | TEXT | Значение настройки | NULL |
| `updated_at` | TEXT | Дата последнего обновления | NULL, формат: ISO 8601 |

### Индексы:
- Индекс на поле `key` для быстрого поиска настроек

### Пример данных:
```
id: 1
key: "default_timeout"
value: "30"
updated_at: "2024-01-10 09:00:00"

id: 2
key: "auto_save"
value: "false"
updated_at: "2024-01-10 09:00:00"
```

## Связи между таблицами

```
prompts (1) ──< (N) results
models  (1) ──< (N) results
```

- Один промт может иметь множество сохраненных результатов
- Одна модель может иметь множество сохраненных результатов
- Результат всегда связан с одним промтом и одной моделью

## SQL для создания таблиц

```sql
-- Таблица prompts
CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    prompt TEXT NOT NULL,
    tags TEXT
);

CREATE INDEX IF NOT EXISTS idx_prompts_date ON prompts(date);
CREATE INDEX IF NOT EXISTS idx_prompts_tags ON prompts(tags);

-- Таблица models
CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    api_url TEXT NOT NULL,
    api_id TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    model_type TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_models_is_active ON models(is_active);
CREATE INDEX IF NOT EXISTS idx_models_name ON models(name);

-- Таблица results
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    model_id INTEGER NOT NULL,
    response TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE,
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_results_prompt_id ON results(prompt_id);
CREATE INDEX IF NOT EXISTS idx_results_model_id ON results(model_id);
CREATE INDEX IF NOT EXISTS idx_results_saved_at ON results(saved_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_results_prompt_model ON results(prompt_id, model_id);

-- Таблица settings
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key);
```

## Примечания по реализации

1. **Безопасность API-ключей**: API-ключи хранятся только в файле `.env`, который не должен попадать в систему контроля версий. В базе данных хранится только имя переменной окружения.

2. **Временная таблица результатов**: Временная таблица для отображения текущих результатов НЕ хранится в базе данных, а существует только в памяти приложения (например, в виде списка словарей или объектов).

3. **Каскадное удаление**: При удалении промта или модели, связанные результаты также удаляются (ON DELETE CASCADE).

4. **Формат даты**: Все даты хранятся в формате ISO 8601 (YYYY-MM-DD HH:MM:SS) для удобства сортировки и сравнения.

5. **Теги**: Теги могут храниться как строка с разделителями (запятая, точка с запятой) или как JSON-массив. Выбор формата зависит от удобства реализации поиска.

