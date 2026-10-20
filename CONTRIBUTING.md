# Участие в разработке

Для ошибок используйте GitHub Issues. Укажите версии Home Assistant,
интеграции, способ установки и ожидаемое поведение. Удалите из логов
пароли, токены, cookies, номера договоров, адреса и другие персональные данные.

Перед pull request выполните:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check custom_components tests scripts
.venv/bin/ruff format --check custom_components tests scripts
```
Изменения парсинга проверяйте на минимальных синтетических HTML-фрагментах.
Не коммитьте дампы личного кабинета, HAR-файлы и реальные учётные данные.

Клиенты провайдеров находятся в `custom_components/isp_balance/providers`.
Для добавления Микронмедиа нужен отдельный клиент, выбор клиента в настройке
и запуске интеграции и тесты его авторизации и получения данных.
