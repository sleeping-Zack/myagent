FROM python:3.11-slim

WORKDIR /app

# asyncpg 有预编译 wheel，不需要 libpq-dev
# 只在 wheel 不够用时才需要编译工具
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY . .

RUN mkdir -p /app/static /app/uploads /app/knowledge /app/models \
    && sed -i 's/\r$//' /app/deploy/entrypoint.sh \
    && chmod +x /app/deploy/entrypoint.sh \
    && addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app app \
    && chown -R app:app /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

USER 10001:10001

ENTRYPOINT ["/app/deploy/entrypoint.sh"]
