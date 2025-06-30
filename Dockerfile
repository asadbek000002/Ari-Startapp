# Base image
FROM python:3.10

# Working directory
WORKDIR /Ari

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    build-essential \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    libzbar0

# Force GDAL to be version 3.2.2
RUN pip install --no-cache-dir GDAL==3.2.2.1

# Set GDAL environment variables
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Verify GDAL version
RUN gdal-config --version

# Install Python dependencies
COPY requirements_docker.txt /Ari/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements_docker.txt

# Create and set permissions for staticfiles folder
RUN mkdir -p /Ari/staticfiles
RUN chmod 755 /Ari/staticfiles

# Copy project files
COPY . /Ari/

# Collect static files
RUN python manage.py collectstatic --noinput

# Django settings
ENV DJANGO_SETTINGS_MODULE=Ari.settings

# Expose port
EXPOSE 8000

# Run migrations and start Gunicorn server
CMD ["sh", "-c", "python manage.py migrate && daphne -b 0.0.0.0 -p 8000 Ari.asgi:application"]

