# 知寻 KnowSeek 后端镜像
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- 阶段 2：测试门禁 ----
# 在这里跑单元测试：测试不通过 -> 本阶段失败 -> 整个镜像构建失败 ->
# deploy.sh 的 build 阶段中止，旧容器继续对外服务，实现"测试不过就不上线"。
# 只跑 tests/ 下不依赖数据库与外部 LLM 的单元测试，保证门禁稳定、秒级完成。
FROM python:3.11-slim AS tester
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
# 关键：可执行入口（uvicorn / pytest 等 console_scripts）装在 /usr/local/bin，必须一并复制
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
RUN python -m pytest tests/ -q

# ---- 阶段 3：运行时（继承 tester，只有测试通过才能产出最终镜像）----
FROM tester AS runtime

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
