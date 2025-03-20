import os
import qrcode
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64

# AES Secret Key (Must be 16, 24, or 32 bytes)
SECRET_KEY = b'LaireNeilVillena0963912010209770'  # Change this to a strong key

def encrypt_data(plain_text):
    """Encrypt data using AES encryption with PKCS7 padding."""
    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    padded_text = pad(plain_text.encode('utf-8'), AES.block_size)
    encrypted_bytes = cipher.encrypt(padded_text)
    return base64.b64encode(encrypted_bytes).decode('utf-8')

def generate_qr_with_text(student_id, name):
    """Generate an encrypted QR code with student info."""
    encrypted_data = encrypt_data(f"{student_id}|{name}")
    print(f"🔒 Encrypted Data Stored in QR: {encrypted_data}")  # Debugging

    qr_folder = "static/qrcodes"
    os.makedirs(qr_folder, exist_ok=True)
    qr_filename = f"{qr_folder}/{student_id}.png"

    # Generate QR Code with Encrypted Data
    qr = qrcode.make(encrypted_data)
    qr.save(qr_filename)
    
    return qr_filename  # Return path for Flask response
