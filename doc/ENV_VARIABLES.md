# 🔐 Использование переменных окружения для паролей

Для автоматизации и удобства можно использовать переменные окружения вместо ручного ввода паролей.

## 🌟 Поддерживаемые переменные

### Для sudo пароля:
- `SUDO_PASSWORD` - основной вариант
- `AUTO_SETUP_PASSWORD` - альтернативный вариант

### Для пароля Samba пользователя:
- `SAMBA_PASSWORD` - основной вариант
- `AUTO_SETUP_SAMBA_PASSWORD` - альтернативный вариант

## 📖 Примеры использования

### Пример 1: Однократный запуск с переменными окружения

```bash
# Установить переменные и запустить
export SUDO_PASSWORD="your_sudo_password"
export SAMBA_PASSWORD="your_samba_password"
sudo -E python3 main.py
```

**Важно:** Используйте `sudo -E` чтобы сохранить переменные окружения при запуске с sudo.

### Пример 2: Запуск в одной команде

```bash
# Запуск с переменными в одной команде
SUDO_PASSWORD="your_sudo_password" SAMBA_PASSWORD="your_samba_password" sudo -E python3 main.py
```

### Пример 3: Использование только sudo пароля

```bash
# Если нужен только sudo пароль, а Samba пароль введёте вручную
export SUDO_PASSWORD="your_sudo_password"
sudo -E python3 main.py
```

### Пример 4: Создание файла .env (для разработки)

```bash
# Создать файл .env (не коммитьте его в git!)
cat > .env << EOF
export SUDO_PASSWORD="your_sudo_password"
export SAMBA_PASSWORD="your_samba_password"
EOF

# Загрузить переменные и запустить
source .env
sudo -E python3 main.py
```

**⚠️ ВАЖНО:** Файл `.env` уже добавлен в `.gitignore` и не будет коммититься в репозиторий.

### Пример 5: Использование в скриптах автоматизации

```bash
#!/bin/bash
# auto_setup.sh - пример скрипта автоматизации

# Загружаем пароли из защищённого файла (с правильными правами: chmod 600)
source /path/to/secure_passwords.sh

# Запускаем автоматическую настройку
sudo -E python3 /path/to/auto_setup/main.py
```

## 🔒 Безопасность

### ✅ Рекомендации:

1. **Никогда не коммитьте пароли в git!**
   - Файлы `.env`, `*.password` уже в `.gitignore`
   - Проверьте, что пароли не попадают в историю git

2. **Используйте правильные права доступа для файлов с паролями:**
   ```bash
   chmod 600 /path/to/password_file.sh
   ```

3. **Очищайте переменные окружения после использования:**
   ```bash
   unset SUDO_PASSWORD
   unset SAMBA_PASSWORD
   ```

4. **Для production используйте менеджеры секретов:**
   - HashiCorp Vault
   - AWS Secrets Manager
   - Kubernetes Secrets
   - Или системные решения (systemd environment files)

### ⚠️ Чего НЕ делать:

- ❌ Не храните пароли в открытом виде в скриптах
- ❌ Не логируйте пароли (они не попадут в вывод скрипта)
- ❌ Не передавайте пароли через командную строку (они видны в `ps aux`)
- ❌ Не коммитьте файлы с паролями в git

## 🔄 Приоритет использования

Скрипт проверяет переменные окружения в следующем порядке:

1. **Для sudo пароля:**
   - Сначала `SUDO_PASSWORD`
   - Затем `AUTO_SETUP_PASSWORD`
   - Если не найдены - запрашивает вручную

2. **Для Samba пароля:**
   - Сначала `SAMBA_PASSWORD`
   - Затем `AUTO_SETUP_SAMBA_PASSWORD`
   - Если не найдены - запрашивает вручную

## 💡 Примеры для разных сценариев

### CI/CD (GitHub Actions, GitLab CI)

```yaml
# .github/workflows/setup.yml
name: Auto Setup
on: [push]

jobs:
  setup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run auto setup
        env:
          SUDO_PASSWORD: ${{ secrets.SUDO_PASSWORD }}
          SAMBA_PASSWORD: ${{ secrets.SAMBA_PASSWORD }}
        run: |
          sudo -E python3 main.py
```

### Docker

```dockerfile
# Dockerfile
FROM archlinux:latest

# Устанавливаем зависимости
RUN pacman -Syu --noconfirm python

# Копируем проект
COPY . /app
WORKDIR /app

# Используйте ARG для build-time или ENV для runtime
ARG SUDO_PASSWORD
ENV SUDO_PASSWORD=$SUDO_PASSWORD
```

### systemd service

```ini
# /etc/systemd/system/auto-setup.service
[Unit]
Description=Auto Setup Service

[Service]
Type=oneshot
Environment="SUDO_PASSWORD=your_password"
Environment="SAMBA_PASSWORD=your_samba_password"
ExecStart=/usr/bin/python3 /path/to/auto_setup/main.py
```

## 🧪 Проверка работы

Проверить, что переменные окружения работают:

```bash
# Установить переменную
export SUDO_PASSWORD="test"

# Проверить что она доступна
echo $SUDO_PASSWORD  # Должно вывести: test

# Запустить с sudo -E (важно!)
sudo -E python3 -c "import os; print('Password:', os.getenv('SUDO_PASSWORD'))"
```

## 📚 Дополнительная информация

- Переменные окружения читаются через `os.getenv()`
- Если переменная не установлена, используется интерактивный ввод
- Пароли не выводятся в консоль и не логируются
- Переменные очищаются из памяти после использования

---

**Используйте переменные окружения для удобства, но всегда следите за безопасностью!** 🔒
