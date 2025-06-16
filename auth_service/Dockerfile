FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/auth_service
ENV PYTHONPATH=/app
CMD ["uvicorn", "auth_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
