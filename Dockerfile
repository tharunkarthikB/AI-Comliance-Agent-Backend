# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies, including Tesseract OCR
# This runs as root inside the Docker container, solving the permission issues
RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*

# Copy the dependencies file and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]

