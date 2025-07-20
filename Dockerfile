FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    cmake \
    g++ \
    libboost-all-dev \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy files
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Run app
CMD ["gunicorn", "app:app"]
