#!/usr/bin/env python3
"""Install and verify sources in a disposable copy, without credential files or repo caches."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.npm-cache', '.pnpm-cache', '.uv-cache', '.uv-python', '.npm', '.cache', '.git', '.agent', '.agents', '.codex', '.idea', 'node_modules', '.venv',
            '.pnpm-store', '.npmrc', '.netrc', '.pypirc', '.aws', '.ssh', '.gnupg', 'coverage', 'dist', 'playwright-report', 'test-results',
            '__pycache__', '.pytest_cache', '.ruff_cache', '.mypy_cache', '.codegraph'}


def ignore(directory, names):
    return [name for name in names if name in EXCLUDED or name == '.env'
            or name.startswith('.env.') or name.endswith(('.pem', '.key', '.p12', '.pfx'))
            or name.startswith('.coverage') or name.endswith('.tsbuildinfo')
            or (Path(directory) / name).is_symlink()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.agent/artifacts/completion/clean_install.json')
    args = parser.parse_args()
    args.output = Path(os.path.abspath(args.output))
    args.output.relative_to(ROOT)
    work = Path(tempfile.mkdtemp(prefix='clientproof-clean-', dir='/private/tmp'))
    env = {key: value for key, value in os.environ.items()
           if key in {'PATH', 'HOME', 'USER', 'TMPDIR', 'LANG', 'LC_ALL', 'SYSTEMROOT'}}
    env.update(ENV='test', AWS_EC2_METADATA_DISABLED='true', PYTHONDONTWRITEBYTECODE='1',
               UV_CACHE_DIR=str(work / 'uv-cache'), VITE_SUPABASE_URL='http://127.0.0.1:54321',
               VITE_SUPABASE_PUBLISHABLE_DEFAULT_KEY='local-build-placeholder',
               VITE_BACKEND_URL='http://127.0.0.1:18001', npm_config_cache=str(work / 'npm-cache'),
               npm_config_userconfig='/dev/null', npm_config_globalconfig=str(work / 'absent-global-config'),
               XDG_CONFIG_HOME=str(work / 'config'))
    results = []
    source_hashes = {}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    log_dir = args.output.parent / ('clean_install_logs_' + work.name)
    log_dir.mkdir(exist_ok=True)
    try:
        for part in ('frontend', 'backend'):
            if (ROOT / part).is_symlink():
                raise ValueError('Source root must not be a symlink')
            shutil.copytree(ROOT / part, work / part, ignore=ignore, symlinks=False)
        source_hashes = {str(path.relative_to(work)): hashlib.sha256(path.read_bytes()).hexdigest()
                         for part in ('frontend', 'backend') for path in (work / part).rglob('*')
                         if path.is_file()}
        package = json.loads((work / 'frontend/package.json').read_text())
        manager = package['packageManager']
        pnpm = ['npm', 'exec', '--yes', '--package=' + manager, '--', 'pnpm']
        commands = [
            ('backend-install', 'backend', ['uv', '--no-config', 'sync', '--locked']),
            ('frontend-install', 'frontend', pnpm + ['install', '--frozen-lockfile', '--store-dir', str(work / 'pnpm-store')]),
            ('backend-lint', 'backend', ['uv', '--no-config', 'run', '--no-sync', 'ruff', 'check', 'app', 'tests']),
            ('backend-typecheck', 'backend', ['uv', '--no-config', 'run', '--no-sync', 'pyright']),
            ('backend-unit', 'backend', ['uv', '--no-config', 'run', '--no-sync', 'pytest', 'tests/unit', '-q']),
            ('frontend-lint', 'frontend', pnpm + ['lint']),
            ('frontend-typecheck', 'frontend', pnpm + ['typecheck']),
            ('frontend-unit', 'frontend', pnpm + ['test:unit']),
            ('frontend-build', 'frontend', pnpm + ['build']),
        ]
        for name, directory, argv in commands:
            log = log_dir / (name + '.log')
            print(name, flush=True)
            with log.open('w') as stream:
                result = subprocess.run(argv, cwd=work / directory, env=env,
                                        stdout=stream, stderr=subprocess.STDOUT, timeout=600)
            results.append({'id': name, 'argv': argv, 'exit_code': result.returncode,
                            'status': 'pass' if result.returncode == 0 else 'fail',
                            'log': str(log.relative_to(ROOT))})
            if result.returncode:
                break
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        results.append({'id': 'harness', 'status': 'fail', 'reason': type(error).__name__})
    finally:
        status = 'pass' if len(results) == 9 and all(row['status'] == 'pass' for row in results) else 'fail'
        args.output.write_text(json.dumps({'status': status, 'checks': results,
                                         'disposable_copy': str(work), 'store_outside_repo': True, 'source_hashes': source_hashes}, indent=2) + '\n')
        # Only this newly-created directory is removed. No pre-existing cache or DB is touched.
        shutil.rmtree(work)
    return 0 if status == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
