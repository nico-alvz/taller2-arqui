FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/auth_service
ENV PYTHONPATH=/app
CMD ["bash", "-c", "python auth_service/seeder.py && uvicorn auth_service.main:app --host 0.0.0.0 --port 8000"]
EXPOSE 8000