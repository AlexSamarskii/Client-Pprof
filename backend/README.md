# ClientProof API

API находится под /api/v1/clientproof; auth/organization/billing starter сохранены под /api/v1.

Python 3.12+, uv sync --locked, затем uv run uvicorn app.main:app --host 127.0.0.1 --port 18001. Переменные передаются процессу; credential-файлы не загружаются. Полный disposable стенд из корня: python3 scripts/run_local_acceptance.py --verify.

Supabase: SUPABASE_URL, SUPABASE_KEY, SUPABASE_JWKS_URL, ENV. Не включайте DEV_AUTH_BYPASS_ENABLED в рабочем окружении. Сервисная роль обходит RLS, поэтому каждый API запрос проверяет actor → organization → membership/project grant → resource. Прямой доступ anon/authenticated к ClientProof таблицам закрыт.

- Клиент связан с существующим Auth user и получает active project grant, без membership агентства.
- Публикация делает версию/file references неизменяемыми; комментарии/решения относятся к version_id.
- Решение атомарно; повтор результата идемпотентен, противоречащий результат возвращает 409.
- Отзыв grant запрещает новые запросы/ссылки; уже выданная ссылка живёт до TTL, максимум 300 секунд.
- Создание/реактивация сериализуются по организации и учитывают оплаченный план 5/25/100.
- Private upload: staging PUT → complete с HEAD/ETag и sealed copy → publish. Повтор staging PUT не меняет опубликованный объект; размер/MIME проверяет сервер.

Проверки: uv run ruff check app tests; uv run pyright; uv run pytest tests/unit --cov=app --cov-report=json:.coverage-backend.json.

Integration использует disposable SUPABASE_TEST_URL/KEY, DATABASE_URL, CLIENTPROOF_DATA_TEST_ADMIN_URL из harness. Не направляйте тесты на рабочую БД. Отсутствующий обязательный local runtime — failure, не skip.

Hosted Stripe target: tests/integration/test_stripe_webhooks.py -k stripe_runtime. Нужны CLIENTPROOF_STRIPE_RUNTIME_API_URL, CLIENTPROOF_STRIPE_RUNTIME_OWNER_TOKEN, CLIENTPROOF_STRIPE_RUNTIME_ORGANIZATION_ID, CLIENTPROOF_STRIPE_RUNTIME_CATALOG_KEY, CLIENTPROOF_STRIPE_TEST_SECRET. Приложение должно использовать тот же test account/catalog. Создаются sessions, но оплата не завершается. Без prerequisites — pending_environment.

Hosted R2 target: tests/integration/test_provider_runtime.py -k hosted_r2. Нужны CLIENTPROOF_HOSTED_R2_UPLOAD_URL и CLIENTPROOF_HOSTED_R2_READ_URL одного disposable private объекта. Значения не записываются в отчёты. Это отдельная проверка от локального S3 transfer.
