#!/bin/bash

set -e

DEFAULT_PORT=3306

# Functions
detect_package_manager() {
    if command -v apt >/dev/null 2>&1; then
        echo "apt"
    elif command -v yum >/dev/null 2>&1; then
        echo "yum"
    else
        echo "Unsupported system: no apt or yum found."
        exit 1
    fi
}

install_mysql() {
    local package_manager
    package_manager=$(detect_package_manager)

    echo "Installing MySQL using $package_manager..."
    if [[ "$package_manager" == "apt" ]]; then
        sudo apt update
        sudo apt install -y mysql-server
    elif [[ "$package_manager" == "yum" ]]; then
        sudo yum install -y mysql-server
        sudo systemctl enable mysqld  # Enable MySQL service at boot on RHEL-based systems
    fi
}

configure_mysql_port() {
    local port=$1
    local config_file="/etc/mysql/mysql.conf.d/mysqld.cnf"

    if [[ -f $config_file ]]; then
        echo "Configuring MySQL to use port $port in $config_file..."
        sudo sed -i "s/^#port.*/port = $port/" $config_file
        sudo sed -i "s/^port.*/port = $port/" $config_file
    else
        echo "Configuration file $config_file not found!"
        exit 1
    fi
}

start_mysql() {
    echo "Starting MySQL service..."
    sudo systemctl restart mysql
}

check_db_exists() {
    local db_name=$1
    mysql -u root -e "SHOW DATABASES LIKE '$db_name';" | grep -q "$db_name"
}

create_database() {
    local db_name=$1
    echo "Creating database '$db_name'..."
    mysql -u root -e "CREATE DATABASE $db_name;"
}

check_user_exists() {
    local user=$1
    mysql -u root -e "SELECT User FROM mysql.user WHERE User = '$user';" | grep -q "$user"
}

# Function to create a user if it does not exist
create_user() {
    local user=$1
    local pass=$2
    echo "Creating user $user..."
    mysql -u root -e "CREATE USER '$user'@'%' IDENTIFIED BY '$pass';"
}

# Check if MySQL is installed
if ! command -v mysql >/dev/null 2>&1; then
    install_mysql
else
    echo "MySQL is already installed."
fi

# Configure MySQL port only if it's not the default
if [[ "$port" -ne $DEFAULT_PORT ]]; then
    configure_mysql_port "$port"
else
    echo "MySQL is already configured to use the default port $DEFAULT_PORT."
fi

# Start MySQL service
start_mysql

read -r -a databases <<< "$db_names"
for db in "${databases[@]}"; do
    # Check if the database exists, create if it doesn't
    if ! check_db_exists "$db"; then
        create_database "$db"
    else
        echo "Database $db already exists."
    fi
done

# Check if the user exists, create if it doesn't
if ! check_user_exists "$username"; then
    create_user "$username" "$password"
else
    echo "User $username already exists."
fi

# Grant access to the user for each database
for db in "${databases[@]}"; do
    grant_access "$username" "$db"
done
