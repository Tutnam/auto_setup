# 🔐 Использование переменных окружения

Скрипт запускается с правами суперпользователя через `pkexec` или `sudo`, поэтому ручной ввод и передача пароля root/sudo в скрипт **больше не требуются**.

Для полной автоматизации настройки Samba можно использовать переменную окружения для пароля Samba-пользователя.

## 🌟 Поддерживаемые переменные

### Для пароля Samba пользователя:
- `SAMBA_PASSWORD` - основной вариант
- `AUTO_SETUP_SAMBA_PASSWORD` - альтернативный вариант

> [!NOTE]
> Переменные `SUDO_PASSWORD` и `AUTO_SETUP_PASSWORD` устарели (deprecated) и больше не используются, так как повышение привилегий выполняется стандартными средствами Linux (`pkexec` или `sudo`) до запуска скрипта.

## 📖 Примеры использования

### Пример 1: Запуск с переменной окружения через pkexec или sudo

```bash
# Установить переменную пароля Samba и запустить
export SAMBA_PASSWORD="your_samba_password"
pkexec env SAMBA_PASSWORD="$SAMBA_PASSWORD" python3 main.py
# или через sudo:
sudo -E python3 main.py
```

### Пример 2: Запуск в одной команде

```bash
SAMBA_PASSWORD="your_samba_password" sudo -E python3 main.py
```

### Пример 3: Запуск без переменных (интерактивный ввод пароля Samba)

```bash
pkexec python3 main.py
# или
sudo python3 main.py
```

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

Скрипт проверяет переменную окружения для Samba пароля в следующем порядке:

1. **Для Samba пароля:**
   - Сначала `SAMBA_PASSWORD`
   - Затем `AUTO_SETUP_SAMBA_PASSWORD`
   - Если не найдены - запрашивает интерактивно

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
          SAMBA_PASSWORD: ${{ secrets.SAMBA_PASSWORD }}
        run: |
          sudo -E python3 main.py
```

### systemd service

```ini
# /etc/systemd/system/auto-setup.service
[Unit]
Description=Auto Setup Service

[Service]
Type=oneshot
Environment="SAMBA_PASSWORD=your_samba_password"
ExecStart=/usr/bin/python3 /path/to/auto_setup/main.py
```

## 🧪 Проверка работы

Проверить, что переменная окружения доступна:

```bash
export SAMBA_PASSWORD="test_samba_password"
echo $SAMBA_PASSWORD

# Проверить при запуске от root
sudo -E python3 -c "import os; print('Samba password set:', bool(os.getenv('SAMBA_PASSWORD')))"
```

## 📚 Дополнительная информация

- Переменные окружения читаются через `os.getenv()`
- Если переменная не установлена, используется интерактивный ввод
- Пароли не выводятся в консоль и не логируются
- Переменные очищаются из памяти после использования

---

**Используйте переменные окружения для удобства, но всегда следите за безопасностью!** 🔒
