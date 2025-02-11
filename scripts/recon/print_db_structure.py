import mysql.connector

import sys
sys.path.append("/root/drako/services/main/")
import lib.Common.Utils.Constants as Constants

def print_db_structure(db='recon', host='192.168.1.12', port=6612):
    # Connect to the database
    conn = mysql.connector.connect(host=host, port=port, user="root", password=Constants.DRAGON_DB_PWD, database=db)
    cursor = conn.cursor()

    # Get the list of tables
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()

    # Loop through all tables
    for table in tables:
        table = table[0]
        if not table.startswith('tool_') and not "view" in table and table not in ("unique_ports", "command", "discovered_url", "finding", "job", "log", "report", "report_area", "scan", "setting", "target", "user"):
            # Print table name
            print(f"Table: {table}")
            # Execute DESCRIBE command
            cursor.execute(f"DESCRIBE {table}")
            # Fetch all rows from the last executed statement
            rows = cursor.fetchall()
            # Print table structure
            for row in rows:
                print(row)
            print("\n")  # Print newline to separate tables

    # Close connection
    cursor.close()
    conn.close()

# Usage
print_db_structure()
