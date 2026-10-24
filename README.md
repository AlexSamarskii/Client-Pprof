# ClientProof

Клиентский портал для небольшого агентства. Здесь можно передать клиенту результат работы, обсудить правки и сохранить решение по каждой версии.

Сотрудник создаёт проект, загружает файлы и публикует версию. Клиент входит по коду из письма, оставляет комментарий и выбирает «Принять» или «На доработку». Когда работа обновляется, её публикуют новой версией. Предыдущее обсуждение и решение остаются в истории.

## Что умеет

- Клиенты, проекты и сроки ответа. На рабочей панели видны черновики, проекты на согласовании, принятые работы и просроченные ответы.
- Черновики и публикация результатов. Опубликованную версию нельзя изменить задним числом.
- Комментарии и решения, привязанные к конкретной версии.
- Приватные файлы с временными ссылками на скачивание.
- Роли сотрудников и отдельный доступ клиента к назначенным проектам.
- Подписки через Stripe: Studio — 5 активных проектов, Team — 25, Agency — 100.

Клиент не становится участником агентства. Доступ к каждому проекту выдаётся отдельно и может быть отозван. Уже выданная ссылка на файл после отзыва работает до окончания своего срока, максимум 300 секунд.

Согласование в ClientProof фиксирует рабочее решение клиента. Юридической электронной подписью оно не является.

## Запуск для разработки

Понадобятся Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 22+ и npm. Для тестового стенда также нужен Docker.

Установите зависимости из корня репозитория:

```sh
cd backend
uv --no-config --cache-dir /tmp/clientproof-uv-cache sync --locked
cd ../frontend
npm exec --yes --package=pnpm@10.34.7 -- pnpm install \
  --frozen-lockfile --store-dir /tmp/clientproof-pnpm-store
cd ..
```

Версия pnpm закреплена в `frontend/package.json`. Устанавливать его глобально не нужно.

Для работы приложения нужен Supabase-проект с настроенной отправкой кодов входа и миграциями из [backend/supabase/migrations](backend/supabase/migrations). Для загрузки файлов подготовьте приватный R2 или S3-совместимый bucket и разрешите в его CORS адрес интерфейса.

Передайте [настройки](#настройки) через окружение процессов. Затем запустите API:

```sh
cd backend
uv run --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8000
```

В другом терминале, из корня проекта, запустите интерфейс:

```sh
node scripts/clientproof_frontend_server.mjs
```

Портал откроется на http://127.0.0.1:5173, документация API — на http://127.0.0.1:8000/docs.

Чтобы пройти первый сценарий, создайте пользователя в Supabase Auth. В портале владелец или администратор добавляет клиента по UUID этого пользователя, создаёт проект и выдаёт к нему доступ. После этого можно создать результат, опубликовать версию и войти под клиентом для согласования.

## Настройки

Значения передаются через окружение или менеджер секретов. Frontend и тестовые fixtures не загружают локальные файлы с секретами.

| Переменная | Для чего нужна |
| --- | --- |
| `VITE_SUPABASE_URL` | URL Supabase для браузера |
| `VITE_SUPABASE_PUBLISHABLE_DEFAULT_KEY` | Публичный ключ Supabase |
| `VITE_BACKEND_URL` | URL API, при локальном запуске — `http://127.0.0.1:8000` |
| `SUPABASE_URL`, `SUPABASE_KEY` | URL и серверный ключ Supabase для backend |
| `SUPABASE_JWKS_URL` | JWKS endpoint для проверки JWT |
| `ENV` | Окружение приложения; для production — `prod` |
| `DEV_AUTH_BYPASS_ENABLED` | Обход проверки входа для разработки; в рабочем окружении должен быть выключен |
| `CLOUDFLARE_ACCOUNT_ID` | Идентификатор аккаунта Cloudflare |
| `CLOUDFLARE_ACCESS_KEY`, `CLOUDFLARE_SECRET_ACCESS_KEY` | Ключи доступа к R2 |
| `CLOUDFLARE_R2_BUCKET` | Имя приватного bucket |
| `CLOUDFLARE_R2_ENDPOINT` | Необязательный endpoint для S3-совместимого хранилища |
| `CLIENTPROOF_FILE_LINK_TTL_SECONDS` | Срок действия ссылки: 1–300 секунд, по умолчанию 300 |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Ключ Stripe и секрет проверки webhook |

В `VITE_*` должны попадать только публичные настройки: они доступны браузеру. Серверный ключ Supabase и ключи хранилища остаются на backend.

Подробнее о настройке API, Stripe и хранилища — в [backend/README.md](backend/README.md).

## Тесты

### Обычные проверки

```sh
# Из backend/
uv run --no-sync ruff check app tests
uv run --no-sync pyright
uv run --no-sync pytest tests/unit

# Из frontend/
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

Для проверки установки с нуля есть отдельный скрипт:

```sh
python3 scripts/clientproof_clean_install.py
```

Он копирует исходники во временный каталог, устанавливает зависимости и выполняет lint, typecheck, unit-тесты и сборку. Локальные настройки и кэши не копируются; временный каталог удаляется после проверки.

### Полный сценарий с базой и браузером

Сначала установите браузеры Playwright:

```sh
cd frontend
PLAYWRIGHT_BROWSERS_PATH=/tmp/clientproof-playwright-browsers \
  npm exec -- playwright install chromium firefox webkit
cd ..
```

Затем из корня проекта:

```sh
PLAYWRIGHT_BROWSERS_PATH=/tmp/clientproof-playwright-browsers \
  python3 scripts/run_local_acceptance.py --verify
```

Скрипт поднимает собственные PostgreSQL, GoTrue, PostgREST, Mailpit и MinIO, запускает API и frontend. В браузере проверяются вход по коду из письма, публикация с файлом, комментарии, оба решения клиента и отзыв доступа. Результаты дополнительно читаются из PostgreSQL.

После прогона стенд удаляется. Он не предназначен для постоянной разработки и не сбрасывает существующие базы. Первый запуск скачивает Docker-образы. Если образ MinIO недоступен, можно указать совместимый образ через `CP_MINIO_IMAGE`.

Команда `python3 scripts/run_local_acceptance.py --prepare` проверяет только подготовку стенда и тоже удаляет его после завершения.

### Проверка интерфейса отдельно от backend

UI e2e использует тестовые ответы API. Для него запустите frontend из корня:

```sh
VITE_SUPABASE_URL=http://127.0.0.1:54321 \
VITE_SUPABASE_PUBLISHABLE_DEFAULT_KEY=local-ui-placeholder \
VITE_BACKEND_URL=http://127.0.0.1:8000 \
  node scripts/clientproof_frontend_server.mjs
```

В другом терминале, из `frontend/`:

```sh
PLAYWRIGHT_BROWSERS_PATH=/tmp/clientproof-playwright-browsers \
  npm run test:e2e -- --reporter=line
```

Playwright сам не запускает сервер. Этот набор проверяет интерфейс в Chromium, Firefox и WebKit; сохранение данных и работу сервисов проверяет полный сценарий выше.

## Перед рабочим запуском

Основной сценарий прошёл локальные проверки с базой, почтовым сервером и приватным хранилищем. В целевом окружении ещё нужно проверить:

- Stripe Checkout, Portal и доставку webhook в test mode.
- Приватный hosted R2 bucket: права доступа, CORS и подписанные ссылки.
- Отправку писем с кодами и redirect URLs выбранного Supabase-проекта.

Локальные GoTrue, Mailpit и MinIO позволяют проверить логику приложения, но настройки внешних сервисов нужно проверить отдельно. Production-развёртывание пока не проверялось.

## Устройство проекта

Frontend написан на React 19 и TypeScript, с Vite, TanStack Router/Query и Tailwind CSS. Backend — FastAPI и Pydantic; данные и вход обслуживают PostgreSQL, PostgREST и Supabase Auth.

Права проверяются на backend для каждого проекта и записи. Решения клиента и квоты защищены транзакциями. При завершении загрузки сервер сверяет метаданные файла и создаёт отдельную копию: повторная загрузка по старой ссылке не меняет опубликованный результат.

```text
backend/app/clientproof/    Маршруты, права доступа и схемы ClientProof
backend/supabase/          Миграции и настройки Supabase
backend/tests/             Unit и integration-тесты
frontend/                  Интерфейс и его тесты
scripts/                   Локальный сервер и проверочные скрипты
docs/upstream/             Документация и происхождение starter
engine/                    Унаследованные worker и webhook gateway
```

Engine/SQS, Cloudflare Images и Stream для согласования не требуются. Корневой `docker-compose.yml` сохранён от starter; для полного тестового стенда используйте `scripts/run_local_acceptance.py`.

## Лицензия

ClientProof основан на [dim-pan/the-saas-template](https://github.com/dim-pan/the-saas-template), MIT, copyright 2026 dim-pan и contributors. Исходная лицензия и уведомления об авторских правах сохранены.

[MIT License](LICENSE) · [Исходная база](docs/upstream/source_manifest.json) · [История изменений](CHANGELOG.md)
