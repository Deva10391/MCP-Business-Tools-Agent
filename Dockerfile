FROM python:3.11-slim
RUN apt-get update && apt-get install -y nodejs npm && npm i -g @anthropic-ai/claude-code && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV APPROVER_KEY=change-me
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
