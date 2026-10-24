# Изменения

## Локальный MVP ClientProof

- Tenant/project authorization, client grants, отзыв доступа и IDOR guards.
- Проекты, результаты, immutable published versions, version-bound комментарии/решения, история и audit.
- Атомарные решения/квоты; сериализация grant revocation с решением.
- Русский UI: клиенты, проекты, черновики, публикация и файлы; role-aware навигация.
- Приватный staged upload с проверкой метаданных и sealed copy; короткоживущие ссылки.
- Counter smoke адаптирован в исходном файле к protected-entry/auth coverage; original reproduction сохранено.
- Credential-safe Vite/Vitest/integration; generated output исключён из lint без ослабления source rules.
- Disposable GoTrue/PostgREST/PostgreSQL/SMTP/S3 проверки, отдельные UI doubles, clean install и coverage comparison.

Hosted Stripe test mode, внешняя доставка почты и hosted R2 требуют отдельного окружения; doubles и локальный S3 не заменяют эти проверки. Публикация, production-миграции и покупки не выполнялись.
