import mysql.connector
import csv

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="attendance_system"
)

cursor = db.cursor()

try:
    with open("students.csv", newline='', encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip header
        for row in reader:
            cursor.execute(
                "INSERT INTO students (student_id, name, section, year_level) VALUES (%s, %s, %s, %s)", 
                (row[0], row[1], row[2], row[3])
            )
    db.commit()
    print("✅ Students imported successfully!")  # ✅ Success message
except Exception as e:
    print(f"❌ Error importing students: {e}")  # ❌ Show error if CSV import fails
finally:
    cursor.close()
    db.close()  # ✅ Ensures connection is always closed
