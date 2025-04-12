FROM python:3.11-slim

WORKDIR /app

# Create data directory and set permissions
RUN mkdir -p /app/data && \
    chown -R 1000:1000 /app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

# Set proper permissions for the app directory
RUN chown -R 1000:1000 /app

# Switch to non-root user
USER 1000

CMD ["python", "bot.py"]
