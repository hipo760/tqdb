#!/bin/bash

# Detect OS and set appropriate variables
if [ -f /etc/rocky-release ]; then
    OS_VERSION=$(cat /etc/rocky-release | grep -oE '[0-9]+\.[0-9]+' | head -1)
    echo "Detected Rocky Linux $OS_VERSION"
fi

# Configuration variables
TQDB_FORWEB_DIR=/home/tqdb/codes/tqdb/tools/for_web/
TDIR=/var/www/

# Apache paths - Rocky Linux 9 uses same paths as CentOS 7, but let's be explicit
if [ -d /etc/httpd/conf.d/ ]; then
    APACHE_CONF_DIR=/etc/httpd/conf.d/
    APACHE_MAIN_CONF=/etc/httpd/conf/httpd.conf
    SERVICE_NAME=httpd
elif [ -d /etc/apache2/sites-available/ ]; then
    # Fallback for Ubuntu/Debian style
    APACHE_CONF_DIR=/etc/apache2/sites-available/
    APACHE_MAIN_CONF=/etc/apache2/apache2.conf
    SERVICE_NAME=apache2
else
    echo "Error: Cannot find Apache configuration directory"
    exit 1
fi

echo "Using Apache config dir: $APACHE_CONF_DIR"
echo "Using Apache main config: $APACHE_MAIN_CONF"

# Backup welcome.conf if it exists
if [ -f ${APACHE_CONF_DIR}/welcome.conf ]; then
    mv ${APACHE_CONF_DIR}/welcome.conf ${APACHE_CONF_DIR}/welcome.conf.orig
fi

# Create symbolic link to TQDB vhost config
ln -sf ${TQDB_FORWEB_DIR}/TQDB.vhost.conf ${APACHE_CONF_DIR}/

# Set permissions
chmod -R +x /home/tqdb/
chmod -R +r /home/tqdb/

# Clean and setup web directory
rm -rf ${TDIR}/*
ln -sf ${TQDB_FORWEB_DIR}/cgi-bin ${TDIR}/
ln -sf ${TQDB_FORWEB_DIR}/html ${TDIR}/
ln -sf ${TQDB_FORWEB_DIR}/images/* ${TDIR}/html/ 2>/dev/null || true
ln -sf ${TQDB_FORWEB_DIR}/js ${TDIR}/html/

echo "==== Disable PrivateTmp for Apache with systemd ===="
# Create systemd override directory
sudo mkdir -p /etc/systemd/system/${SERVICE_NAME}.service.d

# Create override configuration
sudo tee /etc/systemd/system/${SERVICE_NAME}.service.d/nopt.conf > /dev/null <<EOF
[Service]
PrivateTmp=false
EOF

# Reload systemd and show service config
sudo systemctl daemon-reload
sudo systemctl cat ${SERVICE_NAME}.service

echo "==== Set HTTP Timeout to 10 mins ===="
# Check if timeout is already set to avoid duplicates
if ! grep -q "^Timeout" ${APACHE_MAIN_CONF}; then
    echo "Timeout 600" | sudo tee -a ${APACHE_MAIN_CONF}
else
    echo "Timeout already configured in ${APACHE_MAIN_CONF}"
fi

echo "==== Enable and start httpd ===="
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}

# Check if service started successfully
if sudo systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "==== Apache started successfully ===="
else
    echo "==== Error: Apache failed to start ===="
    sudo systemctl status ${SERVICE_NAME}
    exit 1
fi

echo "==== All done. ===="