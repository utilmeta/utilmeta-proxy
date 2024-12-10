#!/bin/bash

set -e

DEFAULT_PORT=5432

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

install_postgresql() {
    local package_manager
    package_manager=$(detect_package_manager)

    echo "Installing PostgreSQL using $package_manager..."
    if [[ "$package_manager" == "apt" ]]; then
        sudo apt update
        sudo apt install -y postgresql
    elif [[ "$package_manager" == "yum" ]]; then
        sudo yum install -y postgresql-server postgresql-contrib
        sudo postgresql-setup initdb  # Initialize PostgreSQL database on RHEL-based systems
        sudo systemctl enable postgresql  # Enable PostgreSQL at boot
    fi
}

get_postgresql_version() {
    # Extract the PostgreSQL version
    psql_version=$(psql --version | awk '{print $3}' | cut -d. -f1,2)
    echo "$psql_version"
}

configure_postgresql_port() {
    local port=$1
    local version
    version=$(get_postgresql_version)
    local config_file="/etc/postgresql/$version/main/postgresql.conf"

    if [[ -f $config_file ]]; then
        echo "Configuring PostgreSQL to use port $port in $config_file..."
        sudo sed -i "s/^#port = .*/port = $port/" $config_file
        sudo sed -i "s/^port = .*/port = $port/" $config_file
    else
        echo "Configuration file $config_file not found for PostgreSQL version $version!"
        exit 1
    fi
}

start_postgresql() {
    echo "Starting PostgreSQL service..."
    sudo systemctl restart postgresql
}

check_database_exists() {
    local db_name=$1
    sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$db_name';" | grep -q 1
}

create_database() {
    local db_name=$1
    echo "Creating database '$db_name'..."
    sudo -u postgres psql -c "CREATE DATABASE $db_name;"
}

check_user_exists() {
    local user=$1
    sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$user';" | grep -q 1
}

# Function to create a user if it does not exist
create_user() {
    local user=$1
    local pass=$2
    echo "Creating user $user..."
    sudo -u postgres psql -c "CREATE USER $user WITH PASSWORD '$pass';"
}

# Function to grant access to the user
grant_access() {
    local user=$1
    local db_name=$2
    echo "Granting access to user $user on database $db_name..."
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $db_name TO $user;"
}

# Main Script
# echo "Enter the port for PostgreSQL (default is 5432):"
# read -r port
# port=${port:-$DEFAULT_PORT}  # Use default port if no input is provided
# echo "Enter the name of the database to create:"
# read -r db_name

# Check if PostgreSQL is installed
if ! command -v psql >/dev/null 2>&1; then
    install_postgresql
else
    echo "PostgreSQL is already installed."
fi

# Configure PostgreSQL port only if it's not the default
if [[ "$port" -ne $DEFAULT_PORT ]]; then
    configure_postgresql_port "$port"
fi

# Start PostgreSQL service
start_postgresql

read -r -a databases <<< "$db_names"
# db names separate with space
# db_names="db1 db2"

for db in "${databases[@]}"; do
    # Check if the database exists, create if it doesn't
    if ! check_db_exists "$db"; then
        create_database "$db"
    else
        echo "Database $db already exists."
    fi
done

if ! check_user_exists "$username"; then
    create_user "$username" "$password"
else
    echo "User $username already exists."
fi

# Grant access to the user for each database
for db in "${databases[@]}"; do
    grant_access "$username" "$db"
done