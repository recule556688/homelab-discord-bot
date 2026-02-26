FROM python:3.11-slim

WORKDIR /app

# Ensure stdout/stderr are unbuffered (so prints show in docker logs)
ENV PYTHONUNBUFFERED=1

# Create data directory
RUN mkdir -p /app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure proper permissions for the app directory and data
RUN chmod -R 777 /app/data

CMD ["python", "-u", "main.py"]
