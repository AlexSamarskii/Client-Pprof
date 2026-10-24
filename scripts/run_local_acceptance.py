#!/usr/bin/env python3
"""Owned disposable real Supabase Auth/PostgREST/Postgres acceptance runtime.

Run with python3; re-execs the existing backend venv without installing anything.
--prepare migrates/seeds/probes then cleans up. --verify additionally runs tests.
No credential files, auth bypass, product doubles, existing database resets or
runner state modifications. Every invocation owns a fresh labelled Docker network.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import uuid

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "backend/.venv/bin/python"
if Path(sys.prefix).resolve() != (ROOT / "backend/.venv").resolve():
    os.execv(str(PYTHON), [str(PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

import boto3  # noqa: E402
import httpx  # noqa: E402
import psycopg  # noqa: E402
from jose import jwt  # noqa: E402


def port() -> int:
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


def wait_until(check, description: str, timeout: int = 90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (httpx.HTTPError, OSError, psycopg.Error):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {description}")


class Runtime:
    def __init__(self):
        self.name = f"clientproof-acceptance-{uuid.uuid4().hex[:10]}"
        self.label = f"clientproof.acceptance.owner={self.name}"
        self.containers: list[str] = []
        self.processes: list[subprocess.Popen] = []
        self.log_threads: list[threading.Thread] = []
        self.logs = []
        self.gateway: ThreadingHTTPServer | None = None
        self.network_created = False
        self.server_coverage_expected = False
        self.native_database: Path | None = None
        self.ports = {}
        for key in ("db", "auth", "rest", "mail", "smtp", "gateway", "api", "ui", "s3"):
            candidate = port()
            while candidate in self.ports.values():
                candidate = port()
            self.ports[key] = candidate
        self.secret = secrets.token_hex(32)
        self.password = secrets.token_urlsafe(24)
        self.anon = self.token("anon")
        self.service = self.token("service_role")
        self.url = f"http://127.0.0.1:{self.ports['gateway']}"
        self.api = f"http://127.0.0.1:{self.ports['api']}"
        self.ui = f"http://127.0.0.1:{self.ports['ui']}"
        self.db_url = f"postgresql://postgres:{self.password}@127.0.0.1:{self.ports['db']}/postgres"
        self.evidence = (
            ROOT / ".agent/artifacts/completion/local_acceptance" / self.name
        )
        self.evidence.mkdir(parents=True, exist_ok=True)

    def token(self, role: str) -> str:
        return jwt.encode(
            {
                "role": role,
                "iss": "supabase",
                "iat": int(time.time()),
                "exp": int(time.time()) + 7200,
            },
            self.secret,
            algorithm="HS256",
        )

    def redact(self, value: str) -> str:
        for sensitive in (
            self.secret,
            self.password,
            self.anon,
            self.service,
            getattr(self, "owner_token", ""),
            getattr(self, "client_token", ""),
            getattr(self, "foreign_token", ""),
            getattr(self, "workflow_client_token", ""),
            getattr(self, "fixture_password_hash", ""),
        ):
            if sensitive:
                value = value.replace(sensitive, "[redacted synthetic credential]")
        value = re.sub(
            r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
            "[redacted JWT]",
            value,
        )
        value = re.sub(r"\b[0-9]{6}\b", "[redacted possible OTP]", value)
        return re.sub(r"(?i)(X-Amz-Signature=)[a-f0-9]+", r"\1[redacted]", value)

    def docker(self, *args: str, input: str | None = None) -> str:
        result = subprocess.run(
            ["docker", *args], input=input, text=True, capture_output=True, timeout=180
        )
        if result.returncode:
            # Never include Docker environment/command text or generated secrets.
            raise RuntimeError(
                f"Docker operation {args[0]} failed (exit {result.returncode})"
            )
        return result.stdout.strip()

    def container(
        self,
        suffix: str,
        image: str,
        env: dict[str, str],
        ports: dict[int, int],
        *args: str,
    ):
        name = f"{self.name}-{suffix}"
        command = [
            "run",
            "-d",
            "--name",
            name,
            "--label",
            self.label,
            "--network",
            self.name,
            "--network-alias",
            suffix,
            "--cpu-shares",
            "4096",
            "--add-host",
            "host.docker.internal:host-gateway",
        ]
        for host, internal in ports.items():
            command += ["-p", f"127.0.0.1:{host}:{internal}"]
        # Pass values through subprocess environment, not argv or files.
        for key in env:
            command += ["-e", key]
        command += [image, *args]
        result = subprocess.run(
            ["docker", *command],
            env={**os.environ, **env},
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode:
            raise RuntimeError(f"Could not start owned {suffix} container")
        self.containers.append(name)
        print(f"Owned {suffix} container started", flush=True)

    def proxy(self):
        runtime = self

        class Gateway(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_OPTIONS(self):
                self.send_response(204)
                self.cors()
                self.end_headers()

            def cors(self):
                self.send_header("Access-Control-Allow-Origin", runtime.ui)
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "authorization,apikey,content-type,x-client-info,x-supabase-api-version",
                )
                self.send_header(
                    "Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS"
                )

            def forward(self):
                if self.path == "/otp-template":
                    body = b"<h2>ClientProof local login</h2><p>{{ .Token }}</p>"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path.startswith("/auth/v1/"):
                    prefix, target = "/auth/v1", runtime.ports["auth"]
                elif self.path.startswith("/rest/v1/"):
                    prefix, target = "/rest/v1", runtime.ports["rest"]
                else:
                    self.send_error(404)
                    return
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                headers = {
                    key: value
                    for key, value in self.headers.items()
                    if key.lower() not in {"host", "connection", "content-length"}
                }
                connection = http.client.HTTPConnection("127.0.0.1", target, timeout=90)
                try:
                    connection.request(
                        self.command, self.path[len(prefix) :], body, headers
                    )
                    response = connection.getresponse()
                    payload = response.read()
                    self.send_response(response.status)
                    for key, value in response.getheaders():
                        if key.lower() not in {
                            "connection",
                            "transfer-encoding",
                            "content-length",
                            "access-control-allow-origin",
                        }:
                            self.send_header(key, value)
                    self.cors()
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except OSError:
                    try:
                        self.send_error(502)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                finally:
                    connection.close()

            do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = forward

        # GoTrue in Docker must fetch its template through host.docker.internal;
        # Docker Desktop maps that address to the host loopback listener.
        self.gateway = ThreadingHTTPServer(
            ("127.0.0.1", self.ports["gateway"]), Gateway
        )
        threading.Thread(target=self.gateway.serve_forever, daemon=True).start()

    def start_process(
        self, command: list[str], env: dict[str, str], name: str, cwd: Path
    ):
        log = (self.evidence / f"{name}.log").open("w")
        self.logs.append(log)
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env={**os.environ, **env},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.processes.append(process)
        if name == "backend":
            self.server_coverage_expected = True

        def capture():
            assert process.stdout is not None
            for line in process.stdout:
                log.write(self.redact(line))
                log.flush()
            process.stdout.close()

        thread = threading.Thread(target=capture, daemon=True)
        self.log_threads.append(thread)
        thread.start()
        return process

    def request(
        self,
        method: str,
        path: str,
        *,
        body=None,
        token: str | None = None,
        auth: bool = False,
    ):
        url = (
            self.url + "/auth/v1" + path
            if auth
            else self.api + "/api/v1/clientproof" + path
        )
        response = httpx.request(
            method,
            url,
            json=body,
            headers={
                "apikey": self.anon,
                "Authorization": f"Bearer {token or self.service}",
            },
            timeout=90,
        )
        if response.status_code >= 400:
            # Bodies never include session material in error evidence.
            raise RuntimeError(f"{method} {path} returned {response.status_code}")
        return response.json()

    def start(self):
        print(
            "Creating uniquely owned local Auth/PostgREST/Postgres/mail runtime",
            flush=True,
        )
        print(f"Evidence: {self.evidence.relative_to(ROOT)}", flush=True)
        self.docker("network", "create", "--label", self.label, self.name)
        self.network_created = True
        native_postgres = os.environ.get("CP_NATIVE_POSTGRES_BIN_DIR")
        database_host = "db"
        database_port = 5432
        if native_postgres:
            self.native_database = Path(tempfile.mkdtemp(prefix=self.name + "-pg-"))
            result = subprocess.run(
                [
                    str(Path(native_postgres) / "initdb"),
                    "-D",
                    str(self.native_database),
                    "--username=postgres",
                    "--auth=scram-sha-256",
                    "--pwfile=/dev/stdin",
                ],
                input=self.password + "\n",
                text=True,
                capture_output=True,
                timeout=60,
            )
            if result.returncode:
                raise RuntimeError("Owned native PostgreSQL initialization failed")
            # Docker Desktop can preserve its gateway source address when
            # reaching a host loopback listener. SCRAM remains mandatory;
            # postgres itself still listens only on 127.0.0.1 below.
            hba = self.native_database / "pg_hba.conf"
            with hba.open("a") as configuration:
                configuration.write("\nhost all all 0.0.0.0/0 scram-sha-256\n")
            self.start_process(
                [
                    str(Path(native_postgres) / "postgres"),
                    "-D",
                    str(self.native_database),
                    "-h",
                    "127.0.0.1",
                    "-p",
                    str(self.ports["db"]),
                ],
                {},
                "native-postgres",
                self.native_database,
            )
            database_host = "host.docker.internal"
            database_port = self.ports["db"]
        else:
            self.container(
                "db",
                "postgres:17.7-alpine",
                {"POSTGRES_PASSWORD": self.password},
                {self.ports["db"]: 5432},
            )

        def database_ready():
            with psycopg.connect(self.db_url, connect_timeout=2) as connection:
                return connection.execute("select 1").fetchone()

        wait_until(database_ready, "owned PostgreSQL", timeout=180)
        with psycopg.connect(self.db_url, autocommit=True) as connection:
            connection.execute(
                (ROOT / "scripts/local_acceptance/bootstrap.sql").read_text()
            )
        self.container(
            "mail",
            "axllent/mailpit:v1.27.10",
            {},
            {self.ports["mail"]: 8025, self.ports["smtp"]: 1025},
        )
        self.proxy()
        auth_environment = {
            "GOTRUE_API_HOST": "0.0.0.0",
            "GOTRUE_API_PORT": "9999",
            "GOTRUE_API_REQUEST_TIMEOUT": "60s",
            "API_EXTERNAL_URL": self.url,
            "GOTRUE_SITE_URL": self.ui,
            "GOTRUE_URI_ALLOW_LIST": f"{self.ui}/**",
            "GOTRUE_DB_DRIVER": "postgres",
            "GOTRUE_DB_NAMESPACE": "auth",
            "GOTRUE_DB_DATABASE_URL": f"postgres://postgres:{self.password}@{database_host}:{database_port}/postgres?search_path=auth",
            "GOTRUE_JWT_SECRET": self.secret,
            "GOTRUE_JWT_EXP": "3600",
            "GOTRUE_JWT_AUD": "authenticated",
            "GOTRUE_JWT_DEFAULT_GROUP_NAME": "authenticated",
            "GOTRUE_JWT_ADMIN_ROLES": "service_role",
            "GOTRUE_EXTERNAL_EMAIL_ENABLED": "true",
            "GOTRUE_DISABLE_SIGNUP": "false",
            "GOTRUE_MAILER_AUTOCONFIRM": "false",
            "GOTRUE_SMTP_HOST": "mail",
            "GOTRUE_SMTP_PORT": "1025",
            "GOTRUE_SMTP_ADMIN_EMAIL": "local@example.invalid",
            "GOTRUE_SMTP_SENDER_NAME": "ClientProof local test",
            "GOTRUE_SMTP_MAX_FREQUENCY": "1s",
            "GOTRUE_RATE_LIMIT_EMAIL_SENT": "1000",
            "GOTRUE_MAILER_TEMPLATES_MAGIC_LINK": f"http://host.docker.internal:{self.ports['gateway']}/otp-template",
            "GOTRUE_LOG_LEVEL": "error",
        }
        native_auth = os.environ.get("CP_NATIVE_AUTH_BINARY")
        if native_auth:
            auth_environment.update(
                {
                    "GOTRUE_API_HOST": "127.0.0.1",
                    "GOTRUE_API_PORT": str(self.ports["auth"]),
                    "GOTRUE_DB_DATABASE_URL": self.db_url + "?search_path=auth",
                    "GOTRUE_SMTP_HOST": "127.0.0.1",
                    "GOTRUE_SMTP_PORT": str(self.ports["smtp"]),
                    "GOTRUE_MAILER_TEMPLATES_MAGIC_LINK": self.url + "/otp-template",
                }
            )
            # /dev/null explicitly suppresses the upstream default dotenv search.
            self.start_process(
                [native_auth, "--config", "/dev/null"],
                auth_environment,
                "native-auth",
                ROOT,
            )
        else:
            self.container(
                "auth",
                "supabase/gotrue:v2.185.0",
                auth_environment,
                {self.ports["auth"]: 9999},
            )
        wait_until(
            lambda: (
                httpx.get(
                    f"http://127.0.0.1:{self.ports['auth']}/health", timeout=2
                ).is_success
            ),
            "genuine Supabase Auth",
        )
        with psycopg.connect(self.db_url, autocommit=True) as connection:
            for migration in sorted(
                (ROOT / "backend/supabase/migrations").glob("*.sql")
            ):
                connection.execute(migration.read_text())
            connection.execute(
                "grant all on all tables in schema public to service_role"
            )
            connection.execute(
                "grant all on all sequences in schema public to service_role"
            )
            connection.execute(
                "grant execute on all functions in schema public to service_role"
            )
        self.container(
            "rest",
            "postgrest/postgrest:v12.2.12",
            {
                "PGRST_DB_URI": f"postgres://postgres:{self.password}@{database_host}:{database_port}/postgres",
                "PGRST_DB_SCHEMAS": "public",
                "PGRST_DB_ANON_ROLE": "anon",
                "PGRST_JWT_SECRET": self.secret,
                "PGRST_DB_POOL": "2",
                "PGRST_DB_POOL_ACQUISITION_TIMEOUT": "10",
                "PGRST_OPENAPI_MODE": "ignore-privileges",
            },
            {self.ports["rest"]: 3000},
        )
        wait_until(
            lambda: (
                httpx.get(
                    f"http://127.0.0.1:{self.ports['rest']}/projects?select=id&limit=1",
                    headers={"Authorization": "Bearer " + self.service},
                    timeout=10,
                ).is_success
            ),
            "real PostgREST",
        )
        self.container(
            "s3",
            os.environ.get(
                "CP_MINIO_IMAGE", "minio/minio:RELEASE.2025-04-22T22-12-26Z"
            ),
            {
                "MINIO_ROOT_USER": "clientproof-local",
                "MINIO_ROOT_PASSWORD": self.password,
                "MINIO_API_CORS_ALLOW_ORIGIN": self.ui,
            },
            {self.ports["s3"]: 9000},
            "server",
            "/data",
            "--console-address",
            ":9001",
        )
        image = self.docker(
            "image",
            "inspect",
            os.environ.get(
                "CP_MINIO_IMAGE", "minio/minio:RELEASE.2025-04-22T22-12-26Z"
            ),
            "--format",
            "{{json .RepoDigests}}",
        )
        (self.evidence / "storage-image.json").write_text(
            json.dumps(
                {
                    "selected_image": os.environ.get(
                        "CP_MINIO_IMAGE", "minio/minio:RELEASE.2025-04-22T22-12-26Z"
                    ),
                    "repo_digests": json.loads(image),
                    "provider": "local S3-compatible MinIO; hosted R2 unverified",
                },
                indent=2,
            )
        )
        s3_url = f"http://127.0.0.1:{self.ports['s3']}"
        wait_until(
            lambda: httpx.get(s3_url + "/minio/health/ready", timeout=2).is_success,
            "owned private S3-compatible storage",
        )
        s3 = boto3.client(
            "s3",
            endpoint_url=s3_url,
            aws_access_key_id="clientproof-local",
            aws_secret_access_key=self.password,
            region_name="us-east-1",
        )
        s3.create_bucket(Bucket="clientproof-private")
        common = {
            "ENV": "dev",
            "DEV_AUTH_BYPASS_ENABLED": "false",
            "SUPABASE_URL": self.url,
            "SUPABASE_KEY": self.service,
            "CORS_ORIGINS": self.ui,
            "LOG_LEVEL": "WARNING",
            "STRIPE_SECRET_KEY": "",
            "STRIPE_WEBHOOK_SECRET": self.password,
            "AWS_EC2_METADATA_DISABLED": "true",
            "CLOUDFLARE_R2_ENDPOINT": s3_url,
            "CLOUDFLARE_ACCOUNT_ID": "local-acceptance",
            "CLOUDFLARE_ACCESS_KEY": "clientproof-local",
            "CLOUDFLARE_SECRET_ACCESS_KEY": self.password,
            "CLOUDFLARE_R2_BUCKET": "clientproof-private",
            "CLIENTPROOF_FILE_LINK_TTL_SECONDS": "10",
        }
        self.start_process(
            [
                str(PYTHON),
                "-c",
                "import coverage; "
                f"cov=coverage.Coverage(data_file={str(self.evidence / '.coverage-server')!r},source=['app']); "
                "cov.set_option('run:sigterm',True); cov.start(); import uvicorn\n"
                "try:\n"
                f" uvicorn.run('app.main:app',host='127.0.0.1',port={self.ports['api']},access_log=False)\n"
                "finally:\n cov.stop(); cov.save()\n",
            ],
            common,
            "backend",
            ROOT / "backend",
        )
        wait_until(lambda: httpx.get(self.api, timeout=2).is_success, "real FastAPI")
        self.seed()
        self.environment = {
            **common,
            "CLIENTPROOF_TEST_API_URL": self.api,
            "SUPABASE_TEST_URL": self.url,
            "SUPABASE_TEST_KEY": self.service,
            "CLIENTPROOF_DATA_TEST_ADMIN_URL": self.db_url,
            "DATABASE_URL": self.db_url,
            "CP_S3_ENDPOINT": s3_url,
            "CLIENTPROOF_TEST_ORGANIZATION_ID": self.fixture["organization_id"],
            "CLIENTPROOF_TEST_OWNER_TOKEN": self.owner_token,
            "CLIENTPROOF_TEST_CLIENT_TOKEN": self.client_token,
            "CLIENTPROOF_TEST_FOREIGN_TOKEN": self.foreign_token,
            "CLIENTPROOF_TEST_ADMIN_TOKEN": self.agency_admin_token,
            "CLIENTPROOF_TEST_MEMBER_TOKEN": self.agency_member_token,
            "CLIENTPROOF_TEST_INACTIVE_TOKEN": self.inactive_staff_token,
            "CP_FIXTURE_JSON": json.dumps(self.fixture),
            "CP_MAIL_URL": f"http://127.0.0.1:{self.ports['mail']}",
            "CP_ANON_KEY": self.anon,
            "CP_FRONTEND_URL": self.ui,
            "CP_FRONTEND_PORT": str(self.ports["ui"]),
            "VITE_SUPABASE_URL": self.url,
            "VITE_SUPABASE_PUBLISHABLE_DEFAULT_KEY": self.anon,
            "VITE_BACKEND_URL": self.api,
            "PLAYWRIGHT_BROWSERS_PATH": os.environ.get(
                "PLAYWRIGHT_BROWSERS_PATH",
                "/private/tmp/clientproof-playwright-browsers",
            ),
        }

    def seed(self):
        users = {}
        # GoTrue generates and hashes a random password even for an admin user
        # without a supplied password. Use its supported password_hash import
        # with a native cost-10 bcrypt hash when Apache htpasswd is available:
        # this avoids expensive emulated CPU hashing without replacing Auth.
        hasher = shutil.which("htpasswd")
        imported_password = {}
        if hasher:
            result = subprocess.run(
                [hasher, "-niBC", "10", "clientproof-fixture"],
                input=self.password + "\n",
                text=True,
                capture_output=True,
                timeout=15,
            )
            if result.returncode:
                raise RuntimeError("Native fixture bcrypt generation failed")
            self.fixture_password_hash = result.stdout.strip().split(":", 1)[1]
            if not self.fixture_password_hash.startswith("$2"):
                raise RuntimeError("Native fixture bcrypt format unsupported")
            imported_password = {"password_hash": self.fixture_password_hash}
        for kind in (
            "owner",
            "client",
            "foreign",
            "workflow_client",
            "agency_admin",
            "agency_member",
            "inactive_staff",
        ):
            email = f"{kind}-{self.name}@example.invalid"
            user = self.request(
                "POST",
                "/admin/users",
                auth=True,
                body={"email": email, "email_confirm": True, **imported_password},
            )
            link = self.request(
                "POST",
                "/admin/generate_link",
                auth=True,
                body={"type": "magiclink", "email": email},
            )
            signed = self.request(
                "POST",
                "/verify",
                auth=True,
                body={"type": "magiclink", "token_hash": link["hashed_token"]},
            )
            users[kind] = {"id": user["id"], "email": email}
            setattr(self, f"{kind}_token", signed["access_token"])
        with psycopg.connect(self.db_url, autocommit=True) as connection:
            for kind, user in users.items():
                connection.execute(
                    "update users set username=%s where id=%s",
                    (kind + "-" + self.name, user["id"]),
                )
            organization_id = str(
                connection.execute(
                    "select organization_id from memberships where user_id = %s",
                    (users["owner"]["id"],),
                ).fetchone()[0]
            )
            connection.execute(
                "update organizations set billing_is_paid=true, billing_plan_key='team' where id=%s",
                (organization_id,),
            )
            for kind, role, inactive in (
                ("agency_admin", "admin", False),
                ("agency_member", "member", False),
                ("inactive_staff", "admin", True),
            ):
                connection.execute(
                    "insert into memberships (organization_id,user_id,role,deleted_at) "
                    "values (%s,%s,%s,case when %s then now() else null end)",
                    (organization_id, users[kind]["id"], role, inactive),
                )
        client = self.request(
            "POST",
            f"/organizations/{organization_id}/clients",
            token=self.owner_token,
            body={
                "external_auth_user_id": users["client"]["id"],
                "email": users["client"]["email"],
                "display_name": "Внешний клиент",
            },
        )
        projects = {}
        for name in (
            "browser_approved",
            "browser_changes_requested",
            "api_approved",
            "api_changes_requested",
        ):
            project = self.request(
                "POST",
                f"/organizations/{organization_id}/projects",
                token=self.owner_token,
                body={"client_id": client["id"], "name": f"Реальный проект {name}"},
            )
            project_id = project["id"]
            grant = self.request(
                "POST",
                f"/projects/{project_id}/grants",
                token=self.owner_token,
                body={"client_id": client["id"]},
            )
            deliverable = self.request(
                "POST",
                f"/projects/{project_id}/deliverables",
                token=self.owner_token,
                body={"name": "Макет для согласования"},
            )
            version = self.request(
                "POST",
                f"/projects/{project_id}/deliverables/{deliverable['id']}/versions",
                token=self.owner_token,
                body={
                    "title": "Опубликованная версия",
                    "content": "Проверьте реальный результат.",
                },
            )
            self.request(
                "POST",
                f"/projects/{project_id}/versions/{version['id']}/publish",
                token=self.owner_token,
            )
            projects[name] = {
                "project_id": project_id,
                "version_id": version["id"],
                "grant_id": grant["id"],
                "name": project["name"],
            }
        self.fixture = {
            "organization_id": organization_id,
            "client_id": client["id"],
            "users": users,
            "projects": projects,
        }
        print(
            "Real users, personal organizations, grants and published versions created",
            flush=True,
        )

    def verify(self):
        self.start_process(
            ["node", str(ROOT / "scripts/clientproof_frontend_server.mjs")],
            self.environment,
            "frontend",
            ROOT,
        )
        wait_until(lambda: httpx.get(self.ui, timeout=2).is_success, "loopback Vite")
        # Entire existing integration tree, including direct-Postgres concurrency,
        # genuine Supabase signup/memberships and additive real HTTP assertions.
        targets = ["tests/integration"]
        for name, cwd, command in (
            (
                "persisted-api",
                ROOT / "backend",
                [
                    str(PYTHON),
                    "-m",
                    "pytest",
                    *targets,
                    "-q",
                    "--cov=app",
                    "--cov-report=json:"
                    + str(self.evidence / "integration-coverage.json"),
                ],
            ),
            (
                "persisted-browser",
                ROOT / "frontend",
                [
                    "npm",
                    "run",
                    "test:e2e",
                    "--",
                    "--config=playwright.fullstack.config.ts",
                ],
            ),
        ):
            print(f"Running {name}", flush=True)
            test_environment = {**os.environ, **self.environment}
            if name == "persisted-api":
                # In-process API-double tests assert the production default;
                # the separately spawned genuine server retains its actual TTL10.
                test_environment["CLIENTPROOF_FILE_LINK_TTL_SECONDS"] = "300"
            result = subprocess.run(
                command,
                cwd=cwd,
                env=test_environment,
                capture_output=True,
                text=True,
                timeout=600,
            )
            (self.evidence / f"{name}.log").write_text(
                self.redact(result.stdout + result.stderr)
            )
            print(f"{name}: exit {result.returncode}", flush=True)
            if result.returncode:
                raise RuntimeError(f"{name} failed; see its local evidence log")
        with psycopg.connect(self.db_url) as connection:
            decisions = connection.execute(
                "select decision, count(*) from approval_decisions group by decision order by decision"
            ).fetchall()
            comments = connection.execute("select count(*) from comments").fetchone()[0]
            audit = connection.execute(
                "select event_type, count(*) from audit_events group by event_type order by event_type"
            ).fetchall()
        (self.evidence / "persistence.json").write_text(
            json.dumps(
                {"decisions": decisions, "comments": comments, "audit": audit}, indent=2
            )
        )
        assert dict(decisions).get("approved", 0) >= 2
        assert dict(decisions).get("changes_requested", 0) >= 2
        assert comments >= 4

    def cleanup(self):
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        for thread in self.log_threads:
            thread.join(timeout=5)
        for log in self.logs:
            log.close()
        if self.native_database:
            # This fresh directory was created by this invocation, never supplied.
            shutil.rmtree(self.native_database)
        if self.gateway:
            self.gateway.shutdown()
            self.gateway.server_close()
        if self.network_created:
            # Include an owned container if interruption happened just after Docker
            # creation but before its successful return was appended to the list.
            owned = self.docker(
                "ps", "-a", "--filter", f"label={self.label}", "--format", "{{.Names}}"
            )
            for name in owned.splitlines():
                if name not in self.containers:
                    self.containers.append(name)
        for name in reversed(self.containers):
            print(f"Cleaning owned {name.rsplit('-', 1)[-1]} container", flush=True)
            # A matching immutable creation label is mandatory before cleanup.
            label = self.docker(
                "inspect",
                "--format",
                '{{index .Config.Labels "clientproof.acceptance.owner"}}',
                name,
            )
            if label != self.name:
                raise RuntimeError(
                    "Refusing cleanup of a resource without matching ownership"
                )
            logs = subprocess.run(
                ["docker", "logs", "--tail", "80", name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            safe_logs = self.redact(logs.stdout + logs.stderr)
            (self.evidence / f"{name.rsplit('-', 1)[-1]}-container.log").write_text(
                safe_logs
            )
            self.docker("rm", "-fv", name)
        if self.network_created:
            label = self.docker(
                "network",
                "inspect",
                "--format",
                '{{index .Labels "clientproof.acceptance.owner"}}',
                self.name,
            )
            if label != self.name:
                raise RuntimeError(
                    "Refusing cleanup of network without matching ownership"
                )
            self.docker("network", "rm", self.name)

        server_coverage = self.evidence / ".coverage-server"
        if self.server_coverage_expected and not server_coverage.exists():
            raise RuntimeError("Actual HTTP server coverage was not saved")
        if server_coverage.exists():
            # Distinct from pytest-side coverage: these are real HTTP server
            # app lines executed during actual auth/storage/database workflows.
            coverage_json = self.evidence / "domain-coverage.json"
            result = subprocess.run(
                [
                    str(PYTHON),
                    "-m",
                    "coverage",
                    "json",
                    "--data-file=" + str(server_coverage),
                    "--include=app/clientproof/*,app/database/clientproof.py",
                    "-o",
                    str(coverage_json),
                ],
                cwd=ROOT / "backend",
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode:
                raise RuntimeError("Actual server domain coverage export failed")
            shutil.copyfile(
                coverage_json, ROOT / "backend/.coverage-clientproof-domain.json"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--verify", action="store_true")
    arguments = parser.parse_args()

    def interrupted(_signal, _frame):
        raise KeyboardInterrupt(
            "Local acceptance interrupted; cleaning owned resources"
        )

    signal.signal(signal.SIGTERM, interrupted)
    runtime = Runtime()
    outcome = {"status": "fail", "mode": "verify" if arguments.verify else "prepare"}
    try:
        runtime.start()
        if arguments.verify:
            runtime.verify()
        outcome["status"] = "pass"
        print("Local runtime verification passed; cleaning owned resources", flush=True)
    except (Exception, KeyboardInterrupt) as exc:
        outcome["error"] = str(exc)
        print(f"Local runtime failed: {exc}", flush=True)
    finally:
        try:
            runtime.cleanup()
            outcome["cleanup"] = "complete"
        except Exception as exc:
            outcome["cleanup"] = "failed"
            outcome["status"] = "fail"
            print(f"Owned cleanup failed: {exc}", flush=True)
        (runtime.evidence / f"{outcome['mode']}-result.json").write_text(
            json.dumps(outcome, indent=2)
        )
    return 0 if outcome["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
