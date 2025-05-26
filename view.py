import sqlite3

DATABASE = 'marathon_dashboard.db'  # **IMPORTANT: Replace with your actual database file name**


def view_table_content(table_name):
    conn = None
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        if not rows:
            print(f"No data found in table '{table_name}'.")
            return

        # Print column headers (optional, but helpful)
        column_names = [description[0] for description in cursor.description]
        print(f"\n--- Content of table '{table_name}' ---")
        print(", ".join(column_names))
        print("-" * (len(", ".join(column_names)) + 5))  # Simple separator

        for row in rows:
            print(row)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()


def list_tables():
    conn = None
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        if tables:
            print("\nAvailable Tables:")
            for table in tables:
                print(f"- {table[0]}")
        else:
            print("No tables found in the database.")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    print("Database Viewer Script")
    while True:
        list_tables()
        table_to_view = input(
            "\nEnter the name of the table to view (or 'quit' to exit): "
        ).strip()
        if table_to_view.lower() == 'quit':
            break
        view_table_content(table_to_view)
