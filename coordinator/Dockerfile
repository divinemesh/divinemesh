FROM python:3.11-slim-bookworm
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY coordinator.py .
EXPOSE 8888
CMD ["python", "coordinator.py"]
