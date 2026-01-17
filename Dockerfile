FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Upgrade pip to latest version
RUN pip install --upgrade pip

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY fake_smsc.py .

# Expose SMPP port (default 2776)
EXPOSE 2776

# Set default command
CMD ["python", "fake_smsc.py"]
