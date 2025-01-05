FROM python:3.9

WORKDIR /app

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire src directory
COPY src/ /app/

# Create necessary directories
RUN mkdir -p /app/templates /app/static/css /app/static/js

# Copy template and static files
COPY src/templates/index.html /app/templates/
COPY src/static/css/styles.css /app/static/css/
COPY src/static/js/main.js /app/static/js/

CMD ["python", "app.py"]