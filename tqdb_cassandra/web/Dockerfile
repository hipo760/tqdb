# TQDB Web Container - Apache + Python CGI
# Base: Python 3.11 slim (Debian-based)
# Purpose: Containerized web interface for TQDB financial data system

FROM python:3.11-slim

LABEL maintainer="TQDB Team"
LABEL description="TQDB Legacy Web Interface - Apache + Python CGI + Python Cassandra Binaries"
LABEL version="1.0"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    apache2 \
    apache2-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    cassandra-driver==3.28.0 \
    python-dateutil

# Enable Apache CGI module
RUN a2enmod cgi && \
    a2enmod rewrite && \
    a2enmod headers && \
    a2enmod deflate

# Create directory structure
RUN mkdir -p /opt/tqdb/tools \
    && mkdir -p /opt/tqdb/python-binaries \
    && mkdir -p /opt/tqdb/scripts \
    && mkdir -p /opt/tqdb/web/cgi-bin \
    && mkdir -p /opt/tqdb/web/html \
    && mkdir -p /var/www/cgi-bin \
    && mkdir -p /var/www/html

# Copy Python binaries (replacement for C++ binaries)
COPY python-binaries/ /opt/tqdb/python-binaries/
RUN chmod +x /opt/tqdb/python-binaries/*.py 2>/dev/null || true

# Copy shell scripts and utilities
COPY scripts/ /opt/tqdb/scripts/
RUN chmod +x /opt/tqdb/scripts/*.sh 2>/dev/null || true \
    && chmod +x /opt/tqdb/scripts/*.py 2>/dev/null || true

# Create symlinks in /opt/tqdb/tools for backward compatibility
RUN ln -s /opt/tqdb/python-binaries /opt/tqdb/tools/python-binaries \
    && ln -s /opt/tqdb/scripts /opt/tqdb/tools/scripts

# Copy CGI scripts
COPY cgi-bin/ /var/www/cgi-bin/
RUN chmod +x /var/www/cgi-bin/*.py 2>/dev/null || true

# Copy static HTML/CSS/JS files
COPY html/ /var/www/html/

# Copy Apache configuration
COPY config/apache.conf /etc/apache2/sites-available/tqdb.conf

# Enable TQDB site and disable default
RUN a2ensite tqdb && \
    a2dissite 000-default

# Set environment variables (can be overridden by docker-compose)
ENV CASSANDRA_HOST=cassandra-node \
    CASSANDRA_PORT=9042 \
    CASSANDRA_KEYSPACE=tqdb1 \
    TOOLS_DIR=/opt/tqdb/tools \
    PYTHONUNBUFFERED=1 \
    TZ=UTC \
    TQDB_ENDPOINT_LOGGING=true \
    TQDB_LOG_DIR=/var/log/apache2

# Configure timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

# Set proper ownership and permissions
RUN chown -R www-data:www-data /var/www/ && \
    chown -R www-data:www-data /opt/tqdb/

# Create temporary directory for query results
RUN mkdir -p /tmp/tqdb && \
    chown www-data:www-data /tmp/tqdb

# Ensure log directory exists and is writable for endpoint logging
RUN mkdir -p /var/log/apache2 && \
    chown -R www-data:www-data /var/log/apache2 && \
    chmod 775 /var/log/apache2

# Expose HTTP port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

# Copy entrypoint script
COPY config/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Switch to entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Default command: start Apache in foreground
CMD ["apache2ctl", "-D", "FOREGROUND"]
