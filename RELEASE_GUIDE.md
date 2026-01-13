# Руководство по публикации ChatList на GitHub

## Подготовка к релизу

### 1. Обновление версии

1. Откройте файл `version.py`
2. Обновите версию (например, с `1.0.0` на `1.0.1`)
3. Сохраните файл

### 2. Сборка приложения

```bash
# Активируйте виртуальное окружение (если используется)
.\venv\Scripts\Activate.ps1

# Соберите приложение
pyinstaller ChatList.spec --clean

# Проверьте, что файл создан
# Должен быть: dist\ChatList-{версия}.exe
```

### 3. Создание установщика

```bash
# Создайте установщик с помощью Inno Setup
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" ChatList.iss

# Проверьте, что установщик создан
# Должен быть: installer\ChatList-Setup-{версия}.exe
```

### 4. Тестирование

- [ ] Установите приложение на чистой системе
- [ ] Проверьте, что приложение запускается
- [ ] Проверьте основные функции
- [ ] Убедитесь, что база данных создается в правильной папке (`%APPDATA%\ChatList`)

## Публикация на GitHub Release

### Шаг 1: Подготовка файлов

1. Убедитесь, что у вас есть:
   - `installer\ChatList-Setup-{версия}.exe` - установщик
   - `RELEASE_NOTES.md` - заметки о релизе (используйте шаблон ниже)

### Шаг 2: Создание тега

```bash
# Перейдите в корень репозитория
cd C:\Work\ChatList

# Создайте тег с версией
git tag -a v1.0.0 -m "Release version 1.0.0"

# Отправьте тег на GitHub
git push origin v1.0.0
```

### Шаг 3: Создание Release на GitHub

1. Перейдите на GitHub в ваш репозиторий
2. Нажмите на **"Releases"** в правом меню
3. Нажмите **"Create a new release"**
4. Выберите созданный тег (например, `v1.0.0`)
5. Заполните форму:
   - **Release title**: `ChatList v1.0.0`
   - **Description**: Скопируйте содержимое из `RELEASE_NOTES.md`
6. Загрузите файл установщика:
   - Нажмите **"Attach binaries"**
   - Выберите `installer\ChatList-Setup-1.0.0.exe`
7. Нажмите **"Publish release"**

### Шаг 4: Обновление GitHub Pages

1. Перейдите в настройки репозитория: **Settings** → **Pages**
2. В разделе **Source** выберите:
   - Branch: `gh-pages`
   - Folder: `/ (root)`
3. Сохраните изменения

## Структура файлов для GitHub Pages

```
ChatList/
├── docs/                    # Папка для GitHub Pages
│   ├── index.html          # Главная страница (лендинг)
│   ├── assets/             # CSS, изображения и т.д.
│   │   └── style.css
│   └── download.html       # Страница загрузки
├── RELEASE_GUIDE.md        # Этот файл
├── RELEASE_NOTES.md        # Шаблон заметок о релизе
└── .github/
    └── workflows/
        └── release.yml     # Автоматизация релизов (опционально)
```

## Автоматизация (опционально)

Можно настроить GitHub Actions для автоматической сборки и публикации при создании тега. См. файл `.github/workflows/release.yml`.

## Чеклист перед релизом

- [ ] Версия обновлена в `version.py`
- [ ] Приложение собрано и протестировано
- [ ] Установщик создан и протестирован
- [ ] Release notes подготовлены
- [ ] Тег создан и отправлен на GitHub
- [ ] Release создан на GitHub с установщиком
- [ ] GitHub Pages обновлен (если используется)
- [ ] Документация обновлена

## Полезные ссылки

- [GitHub Releases Documentation](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [Semantic Versioning](https://semver.org/)
