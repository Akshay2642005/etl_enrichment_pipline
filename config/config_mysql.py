# ====================================================
# MYSQL DATABASES
# ====================================================

MYSQL_DBS = [
    {
        "system_name": "Maintenance Management System",
        "connection_name": "mysql_mro",
        "db_type": "mysql",
        "credentials": {
            "host": "10.0.2.10",
            "port": 3306,
            "database": "mro_db",
            "username": "root",
            "password": "your_password"
        },
        "extraction_rules": {
            "extract_table_info": True,
            "extract_relations": True
        }
    },
    {
        "system_name": "Crew Management System",
        "connection_name": "mysql_crew",
        "db_type": "mysql",
        "credentials": {
            "host": "10.0.2.11",
            "port": 3306,
            "database": "crew_roster_db",
            "username": "root",
            "password": "your_password"
        },
        "extraction_rules": {
            "extract_table_info": True,
            "extract_relations": True
        }
    },
    {
        "system_name": "Loyalty Program",
        "connection_name": "mysql_loyalty",
        "db_type": "mysql",
        "credentials": {
            "host": "10.0.2.12",
            "port": 3306,
            "database": "frequent_flyer_db",
            "username": "root",
            "password": "your_password"
        },
        "extraction_rules": {
            "extract_table_info": True,
            "extract_relations": True
        }
    },
    {
        "system_name": "Ground Resource System",
        "connection_name": "mysql_ground",
        "db_type": "mysql",
        "credentials": {
            "host": "10.0.2.13",
            "port": 3306,
            "database": "ground_ops_db",
            "username": "root",
            "password": "your_password"
        },
        "extraction_rules": {
            "extract_table_info": True,
            "extract_relations": True
        }
    }
]