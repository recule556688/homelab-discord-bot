FROM python:3.11-slim

WORKDIR /app

# Create data directory
RUN mkdir -p /app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure proper permissions for the app directory and data
RUN chmod -R 777 /app/data

CMD ["python", "main.py"]
