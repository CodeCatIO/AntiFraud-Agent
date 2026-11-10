FROM python:3.12.6-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY agent_service ./agent_service
COPY data/knowledge_sources.jsonl ./data/knowledge_sources.jsonl
COPY data/indexes ./data/indexes
COPY scripts ./scripts

EXPOSE 8001

CMD ["uvicorn", "agent_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
