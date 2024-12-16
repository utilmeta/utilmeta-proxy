#!/bin/bash

set -e

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

echo "Installing nginx"
if [ "$OS" = "debian" ]; then
  sudo apt update
  sudo apt install -y nginx certbot python3-certbot-nginx

elif [ "$OS" = "rhel" ]; then
  sudo yum install -y epel-release
  sudo yum install -y nginx certbot python3-certbot-nginx
fi

#firewall_status=$(sudo systemctl is-active firewalld)
#if [ "$firewall_status" = "active" ]; then
#    echo "configure Firewalld"
#    sudo firewall-cmd --permanent --add-service=http
#    sudo firewall-cmd --permanent --add-service=https
#    sudo firewall-cmd --reload
#fi

# Start and enable Nginx
echo "Starting Nginx..."
sudo systemctl start nginx
sudo systemctl enable nginx

# Create a basic Nginx server block
echo "Creating Nginx server block for $DOMAIN..."
NGINX_CONF="/etc/nginx/conf.d/$DOMAIN.conf"
sudo tee $NGINX_CONF > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location /api/{
	      proxy_pass http://127.0.0.1:$PORT/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header REMOTE_ADDR \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Test and reload Nginx
sudo nginx -t && sudo nginx -s reload

# Obtain an SSL certificate
echo "Obtaining SSL certificate for $DOMAIN..."
sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN

# Set up automatic renewal
echo "Setting up automatic renewal..."
if ! sudo crontab -l | grep -q "certbot renew"; then
  (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --nginx") | sudo crontab -
fi

echo "Nginx and SSL certificate setup complete!"
