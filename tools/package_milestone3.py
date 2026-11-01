"""Create a small, credential-free M3 code archive from repository source."""

from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / 'submission' / 'milestone3'
    output.mkdir(parents=True, exist_ok=True)
    names = subprocess.check_output(
        ['git', 'ls-files', '-c', '-o', '--exclude-standard', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    excluded = {'.git', '.venv', '.validation', '.pytest_cache', '__pycache__', 'submission', 'node_modules'}
    with ZipFile(output / 'CODE.zip', 'w', ZIP_DEFLATED) as archive:
        for name in sorted(set(filter(None, names))):
            path = Path(name)
            if any(part in excluded for part in path.parts):
                continue
            if path.name in {'.env', '.flaskenv'} or path.suffix in {'.pyc', '.key', '.pem', '.zip'}:
                continue
            if path.parts[0] == 'docs' and not name.startswith('docs/milestone3/'):
                continue
            if (ROOT / path).is_file():
                archive.write(ROOT / path, path.as_posix())
    shutil.copyfile(ROOT / 'README.txt', output / 'README.txt')
    with ZipFile(output / 'CODE.zip') as archive:
        assert archive.testzip() is None
        assert 'README.txt' in archive.namelist()
        assert 'app/milestone3.py' in archive.namelist()
        assert not any('.flaskenv' in name or '.venv/' in name for name in archive.namelist())
        print(f'{len(archive.namelist())} source files, {(output / "CODE.zip").stat().st_size:,} bytes')
    print(output)


if __name__ == '__main__':
    main()
