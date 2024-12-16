#!/bin/bash

# Function to detect CentOS/RedHat version
get_rhel_version() {
  # Extract the major version from /etc/os-release
  . /etc/os-release
  echo $VERSION_ID | cut -d'.' -f1
}

# Get the RHEL/CentOS version
RHEL_VERSION=$(get_rhel_version)

sudo yum groupinstall "Development Tools" -y

# Install MariaDB-devel or MySQL Community repo based on the detected version
if [ "$RHEL_VERSION" -eq 7 ]; then
  # For CentOS/RHEL 7.x, use MySQL 5.7 or higher
  sudo rpm -Uvh https://dev.mysql.com/get/mysql57-community-release-el7-11.noarch.rpm
elif [ "$RHEL_VERSION" -eq 8 ]; then
  # For CentOS/RHEL 8.x, use MySQL 8.0
  sudo rpm -Uvh https://dev.mysql.com/get/mysql80-community-release-el8-3.noarch.rpm
elif [ "$RHEL_VERSION" -eq 9 ]; then
  sudo rpm -Uvh https://dev.mysql.com/get/mysql84-community-release-el9-1.noarch.rpm
else
  sudo rpm -Uvh https://dev.mysql.com/get/mysql84-community-release-el9-1.noarch.rpm
fi

sudo yum install -y mysql-community-devel python3-devel
