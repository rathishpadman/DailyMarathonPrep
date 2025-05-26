#!/bin/bash

# Database connection variables
DB_HOST="0.0.0.0"
DB_PORT="5432"
DB_USER="postgres"  # Replace with your actual PostgreSQL username
DB_NAME="marathon_dashboard"        # Replace with your actual database name

# Check if the database connection variables are set
if [ -z "$DB_USER" ] || [ -z "$DB_NAME" ]; then
  echo "Database user or database name is not set. Please update the script."
  exit 1
fi

# Connect to the PostgreSQL database
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -p $DB_PORT