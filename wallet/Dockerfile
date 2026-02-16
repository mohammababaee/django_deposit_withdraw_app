# Use Python 3.10 slim
FROM python:3.10-slim

# Set workdir
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command (can be overridden in docker-compose)
CMD ["gunicorn", "wallet.wsgi:application", "--bind", "0.0.0.0:8000"]
