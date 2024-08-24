FROM python:3.9-slim

# Install necessary dependencies
RUN apt-get update && apt-get install -y build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the src folder and all necessary files into the working directory
COPY ./src /app/src

# Copy the environment file
COPY .env.example .env

ENV PYTHONPATH=/app

# Set the default command to run your application
CMD ["python", "/app/src/main.py"]
