FROM python:3.9

WORKDIR /app

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire src directory
COPY src/ /app/

# Create necessary directories for static/template files if they are directly copied (though app.py handles app_data and backups)
# These are for Flask's static/template serving from within the /app directory structure
RUN mkdir -p /app/templates /app/static/css /app/static/js

# Copy template and static files (if they are not already under src/ copied above)
# Assuming src/templates and src/static are the source for these
COPY src/templates/index.html /app/templates/
COPY src/static/css/styles.css /app/static/css/
COPY src/static/js/main.js /app/static/js/

CMD ["python", "app.py"]
