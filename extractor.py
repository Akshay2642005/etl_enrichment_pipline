import os
import json
import psycopg2
import mysql.connector

# Import configurations from the 'config' module
from config.config_global import GLOBAL_PIPELINE, CONNECTOR_SETTINGS
from config.config_postgres import POSTGRES_DBS
from config.config_mysql import MYSQL_DBS

# Combine all imported database configs into one master list
ALL_DATABASES = POSTGRES_DBS + MYSQL_DBS
OUTPUT_FILE = CONNECTOR_SETTINGS["output_file"]

def main():
    print("=======================================")
    print("🚀 STARTING ETL ENRICHMENT PIPELINE (JSON MODE)")
    print("=======================================\n")

    # Master dictionary to hold the entire pipeline's output
    master_json_data = {
        "metadata": {
            "environment": GLOBAL_PIPELINE["environment"],
            "status": "success"
        },
        "systems": {}
    }

    for db in ALL_DATABASES:
        system_name = db['system_name']
        print(f"Connecting to: {system_name} [{db['db_type'].upper()}]")
        
        # Initialize the JSON structure for this specific database
        master_json_data["systems"][system_name] = {
            "database_type": db["db_type"],
            "columns": [],
            "views": [],
            "relationships": []
        }

        db_type = db["db_type"]
        creds = db["credentials"]
        rules = db["extraction_rules"]

        try:
            # ==========================================
            # POSTGRESQL EXTRACTION LOGIC
            # ==========================================
            if db_type == "postgres":
                conn = psycopg2.connect(**creds)
                cursor = conn.cursor()
                
                if rules.get("extract_table_info"):
                    print("   -> Extracting Columns...")
                    cursor.execute("""
                        SELECT table_name, column_name, data_type, character_maximum_length 
                        FROM information_schema.columns 
                        WHERE table_schema='public';
                    """)
                    for row in cursor.fetchall():
                        # Append as a structured dictionary instead of text
                        master_json_data["systems"][system_name]["columns"].append({
                            "table_name": row[0],
                            "column_name": row[1],
                            "data_type": row[2],
                            "max_length": row[3]
                        })
                
                if rules.get("extract_ddl_views"):
                    print("   -> Extracting View Definitions...")
                    cursor.execute("""
                        SELECT table_name, view_definition 
                        FROM information_schema.views 
                        WHERE table_schema='public';
                    """)
                    for row in cursor.fetchall():
                        master_json_data["systems"][system_name]["views"].append({
                            "view_name": row[0],
                            "definition": row[1]
                        })

                conn.close()
                print("   [✓] Postgres Extraction Complete.\n")

            # ==========================================
            # MYSQL EXTRACTION LOGIC
            # ==========================================
            elif db_type == "mysql":
                conn = mysql.connector.connect(**creds)
                cursor = conn.cursor()
                
                if rules.get("extract_table_info"):
                    print("   -> Extracting Columns...")
                    cursor.execute(f"""
                        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA='{creds["database"]}';
                    """)
                    for row in cursor.fetchall():
                        master_json_data["systems"][system_name]["columns"].append({
                            "table_name": row[0],
                            "column_name": row[1],
                            "data_type": row[2],
                            "max_length": row[3]
                        })

                if rules.get("extract_relations"):
                    print("   -> Extracting Relationships...")
                    cursor.execute(f"""
                        SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
                        WHERE REFERENCED_TABLE_NAME IS NOT NULL 
                        AND TABLE_SCHEMA='{creds["database"]}';
                    """)
                    for row in cursor.fetchall():
                        master_json_data["systems"][system_name]["relationships"].append({
                            "source_table": row[0],
                            "source_column": row[1],
                            "target_table": row[2],
                            "target_column": row[3]
                        })

                conn.close()
                print("   [✓] MySQL Extraction Complete.\n")

        except Exception as e:
            print(f"   [!] FAILED to connect or extract from {db['system_name']}.")
            print(f"       Error Details: {e}\n")
            # Log the error directly into the JSON output for debugging
            master_json_data["systems"][system_name]["error"] = str(e)

    # Dump the completed dictionary into a formatted JSON file
    with open(OUTPUT_FILE, 'w') as json_file:
        json.dump(master_json_data, json_file, indent=4)

    print("=======================================")
    print(f"✅ PIPELINE FINISHED. JSON saved to '{OUTPUT_FILE}'.")
    print("=======================================")

if __name__ == "__main__":
    main()