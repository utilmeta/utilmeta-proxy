#!/bin/bash

set -e

# Check if the script is run as root
#if [ "$EUID" -ne 0 ]; then
#  echo "Please run as root."
#  exit 1
#fi

if [ -z "$DOMAIN" ]; then
  echo "Domain name cannot be empty."
  exit 1
fi

# Detect OS
if [ -f /etc/debian_version ]; then
  OS="debian"
elif [ -f /etc/redhat-release ]; then
  OS="rhel"
else
  echo "Unsupported OS. This script supports Debian-based and RHEL-based systems only."
  exit 1
fi

# Install necessary packages
echo "Installing necessary packages..."
if [ "$OS" = "debian" ]; then
  apt update
  apt install -y nginx certbot python3-certbot-nginx
elif [ "$OS" = "rhel" ]; then
  yum install -y epel-release
  yum install -y nginx certbot python3-certbot-nginx
  systemctl enable --now firewalld
  firewall-cmd --permanent --add-service=http
  firewall-cmd --permanent --add-service=https
  firewall-cmd --reload
fi

# Start and enable Nginx
echo "Starting Nginx..."
systemctl start nginx
systemctl enable nginx

# Create a basic Nginx server block
echo "Creating Nginx server block for $DOMAIN..."
NGINX_CONF="/etc/nginx/conf.d/$DOMAIN.conf"
cat > $NGINX_CONF <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location /api/{
	      proxy_pass http://127.0.0.1:$PORT/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header REMOTE_ADDR $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Test and reload Nginx
nginx -t && nginx -s reload

# Obtain an SSL certificate
echo "Obtaining SSL certificate for $DOMAIN..."
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN

# Set up automatic renewal
echo "Setting up automatic renewal..."
if ! crontab -l | grep -q "certbot renew"; then
  (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --nginx") | crontab -
fi

echo "Nginx and SSL certificate setup complete!"
echo "You can access your website at https://$DOMAIN"
