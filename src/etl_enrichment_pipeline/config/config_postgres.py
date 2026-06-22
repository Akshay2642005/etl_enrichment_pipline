# ====================================================
# POSTGRESQL DATABASES
# ====================================================

POSTGRES_DBS = [
    {
        "system_name": "Departure Control System",
        "connection_name": "postgres_dcs",
        "db_type": "postgres",
        "credentials": {
            "host": "10.0.1.15",
            "port": 5432,
            "database": "dcs_prod",
            "username": "admin",
            "password": "your_password"
        },
        "extraction_rules": {
            "extract_table_info": True,
            "extract_ddl_views": True,
            "extract_relations": True
        }
    },
    {
        "system_name": "Passenger Service System",
        "connection_name": "postgres_pss",
        "db_type": "postgres",
        "credentials": {
            "host": "10.0.1.16",
            "port": 5432,
            "database": "pss_core",
            "username": "admin",
            "password": "your_password"
        },
        "extraction_rules": {
            "extract_table_info": True,
            "extract_ddl_views": True,
            "extract_relations": True
        }
    },
    {
        "system_name": "Revenue Management System",
        "connection_name": "postgres_rms",
        "db_type": "postgres",
        "credentials": {
            "host": "10.0.1.17",
            "port": 5432,
            "database": "rms_analytics",
            "username": "admin",
            "password": "your_password"
        },
        "extraction_rules": {
            "extract_table_info": True,
            "extract_ddl_views": True,
            "extract_relations": True
        }
    }
]
