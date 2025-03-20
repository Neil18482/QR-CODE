import os
import csv
import datetime
import qrcode
import mysql.connector
import pandas as pd
import xlsxwriter
from flask import Flask, render_template, request, jsonify, send_file
import re
import unicodedata
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import generate_qr 
from mysql.connector import pooling



app = Flask(__name__)




# ✅ Database Connection Function
db_pool = pooling.MySQLConnectionPool(
    pool_name="mypool",
    pool_size=30,  # Allows 10 concurrent connections
    host="localhost",
    user="root",
    password="",
    database="attendance_system"
)

def get_db_connection():
    """Reuses connections from the pool instead of opening a new one each time."""
    try:
        return db_pool.get_connection()
    except mysql.connector.Error as err:
        print(f"Database Connection Error: {err}")
        return None
# ✅ Database Connection Function END    




# Secret key for AES encryption 
SECRET_KEY = b'LaireNeilVillena0963912010209770'  # Change this to a strong key

def encrypt_data(plain_text):
    """Encrypt data using AES encryption with PKCS7 padding."""
    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    padded_text = pad(plain_text.encode('utf-8'), AES.block_size)  # PKCS7 Padding
    encrypted_bytes = cipher.encrypt(padded_text)
    return base64.b64encode(encrypted_bytes).decode('utf-8')

def decrypt_data(encrypted_text):
    """Decrypt AES encrypted data."""
    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    encrypted_bytes = base64.b64decode(encrypted_text)
    decrypted_data = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)  # Remove padding
    return decrypted_data.decode('utf-8')


@app.route('/decrypt_qr', methods=['POST'])
def decrypt_qr():
    data = request.get_json()
    print(f"📥 Received Data: {data}")  # Debugging
    
    if not data or "qr_data" not in data:
        return jsonify({"success": False, "error": "No QR data received"}), 400  # Handle missing data

    encrypted_qr_data = data.get("qr_data")

    try:
        decrypted_data = decrypt_data(encrypted_qr_data)
        print(f"🔓 Decrypted Data: {decrypted_data}")  # Debugging

        student_id, name = decrypted_data.split("|")

        # Check if the student exists in the database
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT name FROM students WHERE student_id = %s", (student_id,))
        student = cursor.fetchone()
        db.close()

        if student:
            return jsonify({"success": True, "student_id": student_id, "name": name}), 200
        else:
            return jsonify({"success": False, "error": "Student not found!"}), 404
    except Exception as e:
        print(f"❌ Decryption Failed: {e}")  # Debugging
        return jsonify({"success": False, "error": f"Decryption failed: {str(e)}"}), 400
# Secret key for AES encryption END




# SCANNER START
@app.route('/scanner')
def index():
    return render_template("index1.html")
# SCANNER END




# Register_student START
@app.route('/register')
def register_form():
    return render_template("register1.html")
@app.route('/register_student', methods=['POST'])
def register_student():
    data = request.get_json()
    student_id = data.get("student_id")
    name = data.get("name")
    section = data.get("section")
    year_level = data.get("year_level")

    if not all([student_id, name, section, year_level]):
        return jsonify({"error": "Missing required fields."}), 400

    # ✅ Enforce **exact** Student ID
    if not is_valid_student(student_id):  # Pass only student_id
        return jsonify({"error": "Invalid Student ID or Name! Please check your details."}), 403

    try:
        db = get_db_connection()
        if not db:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = db.cursor()

        # ✅ Check if student already exists
        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = %s", (student_id,))
        student_exists = cursor.fetchone()[0] > 0

        # ✅ Generate a new QR Code
        new_qr_path = generate_qr.generate_qr_with_text(student_id, name)

        if student_exists:
            # 🔄 Reset QR if student is already registered
            return jsonify({
                "message": f"QR Code reset successfully for {name}!",
                "qr_path": new_qr_path
            })

        # ✅ If student is new, register them
        cursor.execute(
            "INSERT INTO students (student_id, name, section, year_level) VALUES (%s, %s, %s, %s)", 
            (student_id, name, section, year_level)
        )
        db.commit()

        return jsonify({
            "message": f"Student {name} registered successfully!",
            "qr_path": new_qr_path
        })

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
# Register_student END




# Student Verify START
def is_valid_student(student_id, students=None):
    """
    Checks if the Student ID exists in students.
    """
    if students is None:
        students = read_students_from_csv()
    
    return student_id in students
def normalize_name(name):
    """
    Normalize names for flexible matching:
    - Converts to lowercase
    - Removes extra spaces & dots
    - Supports "First Middle Last" & "Last, First Middle" formats
    """
    if not name:
        return ""
    
    name = unicodedata.normalize('NFKC', name)
    name = re.sub(r"[^\w\s,]", "", name)  # Remove special characters except commas
    name = re.sub(r'\s+', ' ', name).strip().lower()

    if "," in name:
        last_name, first_middle = name.split(",", 1)
        last_name = last_name.strip()
        first_middle = first_middle.strip().split()
        first_name = first_middle[0]
        middle_name = " ".join(first_middle[1:]) if len(first_middle) > 1 else ""
    else:
        parts = name.split()
        if len(parts) == 3:
            first_name, middle_name, last_name = parts
        elif len(parts) == 2:
            first_name, last_name = parts
            middle_name = ""
        else:
            return name.capitalize()
    
    return f"{last_name.capitalize()}, {first_name.capitalize()} {middle_name.capitalize()}".strip()

def read_students_from_csv(csv_filename="students.csv"):
    """Reads student data from CSV and returns a dictionary."""
    if not os.path.exists(csv_filename):
        print(f"ERROR: File not found - {csv_filename}")
        return {}
    
    students = {}
    with open(csv_filename, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            student_id = row.get("STUDENT ID", "").strip()
            full_name = row.get("FULL NAME", "").strip()
            if student_id and full_name:
                students[student_id] = normalize_name(full_name)
    
    return students
# Student Verify END




# Mark Attendance START
@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    data = request.get_json()
    student_id = data.get("student_id")

    if not student_id:
        return jsonify({"error": "Missing student_id"}), 400

    db = get_db_connection()
    if not db:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = db.cursor()

    # ✅ Check if student exists
    cursor.execute("SELECT name FROM students WHERE student_id = %s", (student_id,))
    student = cursor.fetchone()

    if not student:
        cursor.close()
        db.close()
        return jsonify({"error": "Student not found!"}), 404

    student_name = student[0]

    # ✅ Check last scan time
    cursor.execute("SELECT scan_date, scan_time FROM attendance WHERE student_id = %s ORDER BY scan_date DESC, scan_time DESC LIMIT 1", (student_id,))
    last_scan = cursor.fetchone()

    cooldown_seconds = 3600  # 1-hour cooldown

    if last_scan:
        last_scan_date, last_scan_time = last_scan

        # ✅ Ensure last_scan_time is a datetime.time object
        if isinstance(last_scan_time, datetime.timedelta):  
            last_scan_time = (datetime.datetime.min + last_scan_time).time()  

        # ✅ Define `last_scan_datetime`
        last_scan_datetime = datetime.datetime.combine(last_scan_date, last_scan_time)
        current_time = datetime.datetime.now()

        time_diff = (current_time - last_scan_datetime).total_seconds()

        if time_diff < cooldown_seconds:
            cursor.close()
            db.close()
            return jsonify({
                "message": f"⚠️ ALREADY SCANNED RECENTLY!\n\nStudent ID: {student_id}\nName: {student_name}\n\n⏳ Please wait before scanning again.",
                "alert": "warning"
            }), 400

    # ✅ Insert attendance record
    cursor.execute("INSERT INTO attendance (student_id, scan_date, scan_time) VALUES (%s, CURDATE(), CURTIME())", (student_id,))
    db.commit()
    cursor.close()
    db.close()

    return jsonify({
        "message": f"✅ ATTENDANCE MARKED FOR\n\nStudent ID: {student_id}\nName: {student_name}",
        "alert": "success"
    }), 200
# Mark Attendance END




# Download Attendance START
@app.route('/download_attendance')
def download_attendance():
    filename = "attendance_records.xlsx"

    db = get_db_connection()
    if not db:
        return "Database connection error", 500

    with db.cursor(dictionary=True) as cursor:
        cursor.execute("""
            SELECT s.student_id, s.name, s.year_level, s.section, a.scan_date, 
            DATE_FORMAT(a.scan_time, '%l:%i %p') AS scan_time
            FROM students s
            JOIN attendance a ON s.student_id = a.student_id
            ORDER BY a.scan_date DESC, a.scan_time DESC
        """)
        records = cursor.fetchall()

    db.close()

    if not records:
        return jsonify({"error": "No attendance records found!"}), 404

    df = pd.DataFrame(records)

    # ✅ Ensure scan_time is a string
    df["scan_time"] = df["scan_time"].astype(str)

    with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
        # ✅ Write full attendance sheet
        df.to_excel(writer, sheet_name="Attendance", index=False)

        # ✅ Group by Year & Section and create separate sheets
        grouped = df.groupby(["year_level", "section"])
        for (year, section), data in grouped:
            sheet_name = f"{year}_{section}"
            sheet_name = sheet_name[:31]  # Excel sheet name limit

            # Drop year_level & section columns before writing to sheet
            data = data.drop(columns=["year_level", "section"])
            data.to_excel(writer, sheet_name=sheet_name, index=False)

    return send_file(filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
# download_attendance END




# Download Students START
@app.route('/download_students')
def download_students():
    filename = "registered_students.csv"

    db = get_db_connection()
    if not db:
        return jsonify({"error": "Database connection error"}), 500

    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT student_id, name, section, year_level FROM students ORDER BY student_id ASC")
            students = cursor.fetchall()

        db.close()

        # ✅ Check if there are students in the database
        if not students:
            return jsonify({"error": "No registered students found!"}), 404

        # ✅ Ensure the CSV is created before sending
        with open(filename, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Student ID", "Name", "Section", "Year Level"])
            writer.writerows(students)

        # ✅ Check if the file was successfully created
        if not os.path.exists(filename):
            return jsonify({"error": "Failed to generate student records file!"}), 500

        return send_file(filename, as_attachment=True, mimetype='text/csv')

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
# Download Students END




# Reset Attendance START
@app.route('/reset_attendance', methods=['POST'])
def reset_attendance():
    try:
        data = request.get_json()
        if not data or data.get("confirm") != "yes":
            return jsonify({"error": "Reset cancelled.", "alert": "info"}), 400

        db = get_db_connection()
        if not db:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = db.cursor()

        # ✅ Delete all attendance records
        cursor.execute("DELETE FROM attendance")

        db.commit()
        cursor.close()
        db.close()

        return jsonify({
            "message": "✅ All attendance records have been reset successfully!",
            "alert": "success"
        }), 200

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}", "alert": "error"}), 500
# Reset Attendance END




# Reset Students START
@app.route('/reset_students', methods=['POST'])
def reset_students():
    try:
        data = request.get_json()
        if not data or data.get("confirm") != "yes":
            return jsonify({"error": "Reset cancelled.", "alert": "info"}), 400

        db = get_db_connection()
        if not db:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = db.cursor()

        # ✅ Delete only students (DO NOT delete attendance)
        cursor.execute("DELETE FROM students")

        # ✅ Reset students table's auto-increment
        cursor.execute("ALTER TABLE students AUTO_INCREMENT = 1")

        db.commit()
        
        # ✅ Step 3: Delete all QR codes
        qr_folder = "static/qrcodes"
        if os.path.exists(qr_folder):
            for file in os.listdir(qr_folder):
                file_path = os.path.join(qr_folder, file)
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"ERROR: Failed to delete {file}: {e}")

        cursor.close()
        db.close()

        return jsonify({
            "message": "All registered students and QR codes have been reset successfully!",
            "alert": "success"
        }), 200

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
# Reset Students END




if __name__ == '__main__':
    app.run(debug=True)
