# 前端阶段：压缩静态脚本，降低浏览器端代码可读性
FROM --platform=$BUILDPLATFORM node:22-slim AS frontend

WORKDIR /src
COPY static ./static
RUN mkdir -p /protected-static \
    && cp -a static/. /protected-static/ \
    && npx --yes terser@5 static/app.js --compress --mangle --comments false --output /protected-static/app.js

# 构建阶段：包含源码，仅用于生成受保护运行目录
FROM --platform=$BUILDPLATFORM python:3.12-slim AS builder

WORKDIR /src

COPY . .
COPY config/media_organize_category_rules.json config/media_organize_category_rules.json

RUN python - <<'PY'
from pathlib import Path
import py_compile
import shutil

src = Path('/src')
out = Path('/protected')

if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)

copy_dirs = ['templates', 'fonts']
for name in copy_dirs:
    path = src / name
    if path.exists():
        shutil.copytree(path, out / name)

for name in ['static', 'config', 'backups', 'layouts', 'defaults']:
    (out / name).mkdir(parents=True, exist_ok=True)

rules = src / 'config' / 'media_organize_category_rules.json'
if rules.exists():
    (out / 'config').mkdir(parents=True, exist_ok=True)
    shutil.copy2(rules, out / 'config' / rules.name)

for name in ['requirements.txt']:
    path = src / name
    if path.exists():
        shutil.copy2(path, out / name)

for folder in ['app', 'core']:
    base = src / folder
    if base.exists():
        for path in base.rglob('*'):
            rel = path.relative_to(src)
            if path.is_dir():
                (out / rel).mkdir(parents=True, exist_ok=True)
            elif path.suffix == '.py':
                target = out / rel.with_suffix(path.suffix + 'c')
                target.parent.mkdir(parents=True, exist_ok=True)
                py_compile.compile(str(path), cfile=str(target), doraise=True)
            elif '__pycache__' not in path.parts:
                target = out / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)

for name in ['main.py', 'client.py', 'config_manager.py', 'constants.py', 'utils.py']:
    path = src / name
    if path.exists():
        py_compile.compile(str(path), cfile=str(out / f'{name}c'), doraise=True)

layouts = src / 'layouts'
if layouts.exists():
    for path in layouts.iterdir():
        if path.is_file() and path.suffix == '.py' and path.name != '__init__.py':
            py_compile.compile(str(path), cfile=str(out / 'layouts' / f'{path.name}c'), doraise=True)
        elif path.is_file() and path.name != '__init__.py':
            shutil.copy2(path, out / 'layouts' / path.name)

for folder in ['config', 'templates', 'layouts', 'fonts']:
    source = out / folder
    target = out / 'defaults' / folder
    target.mkdir(parents=True, exist_ok=True)
    if source.exists():
        for item in source.iterdir():
            dest = target / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
PY

# 运行阶段：只复制编译后的代码与资源，不包含源码层
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai
ARG CHILLPOSTER_VERSION=vdev
ARG BUILD_DATE
LABEL org.opencontainers.image.version=$CHILLPOSTER_VERSION
LABEL org.opencontainers.image.created=$BUILD_DATE
RUN echo "$CHILLPOSTER_VERSION" > /app/VERSION

RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ffmpeg \
    libfreetype6-dev \
    libfribidi-dev \
    libharfbuzz-dev \
    libjpeg-dev \
    zlib1g-dev \
    libimagequant-dev \
    libraqm-dev \
    libtiff-dev \
    libwebp-dev \
    tcl8.6-dev \
    tk8.6-dev \
    python3-tk \
    && ln -fs /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /protected/requirements.txt .
RUN pip install --no-cache-dir --default-timeout=300 -r requirements.txt
RUN playwright install --with-deps chromium

COPY --from=builder /protected/ .
COPY --from=frontend /protected-static/ static/

EXPOSE 5256
VOLUME ["/app/config", "/app/templates", "/app/layouts", "/app/fonts", "/app/backups"]
CMD ["python", "main.pyc"]
