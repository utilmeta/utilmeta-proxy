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

configure_mysql_port_and_host() {
    if [[ $port == "$DEFAULT_PORT" && $host == "$DEFAULT_HOST" ]]; then
        echo "Using default port $DEFAULT_PORT and host $DEFAULT_HOST"
        return
    fi

    if [[ -f /etc/mysql/mysql.conf.d/mysqld.cnf ]]; then
        # Debian-based systems
        local config_file="/etc/mysql/mysql.conf.d/mysqld.cnf"
    elif [[ -f /etc/my.cnf ]]; then
        # RHEL-based systems
        local config_file="/etc/my.cnf"
    else
        echo "MySQL configuration file not found!"
        exit 1
    fi

    echo "Configuring MySQL to use port $port and listen on host $host in $config_file..."

    if [[ "$host" != "127.0.0.1" && "$host" != "localhost" ]]; then
      if grep -q '^bind-address' $config_file; then
          sudo sed -i "s/^bind-address.*/bind-address = $host/" $config_file
      else
          echo "bind-address = $host" | sudo tee -a $config_file
      fi
    fi

    if [[ "$port" -ne $DEFAULT_PORT ]]; then
      if grep -q '^port' $config_file; then
          sudo sed -i "s/^port.*/port = $port/" $config_file
      else
          echo "port = $port" | sudo tee -a $config_file
      fi
    fi
}

start_mysql() {
    local package_manager
    package_manager=$(detect_package_manager)
    echo "Starting MySQL service..."
    if [[ "$package_manager" == "yum" ]]; then
      sudo systemctl start mysqld
    else
      sudo systemctl start mysql
    fi
    # set root password
}

retrieve_temporary_root_password() {
    if [[ -f /var/log/mysqld.log ]]; then
        # RHEL-based systems log
        grep 'temporary password' /var/log/mysqld.log | awk '{print $NF}' | tail -1
    elif [[ -f /var/log/mysql/error.log ]]; then
        # Debian-based systems log
        grep 'temporary password' /var/log/mysql/error.log | awk '{print $NF}' | tail -1
    else
        echo "Temporary root password not found. Please check MySQL logs manually."
        exit 1
    fi
}

check_db_exists() {
    local db_name=$1
    mysql -u root -p"$root_password" --connect-expired-password -e "SHOW DATABASES LIKE '$db_name';" | grep -q "$db_name"
}

create_database() {
    local db_name=$1
    echo "Creating database '$db_name'..."
    mysql -u root -p"$root_password" --connect-expired-password -e "CREATE DATABASE $db_name;"
}

check_user_exists() {
    local user=$1
    mysql -u root -p"$root_password" --connect-expired-password -e "SELECT User FROM mysql.user WHERE User = '$user';" | grep -q "$user"
}

# Function to create a user if it does not exist
create_user() {
    local user=$1
    local pass=$2
    echo "Creating user $user..."
    mysql -u root -p"$root_password" --connect-expired-password -e "CREATE USER '$user'@'%' IDENTIFIED BY '$pass';"
}

grant_access() {
    local user=$1
    local db=$2
    echo "Grant $db to $user..."
    mysql -u root -p"$root_password" --connect-expired-password -e "GRANT ALL PRIVILEGES ON $db.* TO '$user'@'%';"
}

reset_root_password() {
    local temporary_password=$1
    echo "Resetting MySQL root password..."
    mysql -u root -p"$temporary_password" --connect-expired-password -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$password';"
}

root_password=""

# Check if MySQL is installed
if ! command -v mysql >/dev/null 2>&1; then
    install_mysql
else
    echo "MySQL is already installed."
    echo "Enter the MySQL root password (press enter to use temporary password):"
    read -sr root_password
fi

if [ ${#root_password} -eq 0 ]; then
    echo 'using temporary root password to reset password'
    tmp_password=$(retrieve_temporary_root_password)
    reset_root_password "$tmp_password" "$password"
    root_password=$password
fi

# Configure MySQL port only if it's not the default
configure_mysql_port_and_host

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
