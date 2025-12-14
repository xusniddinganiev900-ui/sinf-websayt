from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from apscheduler.schedulers.background import BackgroundScheduler
import json
import os
import random
import atexit
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sinf_secret_key_2024')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB limit
socketio = SocketIO(app, cors_allowed_origins="*")

# Sinflar papkasi
SINFLAR_DIR = 'maktablar'
SINFLAR_FILE = 'sinflar.json'

# Test accountlari - yashirin, cheksiz coin, coin berish imkoniyati
TEST_ACCOUNTS = {
    'Test1': {'parol': 'test111', 'yashirin': True},
    'Test2': {'parol': 'test222', 'yashirin': True},
    'Test3': {'parol': 'test333', 'yashirin': True},
    'Test4': {'parol': 'test444', 'yashirin': True},
    'Test5': {'parol': 'test555', 'yashirin': True},
}

# VIP accountlar - faqat do'stlariga ko'rinadi, coin berish imkoniyati bor
VIP_ACCOUNTS = {
    'P U L K E R E M I Q I Z L A R': {'parol': 'pul2025', 'yashirin': True, 'coin_berish': True},
    '𝐕𝐈𝐏': {'parol': '5202', 'yashirin': True, 'coin_berish': True},
}

# Admin accountlari
ADMINS = {
    'ADMIN': {
        'parol': '3-dimi',
        'tur': 'ochiq',  # Hammaga ko'rinadi
        'ruxsatlar': ['coin_qoshish', 'coin_ayirish', 'bosqich_kotarish', 'ochirish', 'parol_tiklash']
    },
    'HAKER': {
        'parol': 'C.B_2025',
        'tur': 'yopiq',  # Hech kimga ko'rinmaydi
        'ruxsatlar': ['coin_qoshish', 'coin_ayirish', 'bosqich_kotarish', 'bosqich_tushirish',
                      'ochirish', 'parol_tiklash', 'bloklash', 'blokdan_chiqarish',
                      'xabar_oqish', 'admin_bloklash', 'vaqtinchalik_bloklash', 'qarzga_tiqish']
    }
}

# Bloklangan foydalanuvchilar fayli
BLOCKED_FILE = 'blocked_users.json'

def load_blocked():
    if os.path.exists(BLOCKED_FILE):
        with open(BLOCKED_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'blocked': [], 'temp_blocked': {}, 'admin_blocked': []}

def save_blocked(data):
    with open(BLOCKED_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_blocked(username, sinf_id):
    blocked = load_blocked()
    key = f"{sinf_id}:{username}"
    # Doimiy blok
    if key in blocked.get('blocked', []):
        return True
    # Vaqtinchalik blok
    temp = blocked.get('temp_blocked', {}).get(key)
    if temp:
        from datetime import datetime
        if datetime.fromisoformat(temp) > datetime.now():
            return True
        else:
            # Vaqt o'tgan, blokni olib tashlash
            del blocked['temp_blocked'][key]
            save_blocked(blocked)
    return False

# Sinf darajasiga qarab savollar
SAVOLLAR_SINF = {
    # 1-2 sinf uchun oddiy savollar
    1: [
        {"savol": "Kompyuter nima?", "javoblar": ["O'yinchoq", "Elektron qurilma", "Kitob", "Ruchka"], "togri": 1},
        {"savol": "Sichqoncha nima uchun kerak?", "javoblar": ["Yozish", "Ko'rsatish va bosish", "O'chirish", "Chizish"], "togri": 1},
        {"savol": "Klaviatura nima uchun kerak?", "javoblar": ["Rasm chizish", "Yozish", "Tinglash", "Ko'rish"], "togri": 1},
        {"savol": "Monitor nima?", "javoblar": ["Ekran", "Tugma", "Sim", "Quti"], "togri": 0},
        {"savol": "Kompyuterni yoqish uchun nima bosamiz?", "javoblar": ["Sichqonchani", "Tugmani", "Ekranni", "Klaviaturani"], "togri": 1},
        {"savol": "Rasm chizish uchun qaysi dastur?", "javoblar": ["Paint", "Word", "Excel", "Chrome"], "togri": 0},
        {"savol": "1 + 1 = ?", "javoblar": ["1", "2", "3", "4"], "togri": 1},
        {"savol": "Quyosh qaysi rangda?", "javoblar": ["Ko'k", "Sariq", "Qizil", "Yashil"], "togri": 1},
        {"savol": "Olma qaysi rangda bo'ladi?", "javoblar": ["Qizil", "Ko'k", "Oq", "Qora"], "togri": 0},
        {"savol": "Kitob o'qish uchun nima kerak?", "javoblar": ["Ko'zlar", "Quloqlar", "Oyoqlar", "Qo'llar"], "togri": 0},
    ],
    2: [
        {"savol": "Kompyuterda nechta asosiy qism bor?", "javoblar": ["2 ta", "3 ta", "4 ta", "5 ta"], "togri": 2},
        {"savol": "Sichqonchada nechta tugma bor?", "javoblar": ["1 ta", "2 ta", "3 ta", "4 ta"], "togri": 1},
        {"savol": "Monitor nima ko'rsatadi?", "javoblar": ["Ovoz", "Rasm", "Hid", "Issiqlik"], "togri": 1},
        {"savol": "Klaviaturada harflar bormi?", "javoblar": ["Ha", "Yo'q", "Ba'zan", "Bilmayman"], "togri": 0},
        {"savol": "Kompyuter elektr bilan ishlaydimi?", "javoblar": ["Ha", "Yo'q", "Suv bilan", "Shamol bilan"], "togri": 0},
        {"savol": "2 + 3 = ?", "javoblar": ["4", "5", "6", "7"], "togri": 1},
        {"savol": "O'zbek alifbosida nechta harf bor?", "javoblar": ["29", "33", "26", "35"], "togri": 0},
        {"savol": "Hafta necha kundan iborat?", "javoblar": ["5", "6", "7", "8"], "togri": 2},
        {"savol": "Yilda necha oy bor?", "javoblar": ["10", "11", "12", "13"], "togri": 2},
        {"savol": "Kompyuterni o'chirish tugmasi qayerda?", "javoblar": ["Ekranda", "Blokda", "Sichqonchada", "Klaviaturada"], "togri": 1},
    ],
    3: [
        {"savol": "Kompyuterning miyasi qaysi?", "javoblar": ["Monitor", "Protsessor", "Klaviatura", "Sichqoncha"], "togri": 1},
        {"savol": "Faylni saqlash uchun qaysi tugmalarni bosamiz?", "javoblar": ["Ctrl+S", "Ctrl+C", "Ctrl+V", "Ctrl+Z"], "togri": 0},
        {"savol": "Internet nima?", "javoblar": ["Dastur", "Dunyo tarmog'i", "O'yin", "Fayl"], "togri": 1},
        {"savol": "Papka nima uchun kerak?", "javoblar": ["O'yin o'ynash", "Fayllarni saqlash", "Rasm chizish", "Musiqa tinglash"], "togri": 1},
        {"savol": "Brauzer nima?", "javoblar": ["Internet dasturi", "O'yin", "Rasm", "Musiqa"], "togri": 0},
        {"savol": "10 x 2 = ?", "javoblar": ["12", "20", "22", "15"], "togri": 1},
        {"savol": "1 soatda necha minut bor?", "javoblar": ["30", "45", "60", "100"], "togri": 2},
        {"savol": "Eng katta bir xonali son qaysi?", "javoblar": ["8", "9", "10", "7"], "togri": 1},
        {"savol": "Uchburchakning nechta tomoni bor?", "javoblar": ["2", "3", "4", "5"], "togri": 1},
        {"savol": "O'zbekiston poytaxti qayer?", "javoblar": ["Samarqand", "Toshkent", "Buxoro", "Xiva"], "togri": 1},
    ],
    4: [
        {"savol": "RAM nima?", "javoblar": ["Doimiy xotira", "Tezkor xotira", "Ekran", "Printer"], "togri": 1},
        {"savol": "1 kilobayt necha bayt?", "javoblar": ["100", "1000", "1024", "512"], "togri": 2},
        {"savol": "Windows nima?", "javoblar": ["O'yin", "Operatsion tizim", "Brauzer", "Fayl"], "togri": 1},
        {"savol": "Ctrl+C nima qiladi?", "javoblar": ["Kesish", "Nusxa olish", "Qo'yish", "O'chirish"], "togri": 1},
        {"savol": "Ctrl+V nima qiladi?", "javoblar": ["Kesish", "Nusxa olish", "Qo'yish", "Saqlash"], "togri": 2},
        {"savol": "100 ÷ 4 = ?", "javoblar": ["20", "25", "30", "40"], "togri": 1},
        {"savol": "Kvadratning nechta tomoni bor?", "javoblar": ["3", "4", "5", "6"], "togri": 1},
        {"savol": "1 metrda necha santimetr?", "javoblar": ["10", "50", "100", "1000"], "togri": 2},
        {"savol": "1 kilogrammda necha gramm?", "javoblar": ["100", "500", "1000", "10000"], "togri": 2},
        {"savol": "Fayl nima?", "javoblar": ["Papka", "Ma'lumot saqlash joyi", "Dastur", "Kompyuter"], "togri": 1},
    ],
    5: [
        {"savol": "Kompyuterning asosiy qurilmasi qaysi?", "javoblar": ["Monitor", "Klaviatura", "Protsessor", "Sichqoncha"], "togri": 2},
        {"savol": "1 bayt necha bitga teng?", "javoblar": ["4 bit", "8 bit", "16 bit", "32 bit"], "togri": 1},
        {"savol": "Internetga ulanish uchun nima kerak?", "javoblar": ["Printer", "Modem", "Skaner", "Karnay"], "togri": 1},
        {"savol": "Matn muharriri qaysi dastur?", "javoblar": ["Paint", "Word", "Excel", "Chrome"], "togri": 1},
        {"savol": "Qaysi qurilma ma'lumot chiqaradi?", "javoblar": ["Klaviatura", "Sichqoncha", "Monitor", "Mikrofon"], "togri": 2},
        {"savol": "Fayl kengaytmasi .txt nimani bildiradi?", "javoblar": ["Rasm", "Matn", "Video", "Musiqa"], "togri": 1},
        {"savol": "USB - bu nima?", "javoblar": ["Dastur", "Port turi", "Virus", "Fayl"], "togri": 1},
        {"savol": "Qaysi qurilma ma'lumot kiritadi?", "javoblar": ["Printer", "Monitor", "Klaviatura", "Karnay"], "togri": 2},
        {"savol": "Excel nima uchun ishlatiladi?", "javoblar": ["Rasm chizish", "Jadvallar bilan ishlash", "Video ko'rish", "O'yin o'ynash"], "togri": 1},
        {"savol": "Printer nima qiladi?", "javoblar": ["Skanerlaydi", "Chop etadi", "Ovoz chiqaradi", "Ma'lumot kiritadi"], "togri": 1},
    ],
    6: [
        {"savol": "Algoritm nima?", "javoblar": ["Dastur", "Ketma-ket buyruqlar", "Kompyuter", "Fayl"], "togri": 1},
        {"savol": "1 megabayt necha kilobayt?", "javoblar": ["100", "512", "1024", "2048"], "togri": 2},
        {"savol": "PowerPoint nima uchun?", "javoblar": ["Jadval", "Taqdimot", "Matn", "Rasm"], "togri": 1},
        {"savol": "SSD nima?", "javoblar": ["Tezkor disk", "Operativ xotira", "Protsessor", "Videokar"], "togri": 0},
        {"savol": "Dasturlash nima?", "javoblar": ["O'yin o'ynash", "Kod yozish", "Rasm chizish", "Musiqa tinglash"], "togri": 1},
        {"savol": "HTML nima uchun ishlatiladi?", "javoblar": ["O'yin yaratish", "Web sahifa", "Musiqa", "Video"], "togri": 1},
        {"savol": ".exe kengaytmasi nima?", "javoblar": ["Rasm", "Dastur", "Matn", "Video"], "togri": 1},
        {"savol": "Antivirus nima qiladi?", "javoblar": ["Virus yaratadi", "Virusdan himoyalaydi", "O'yin o'ynatadi", "Internet ochadi"], "togri": 1},
        {"savol": "Wi-Fi nima?", "javoblar": ["Simli internet", "Simsiz internet", "Dastur", "Qurilma"], "togri": 1},
        {"savol": "1 gigabayt necha megabayt?", "javoblar": ["100", "512", "1024", "2048"], "togri": 2},
    ],
    7: [
        {"savol": "CPU ning to'liq nomi nima?", "javoblar": ["Central Power Unit", "Central Processing Unit", "Computer Power Unit", "Central Program Unit"], "togri": 1},
        {"savol": "IP-manzil nima?", "javoblar": ["Kompyuter nomi", "Tarmoq manzili", "Dastur", "Fayl turi"], "togri": 1},
        {"savol": "Python nima?", "javoblar": ["Ilon", "Dasturlash tili", "O'yin", "Brauzer"], "togri": 1},
        {"savol": "Binary tizimda qanday raqamlar ishlatiladi?", "javoblar": ["0-9", "0 va 1", "1-10", "A-Z"], "togri": 1},
        {"savol": "Router nima qiladi?", "javoblar": ["Chop etadi", "Tarmoqni ulaydi", "Ovoz chiqaradi", "Rasm ko'rsatadi"], "togri": 1},
        {"savol": "Database nima?", "javoblar": ["Ma'lumotlar bazasi", "Dastur", "Qurilma", "Tarmoq"], "togri": 0},
        {"savol": "CSS nima uchun ishlatiladi?", "javoblar": ["Dasturlash", "Dizayn/Stil", "Hisoblash", "Tarmoq"], "togri": 1},
        {"savol": "Firewall nima?", "javoblar": ["O'yin", "Xavfsizlik devori", "Brauzer", "Virus"], "togri": 1},
        {"savol": "Cloud computing nima?", "javoblar": ["Bulutli hisoblash", "Ob-havo dasturi", "O'yin", "Rasm"], "togri": 0},
        {"savol": "JavaScript qayerda ishlatiladi?", "javoblar": ["Web sahifalar", "Telefon", "Printer", "Skaner"], "togri": 0},
    ],
    8: [
        {"savol": "OOP nima?", "javoblar": ["Obyektga yo'naltirilgan dasturlash", "O'yin dasturi", "Operatsion tizim", "Ofis dasturi"], "togri": 0},
        {"savol": "For loop nima qiladi?", "javoblar": ["Takrorlaydi", "O'chiradi", "Saqlaydi", "Chiqaradi"], "togri": 0},
        {"savol": "Variable nima?", "javoblar": ["O'zgaruvchi", "Funksiya", "Massiv", "Sikl"], "togri": 0},
        {"savol": "Array nima?", "javoblar": ["Massiv", "O'zgaruvchi", "Funksiya", "Sikl"], "togri": 0},
        {"savol": "Function nima qiladi?", "javoblar": ["Vazifani bajaradi", "Xato chiqaradi", "Dasturni o'chiradi", "Hech nima"], "togri": 0},
        {"savol": "If-else nima?", "javoblar": ["Shart operatori", "Sikl", "Massiv", "Funksiya"], "togri": 0},
        {"savol": "Debugging nima?", "javoblar": ["Xatolarni tuzatish", "Dastur yozish", "O'yin o'ynash", "Rasm chizish"], "togri": 0},
        {"savol": "String nima?", "javoblar": ["Matn turi", "Raqam turi", "Mantiqiy tur", "Massiv"], "togri": 0},
        {"savol": "Boolean qanday qiymat oladi?", "javoblar": ["True/False", "Raqamlar", "Harflar", "Belgilar"], "togri": 0},
        {"savol": "SQL nima uchun?", "javoblar": ["Ma'lumotlar bazasi so'rovlari", "Web dizayn", "O'yin yaratish", "Rasm tahrirlash"], "togri": 0},
    ],
    9: [
        {"savol": "Git nima?", "javoblar": ["Versiya nazorati", "Dasturlash tili", "Brauzer", "Operatsion tizim"], "togri": 0},
        {"savol": "API nima?", "javoblar": ["Dastur interfeysi", "Kompyuter", "Tarmoq", "Xotira"], "togri": 0},
        {"savol": "Linux nima?", "javoblar": ["Operatsion tizim", "Dasturlash tili", "Brauzer", "O'yin"], "togri": 0},
        {"savol": "Terminal nima uchun?", "javoblar": ["Buyruqlar kiritish", "Rasm chizish", "O'yin o'ynash", "Video ko'rish"], "togri": 0},
        {"savol": "HTTP nima?", "javoblar": ["Internet protokoli", "Dastur", "Fayl turi", "Qurilma"], "togri": 0},
        {"savol": "JSON nima?", "javoblar": ["Ma'lumot formati", "Dasturlash tili", "Brauzer", "Operatsion tizim"], "togri": 0},
        {"savol": "Framework nima?", "javoblar": ["Dastur asosi", "Kompyuter", "Tarmoq", "Xotira"], "togri": 0},
        {"savol": "IDE nima?", "javoblar": ["Dasturlash muhiti", "O'yin", "Brauzer", "Tarmoq"], "togri": 0},
        {"savol": "Recursion nima?", "javoblar": ["O'zini chaqirish", "Sikl", "Massiv", "O'zgaruvchi"], "togri": 0},
        {"savol": "Encryption nima?", "javoblar": ["Shifrlash", "O'chirish", "Nusxalash", "Ko'chirish"], "togri": 0},
    ],
    10: [
        {"savol": "Machine Learning nima?", "javoblar": ["Mashinali o'rganish", "Kompyuter ta'miri", "Tarmoq", "Dastur"], "togri": 0},
        {"savol": "Neural Network nima?", "javoblar": ["Neyron tarmog'i", "Internet tarmog'i", "Lokal tarmoq", "Uy tarmog'i"], "togri": 0},
        {"savol": "Docker nima?", "javoblar": ["Konteyner platformasi", "O'yin", "Brauzer", "Ofis dasturi"], "togri": 0},
        {"savol": "Kubernetes nima uchun?", "javoblar": ["Konteyner boshqaruvi", "Rasm chizish", "Matn yozish", "Video ko'rish"], "togri": 0},
        {"savol": "REST API nima?", "javoblar": ["Web xizmat arxitekturasi", "O'yin", "Dasturlash tili", "Operatsion tizim"], "togri": 0},
        {"savol": "NoSQL nima?", "javoblar": ["Relyatsion bo'lmagan DB", "SQL turi", "Dasturlash tili", "Tarmoq"], "togri": 0},
        {"savol": "Microservices nima?", "javoblar": ["Kichik xizmatlar arxitekturasi", "Kichik kompyuterlar", "Kichik dasturlar", "Kichik fayllar"], "togri": 0},
        {"savol": "Blockchain nima?", "javoblar": ["Bloklar zanjiri", "O'yin", "Tarmoq kabeli", "Kompyuter turi"], "togri": 0},
        {"savol": "CI/CD nima?", "javoblar": ["Uzluksiz integratsiya", "Kompyuter interfeysi", "C dasturlash tili", "CD disk"], "togri": 0},
        {"savol": "Big Data nima?", "javoblar": ["Katta ma'lumotlar", "Katta kompyuter", "Katta tarmoq", "Katta dastur"], "togri": 0},
    ],
    11: [
        {"savol": "AI va ML orasidagi farq nima?", "javoblar": ["AI kengroq tushuncha", "Farqi yo'q", "ML kengroq", "Bir xil"], "togri": 0},
        {"savol": "Deep Learning nima?", "javoblar": ["Chuqur o'rganish", "Oddiy o'rganish", "Tez o'rganish", "Sekin o'rganish"], "togri": 0},
        {"savol": "Quantum Computing nima?", "javoblar": ["Kvant hisoblash", "Oddiy hisoblash", "Tez hisoblash", "Sekin hisoblash"], "togri": 0},
        {"savol": "DevOps nima?", "javoblar": ["Development + Operations", "Dastur nomi", "Kompyuter turi", "Tarmoq"], "togri": 0},
        {"savol": "Agile nima?", "javoblar": ["Dastur yaratish metodologiyasi", "Dasturlash tili", "Kompyuter", "Tarmoq"], "togri": 0},
        {"savol": "Scrum nima?", "javoblar": ["Loyiha boshqaruvi", "Dasturlash tili", "O'yin", "Tarmoq"], "togri": 0},
        {"savol": "TDD nima?", "javoblar": ["Test Driven Development", "Dastur nomi", "Tarmoq turi", "Kompyuter"], "togri": 0},
        {"savol": "Clean Code nima?", "javoblar": ["Toza kod yozish prinsipi", "Dastur turi", "Tarmoq", "Xotira"], "togri": 0},
        {"savol": "Design Patterns nima?", "javoblar": ["Dizayn naqshlari", "Rasm chizish", "Web dizayn", "Tarmoq dizayni"], "togri": 0},
        {"savol": "SOLID prinsipi nima?", "javoblar": ["OOP prinsiplari", "Qattiq disk", "Tarmoq", "Dastur"], "togri": 0},
    ],
}

# Sinf darajasini aniqlash funksiyasi
def get_sinf_daraja(sinf_nomi):
    """Sinf nomidan daraja raqamini ajratib olish"""
    import re
    # "5-sinf", "5-A sinf", "5 sinf" kabi nomlardan raqamni olish
    match = re.search(r'(\d+)', sinf_nomi)
    if match:
        daraja = int(match.group(1))
        if 1 <= daraja <= 11:
            return daraja
    return 5  # Default 5-sinf

def get_savollar(sinf_id):
    """Sinf uchun mos savollarni olish"""
    sinflar = load_sinflar()
    if sinf_id in sinflar:
        sinf_nomi = sinflar[sinf_id].get('nomi', '')
        daraja = get_sinf_daraja(sinf_nomi)
        return SAVOLLAR_SINF.get(daraja, SAVOLLAR_SINF[5])
    return SAVOLLAR_SINF[5]

# Har soatlik bonus funksiyasi
def soatlik_bonus():
    """Muhammadakbra ga har soatda 200 ball qo'shish"""
    sinf_path = os.path.join(SINFLAR_DIR, 'bizning_sinf', 'oquvchilar.json')
    if os.path.exists(sinf_path):
        with open(sinf_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'Muhammadakbra' in data:
            data['Muhammadakbra']['ball'] = data['Muhammadakbra'].get('ball', 0) + 200
            with open(sinf_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Muhammadakbra ga 200 ball qo'shildi!")

# Scheduler sozlash
scheduler = BackgroundScheduler()
scheduler.add_job(func=soatlik_bonus, trigger="interval", hours=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# Sinflar funksiyalari
def load_sinflar():
    if os.path.exists(SINFLAR_FILE):
        with open(SINFLAR_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    # Default sinf
    default = {
        'bizning_sinf': {
            'nomi': 'Bizning sinf',
            'tavsif': 'Asosiy sinf',
            'icon': '🏫',
            'oquvchilar_soni': 0
        }
    }
    save_sinflar(default)
    return default

def save_sinflar(data):
    with open(SINFLAR_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_sinf_path(sinf_id):
    return os.path.join(SINFLAR_DIR, sinf_id)

def load_data(sinf_id):
    sinf_path = get_sinf_path(sinf_id)
    data_file = os.path.join(sinf_path, 'oquvchilar.json')

    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for ism in data:
                if 'ball' not in data[ism]: data[ism]['ball'] = 0
                if 'bosqich' not in data[ism]: data[ism]['bosqich'] = 1
                if 'mavsum' not in data[ism]: data[ism]['mavsum'] = 1
                if 'avatar' not in data[ism]: data[ism]['avatar'] = 'oddiy'
                if 'gadjetlar' not in data[ism]: data[ism]['gadjetlar'] = []
                if 'bonuslar' not in data[ism]: data[ism]['bonuslar'] = {}
                if 'online' not in data[ism]: data[ism]['online'] = False
            return data
    return {}

def save_data(sinf_id, data):
    sinf_path = get_sinf_path(sinf_id)
    os.makedirs(sinf_path, exist_ok=True)
    data_file = os.path.join(sinf_path, 'oquvchilar.json')
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_chat(sinf_id):
    sinf_path = get_sinf_path(sinf_id)
    chat_file = os.path.join(sinf_path, 'chat_xabarlari.json')
    if os.path.exists(chat_file):
        with open(chat_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_chat(sinf_id, xabarlar):
    sinf_path = get_sinf_path(sinf_id)
    os.makedirs(sinf_path, exist_ok=True)
    chat_file = os.path.join(sinf_path, 'chat_xabarlari.json')
    with open(chat_file, 'w', encoding='utf-8') as f:
        json.dump(xabarlar[-100:], f, ensure_ascii=False, indent=2)

def update_sinf_count(sinf_id):
    sinflar = load_sinflar()
    if sinf_id in sinflar:
        data = load_data(sinf_id)
        sinflar[sinf_id]['oquvchilar_soni'] = len(data)
        save_sinflar(sinflar)

# Eski fayllarni yangi tizimga o'tkazish
def migrate_old_data():
    old_data_file = 'oquvchilar.json'
    old_chat_file = 'chat_xabarlari.json'
    sinf_id = 'bizning_sinf'
    sinf_path = get_sinf_path(sinf_id)

    os.makedirs(sinf_path, exist_ok=True)

    if os.path.exists(old_data_file):
        new_data_file = os.path.join(sinf_path, 'oquvchilar.json')
        if not os.path.exists(new_data_file):
            with open(old_data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            with open(new_data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    if os.path.exists(old_chat_file):
        new_chat_file = os.path.join(sinf_path, 'chat_xabarlari.json')
        if not os.path.exists(new_chat_file):
            with open(old_chat_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            with open(new_chat_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

# Routes
@app.route('/')
def index():
    sinf_id = request.args.get('sinf_id', 'bizning_sinf')
    sinflar = load_sinflar()

    if sinf_id not in sinflar:
        sinf_id = 'bizning_sinf'

    return render_template('index.html',
                         sinf_id=sinf_id,
                         sinf_nomi=sinflar.get(sinf_id, {}).get('nomi', 'Sinf'))

@app.route('/sinflar')
def sinflar():
    sinflar_data = load_sinflar()
    # O'quvchilar sonini yangilash
    for sinf_id in sinflar_data:
        data = load_data(sinf_id)
        sinflar_data[sinf_id]['oquvchilar_soni'] = len(data)
    save_sinflar(sinflar_data)
    return render_template('sinflar.html', sinflar=sinflar_data)

@app.route('/yangi_sinf')
def yangi_sinf():
    return render_template('yangi_sinf.html')

@app.route('/sinf_yaratish', methods=['POST'])
def sinf_yaratish():
    sinf_nomi = request.form.get('sinf_nomi', '').strip()
    tavsif = request.form.get('tavsif', '')
    icon = request.form.get('icon', 'school')

    icons = {'school': '🏫', 'star': '⭐', 'book': '📚', 'rocket': '🚀', 'heart': '❤️', 'fire': '🔥'}

    if not sinf_nomi:
        return render_template('yangi_sinf.html', xato="Sinf nomini kiriting!")

    # Sinf ID yaratish
    sinf_id = sinf_nomi.lower().replace(' ', '_').replace('-', '_')
    sinf_id = ''.join(c for c in sinf_id if c.isalnum() or c == '_')

    sinflar = load_sinflar()

    if sinf_id in sinflar:
        return render_template('yangi_sinf.html', xato="Bu nomdagi sinf mavjud!")

    # Yangi sinf yaratish
    sinflar[sinf_id] = {
        'nomi': sinf_nomi,
        'tavsif': tavsif,
        'icon': icons.get(icon, '🏫'),
        'oquvchilar_soni': 0
    }
    save_sinflar(sinflar)

    # Sinf papkasini yaratish
    sinf_path = get_sinf_path(sinf_id)
    os.makedirs(sinf_path, exist_ok=True)

    return redirect(url_for('index', sinf_id=sinf_id))

@app.route('/kirish', methods=['POST'])
def kirish():
    ism = request.form.get('ism', '').strip()
    parol = request.form.get('parol', '')
    sinf_id = request.form.get('sinf_id', 'bizning_sinf')

    sinflar = load_sinflar()
    data = load_data(sinf_id)

    # Test account tekshirish
    if ism in TEST_ACCOUNTS:
        if TEST_ACCOUNTS[ism]['parol'] == parol:
            # Test accountni yaratish yoki yangilash
            if ism not in data:
                data[ism] = {
                    'parol': parol,
                    'eslatma': '',
                    'jins': 'ogil',
                    'malumot': 'Test account',
                    'ball': 999999,
                    'bosqich': 20,
                    'mavsum': 99,
                    'avatar': 'oddiy',
                    'gadjetlar': [],
                    'bonuslar': {},
                    'online': False,
                    'test_account': True
                }
            else:
                data[ism]['ball'] = 999999  # Har safar cheksiz coin
                data[ism]['test_account'] = True
            save_data(sinf_id, data)

            session['foydalanuvchi'] = ism
            session['sinf_id'] = sinf_id
            session['admin'] = False
            session['test_account'] = True
            return redirect(url_for('home'))
        else:
            return render_template('index.html',
                                 xato="Parol noto'g'ri!",
                                 ism=ism,
                                 sinf_id=sinf_id,
                                 sinf_nomi=sinflar.get(sinf_id, {}).get('nomi', 'Sinf'))

    # VIP account tekshirish
    if ism in VIP_ACCOUNTS:
        if VIP_ACCOUNTS[ism]['parol'] == parol:
            # VIP accountni yaratish yoki yangilash
            if ism not in data:
                data[ism] = {
                    'parol': parol,
                    'eslatma': '',
                    'jins': 'qiz',
                    'malumot': 'VIP account',
                    'ball': 999999,
                    'bosqich': 20,
                    'mavsum': 99,
                    'avatar': 'super_qiz',
                    'gadjetlar': [],
                    'bonuslar': {},
                    'online': False,
                    'vip_account': True,
                    'dostlar': []
                }
            else:
                data[ism]['ball'] = 999999  # Har safar cheksiz coin
                data[ism]['vip_account'] = True
            save_data(sinf_id, data)

            session['foydalanuvchi'] = ism
            session['sinf_id'] = sinf_id
            session['admin'] = False
            session['vip_account'] = True
            return redirect(url_for('home'))
        else:
            return render_template('index.html',
                                 xato="Parol noto'g'ri!",
                                 ism=ism,
                                 sinf_id=sinf_id,
                                 sinf_nomi=sinflar.get(sinf_id, {}).get('nomi', 'Sinf'))

    # Admin tekshirish
    if ism in ADMINS:
        if ADMINS[ism]['parol'] == parol:
            # Admin bloklangan mi?
            blocked = load_blocked()
            if ism in blocked.get('admin_blocked', []):
                return render_template('index.html',
                                     xato="Bu admin bloklangan!",
                                     ism=ism,
                                     sinf_id=sinf_id,
                                     sinf_nomi=sinflar.get(sinf_id, {}).get('nomi', 'Sinf'))
            session['foydalanuvchi'] = ism
            session['sinf_id'] = sinf_id
            session['admin'] = True
            session['admin_tur'] = ADMINS[ism]['tur']
            return redirect(url_for('admin_panel'))
        else:
            return render_template('index.html',
                                 xato="Parol noto'g'ri!",
                                 ism=ism,
                                 sinf_id=sinf_id,
                                 sinf_nomi=sinflar.get(sinf_id, {}).get('nomi', 'Sinf'))

    if ism in data:
        # Bloklangan tekshirish
        if is_blocked(ism, sinf_id):
            return render_template('index.html',
                                 xato="Sizning akkauntingiz bloklangan!",
                                 ism=ism,
                                 sinf_id=sinf_id,
                                 sinf_nomi=sinflar.get(sinf_id, {}).get('nomi', 'Sinf'))
        if data[ism]['parol'] == parol:
            session['foydalanuvchi'] = ism
            session['sinf_id'] = sinf_id
            session['admin'] = False
            return redirect(url_for('home'))
        else:
            eslatma = data[ism].get('eslatma', '')
            return render_template('index.html',
                                 xato="Parol noto'g'ri!",
                                 eslatma=eslatma,
                                 ism=ism,
                                 sinf_id=sinf_id,
                                 sinf_nomi=sinflar.get(sinf_id, {}).get('nomi', 'Sinf'))
    else:
        return render_template('index.html',
                             xato="Bunday foydalanuvchi topilmadi.",
                             ism=ism,
                             sinf_id=sinf_id,
                             sinf_nomi=sinflar.get(sinf_id, {}).get('nomi', 'Sinf'))

@app.route('/royxat')
def royxat():
    sinf_id = request.args.get('sinf_id', 'bizning_sinf')
    return render_template('royxat.html', sinf_id=sinf_id)

@app.route('/royxatdan_otish', methods=['POST'])
def royxatdan_otish():
    ism = request.form.get('ism', '').strip()
    parol = request.form.get('parol', '')
    eslatma = request.form.get('eslatma', '')
    jins = request.form.get('jins', 'ogil')
    malumot = request.form.get('malumot', '')
    sinf_id = request.form.get('sinf_id', 'bizning_sinf')

    if not ism or not parol:
        return render_template('royxat.html', xato="Ism va parol kiritish shart!", sinf_id=sinf_id)

    data = load_data(sinf_id)
    if ism in data:
        return render_template('royxat.html', xato="Bu ism band!", sinf_id=sinf_id)

    data[ism] = {
        'parol': parol,
        'eslatma': eslatma,
        'jins': jins,
        'malumot': malumot,
        'ball': 0,
        'bosqich': 1,
        'mavsum': 1,
        'avatar': 'oddiy',
        'gadjetlar': [],
        'bonuslar': {},
        'online': False
    }
    save_data(sinf_id, data)
    update_sinf_count(sinf_id)

    session['foydalanuvchi'] = ism
    session['sinf_id'] = sinf_id
    return redirect(url_for('home'))

@app.route('/home')
def home():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    if ism not in data:
        session.clear()
        return redirect(url_for('sinflar'))

    data[ism]['online'] = True

    # Test account bo'lsa coinni qayta tiklash
    if session.get('test_account', False):
        data[ism]['ball'] = 999999

    # VIP account bo'lsa coinni qayta tiklash
    if session.get('vip_account', False):
        data[ism]['ball'] = 999999

    save_data(sinf_id, data)

    # Foydalanuvchining do'stlari
    user_friends = data[ism].get('dostlar', [])

    # Test va VIP accountlarni yashirish (VIP faqat do'stlariga ko'rinadi)
    visible_users = {}
    for k, v in data.items():
        # Test accountlarni yashirish
        if v.get('test_account', False) or k in TEST_ACCOUNTS:
            continue
        # VIP accountlarni faqat do'stlariga ko'rsatish
        if v.get('vip_account', False) or k in VIP_ACCOUNTS:
            if k == ism or ism in v.get('dostlar', []):
                visible_users[k] = v
            continue
        visible_users[k] = v

    return render_template('home.html', ism=ism, foydalanuvchi=data[ism],
                         barcha_oquvchilar=visible_users,
                         test_account=session.get('test_account', False),
                         vip_account=session.get('vip_account', False),
                         all_users=visible_users)

@app.route('/jadval')
def jadval():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    if ism not in data:
        session.clear()
        return redirect(url_for('sinflar'))

    # Bugungi kun (0=Dushanba, 5=Shanba)
    from datetime import datetime
    bugun = datetime.now().weekday()
    if bugun > 5:  # Yakshanba
        bugun = 0

    # Jadval ma'lumotlari (sinf uchun)
    jadval_file = os.path.join(SINFLAR_DIR, sinf_id, 'jadval.json')
    if os.path.exists(jadval_file):
        with open(jadval_file, 'r', encoding='utf-8') as f:
            jadval_data = json.load(f)
    else:
        # Default jadval
        jadval_data = {
            "0": [
                {"nomi": "Matematika", "vaqt": "08:00 - 08:45", "oqituvchi": ""},
                {"nomi": "Ona tili", "vaqt": "08:55 - 09:40", "oqituvchi": ""},
                {"nomi": "Ingliz tili", "vaqt": "09:50 - 10:35", "oqituvchi": ""},
                {"nomi": "Tarix", "vaqt": "10:55 - 11:40", "oqituvchi": ""}
            ],
            "1": [
                {"nomi": "Fizika", "vaqt": "08:00 - 08:45", "oqituvchi": ""},
                {"nomi": "Kimyo", "vaqt": "08:55 - 09:40", "oqituvchi": ""},
                {"nomi": "Biologiya", "vaqt": "09:50 - 10:35", "oqituvchi": ""},
                {"nomi": "Informatika", "vaqt": "10:55 - 11:40", "oqituvchi": ""}
            ],
            "2": [
                {"nomi": "Matematika", "vaqt": "08:00 - 08:45", "oqituvchi": ""},
                {"nomi": "Adabiyot", "vaqt": "08:55 - 09:40", "oqituvchi": ""},
                {"nomi": "Geografiya", "vaqt": "09:50 - 10:35", "oqituvchi": ""},
                {"nomi": "Chizmachilik", "vaqt": "10:55 - 11:40", "oqituvchi": ""}
            ],
            "3": [
                {"nomi": "Ingliz tili", "vaqt": "08:00 - 08:45", "oqituvchi": ""},
                {"nomi": "Matematika", "vaqt": "08:55 - 09:40", "oqituvchi": ""},
                {"nomi": "Ona tili", "vaqt": "09:50 - 10:35", "oqituvchi": ""},
                {"nomi": "Jismoniy tarbiya", "vaqt": "10:55 - 11:40", "oqituvchi": ""}
            ],
            "4": [
                {"nomi": "Informatika", "vaqt": "08:00 - 08:45", "oqituvchi": ""},
                {"nomi": "Fizika", "vaqt": "08:55 - 09:40", "oqituvchi": ""},
                {"nomi": "Matematika", "vaqt": "09:50 - 10:35", "oqituvchi": ""},
                {"nomi": "Musiqa", "vaqt": "10:55 - 11:40", "oqituvchi": ""}
            ],
            "5": [
                {"nomi": "Tarix", "vaqt": "08:00 - 08:45", "oqituvchi": ""},
                {"nomi": "Adabiyot", "vaqt": "08:55 - 09:40", "oqituvchi": ""},
                {"nomi": "Rasm", "vaqt": "09:50 - 10:35", "oqituvchi": ""}
            ]
        }

    return render_template('jadval.html',
                         ism=ism,
                         foydalanuvchi=data[ism],
                         jadval=jadval_data,
                         bugun_kun=bugun)

@app.route('/kabinet')
def kabinet():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    if ism not in data:
        return redirect(url_for('sinflar'))

    return render_template('kabinet.html', ism=ism, foydalanuvchi=data[ism])

@app.route('/malumot_saqlash', methods=['POST'])
def malumot_saqlash():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    malumot = request.form.get('malumot', '')

    data = load_data(sinf_id)
    if ism in data:
        data[ism]['malumot'] = malumot
        save_data(sinf_id, data)

    return redirect(url_for('kabinet'))

@app.route('/magazin')
def magazin():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    return render_template('magazin.html', ism=ism, foydalanuvchi=data[ism], mahsulotlar={})

@app.route('/sotib_olish', methods=['POST'])
def sotib_olish():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    mahsulot_id = request.form.get('mahsulot_id')
    narx = int(request.form.get('narx', 0))
    tur = request.form.get('tur')
    soni = int(request.form.get('soni', 1))

    jami_narx = narx * soni

    if data[ism]['ball'] >= jami_narx:
        data[ism]['ball'] -= jami_narx

        if tur == 'avatar':
            data[ism]['avatar'] = mahsulot_id
        elif tur == 'gadjet':
            if mahsulot_id not in data[ism]['gadjetlar']:
                data[ism]['gadjetlar'].append(mahsulot_id)
        elif tur == 'bonus':
            if 'bonuslar' not in data[ism]:
                data[ism]['bonuslar'] = {}
            if mahsulot_id not in data[ism]['bonuslar']:
                data[ism]['bonuslar'][mahsulot_id] = 0
            data[ism]['bonuslar'][mahsulot_id] += soni

        save_data(sinf_id, data)
        return jsonify({'success': True, 'yangi_ball': data[ism]['ball']})
    else:
        return jsonify({'success': False, 'xato': 'Ball yetarli emas!'})

@app.route('/oyin')
def oyin():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    return render_template('oyin.html', ism=ism, foydalanuvchi=data[ism])

# Zar o'yini
@app.route('/zar_oyin')
def zar_oyin():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    return render_template('zar_oyin.html', ism=ism, foydalanuvchi=data[ism])

@app.route('/zar_tashlash', methods=['POST'])
def zar_tashlash():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    if ism not in data:
        return jsonify({'success': False, 'xato': 'Foydalanuvchi topilmadi'})

    # Kuniga 5 marta tashlay oladi
    bugun = str(date.today())
    zar_data = data[ism].get('zar_oyin', {})
    if zar_data.get('sana') != bugun:
        zar_data = {'sana': bugun, 'urinishlar': 0}

    # Test accountlar uchun cheksiz, boshqalar uchun kuniga 5 marta
    if zar_data['urinishlar'] >= 5 and not session.get('test_account', False):
        return jsonify({'success': False, 'xato': 'Bugungi urinishlar tugadi! (5/5)'})

    # Zar tashlash
    zar1 = random.randint(1, 6)
    zar2 = random.randint(1, 6)
    jami = zar1 + zar2

    # Ball hisoblash
    if zar1 == zar2:  # Juftlik
        if zar1 == 6:
            ball = 50  # Ikki 6
        else:
            ball = zar1 * 5  # Juftlik bonusi
    else:
        ball = jami

    zar_data['urinishlar'] += 1
    data[ism]['zar_oyin'] = zar_data
    data[ism]['ball'] = data[ism].get('ball', 0) + ball
    save_data(sinf_id, data)

    return jsonify({
        'success': True,
        'zar1': zar1,
        'zar2': zar2,
        'ball': ball,
        'yangi_ball': data[ism]['ball'],
        'qolgan_urinish': 5 - zar_data['urinishlar']
    })

# Tosh-Qog'oz-Qaychi o'yini
@app.route('/tqq_oyin')
def tqq_oyin():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    return render_template('tqq_oyin.html', ism=ism, foydalanuvchi=data[ism])

@app.route('/tqq_oynash', methods=['POST'])
def tqq_oynash():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req_data = request.get_json()
    user_choice = req_data.get('tanlov')  # tosh, qogoz, qaychi

    choices = ['tosh', 'qogoz', 'qaychi']
    if user_choice not in choices:
        return jsonify({'success': False, 'xato': 'Noto\'g\'ri tanlov'})

    ai_choice = random.choice(choices)

    # Natijani aniqlash
    if user_choice == ai_choice:
        natija = 'durrang'
        ball = 2
    elif (user_choice == 'tosh' and ai_choice == 'qaychi') or \
         (user_choice == 'qaychi' and ai_choice == 'qogoz') or \
         (user_choice == 'qogoz' and ai_choice == 'tosh'):
        natija = 'yutdingiz'
        ball = 5
    else:
        natija = 'yutqazdingiz'
        ball = 0

    data[ism]['ball'] = data[ism].get('ball', 0) + ball
    save_data(sinf_id, data)

    return jsonify({
        'success': True,
        'user_choice': user_choice,
        'ai_choice': ai_choice,
        'natija': natija,
        'ball': ball,
        'yangi_ball': data[ism]['ball']
    })

# Qog'oz o'yini
QOGOZ_ROOMS = {}  # {room_code: {players: [], answers: [], current_turn: 0, started: False}}

# AI javoblari - har bir savol uchun
AI_JAVOBLAR = {
    'kim': [
        "Prezident", "Kosmik kema kapitani", "Uch boshli ajdaho", "Kuchukcha Bobik",
        "Marslik", "Sehrgar", "Robotlar qiroli", "Talking Tom", "SpongeBob",
        "Yolg'on gapiradigan bo'ri", "Cho'ponning qo'yi", "Maymun Joji",
        "O'qituvchi", "Futbolchi Ronaldo", "Super qahramon", "Ninja",
        "Qush Tviti", "Mushuk Leopold", "Dasturchi", "Blogger", "Tiktoker"
    ],
    'qachon': [
        "Kecha tunda", "100 yil oldin", "Ertaga ertalab", "Tushda",
        "Yangi yil kechasi", "Dinozavrlar davrida", "3021 yilda",
        "Oy tutilganda", "Soat 3 da", "Nonushta paytida", "Imtihon vaqtida",
        "Yomg'ir yog'ayotganda", "Qor yog'ayotganda", "Kechqurun",
        "Dam olish kunida", "Maktab paytida", "Uxlayotganda", "Kanikul vaqtida"
    ],
    'kim_bilan': [
        "Mushuk bilan", "Fil bilan", "Robot bilan", "O'zi bilan",
        "UFO bilan", "Sehrgar bilan", "Qo'shni bilan", "Marslik bilan",
        "Talking Angela bilan", "Ayiq bilan", "Qush bilan", "It bilan",
        "Ilonlar bilan", "Maymun bilan", "Kenguru bilan", "Pingvin bilan",
        "Sher bilan", "Oshpaz bilan", "Raqqosa bilan", "Xonanda bilan"
    ],
    'nima_qilyapti': [
        "Raqs tushyapti", "Parvoz qilyapti", "Suzib yuribdi", "Uxlayapti",
        "Kulyapti", "Yig'layapti", "Qo'shiq aytmoqda", "Yugurmoqda",
        "O'yin o'ynayapti", "Ovqat pishirmoqda", "Kitob o'qimoqda",
        "Rasm chizmoqda", "Sakramoqda", "Velosiped minmoqda",
        "Shaxmat o'ynayapti", "Selfi olmoqda", "TikTok qilmoqda",
        "YouTube ko'rmoqda", "Mashina haydamoqda", "Suzmoqda"
    ],
    'qayerda': [
        "Oyda", "Suv ostida", "Bulutlar ustida", "Cho'l o'rtasida",
        "Maktabda", "Oshxonada", "Hammomda", "Avtobusda", "Marsda",
        "Do'konda", "Stadionjustifyda", "Kinoteatrda", "Shifokorda",
        "Daraxt ustida", "Tog' cho'qqisida", "Kemada", "Samolyotda",
        "Metroda", "Parkda", "Hovuzda", "Zoo parkda", "Sirk sahnasida"
    ]
}

def get_ai_javob(savol_index):
    """AI javobini olish"""
    # Yangi tartib: Kim? Kim bilan? Qachon? Qayerda? Nima qilyapti?
    savol_turlari = ['kim', 'kim_bilan', 'qachon', 'qayerda', 'nima_qilyapti']
    tur = savol_turlari[savol_index]
    return random.choice(AI_JAVOBLAR[tur])

def generate_room_code():
    """4 ta harfli xona kodi yaratish"""
    import string
    return ''.join(random.choices(string.ascii_uppercase, k=4))

@app.route('/qogoz_oyin')
def qogoz_oyin():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    return render_template('qogoz_oyin.html', ism=ism, foydalanuvchi=data[ism], sinf_id=sinf_id)

@app.route('/qogoz_ai_oyin', methods=['POST'])
def qogoz_ai_oyin():
    """AI bilan yakka o'yin"""
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    req_data = request.get_json()
    user_answers = req_data.get('javoblar', {})  # {0: "javob1", 1: "javob2", ...}

    # Barcha 5 ta javobni yig'ish
    javoblar = []
    ai_nomlari = ["Robot Bekzod", "AI Dilshod", "Bot Sardor", "Kompyuter Aziz", "ChatGPT"]

    for i in range(5):
        if str(i) in user_answers and user_answers[str(i)]:
            # Foydalanuvchi javobi
            javoblar.append({
                'ism': ism,
                'javob': user_answers[str(i)]
            })
        else:
            # AI javobi
            javoblar.append({
                'ism': random.choice(ai_nomlari),
                'javob': get_ai_javob(i)
            })

    # O'yin tugadi - 10 ball qo'shish
    data = load_data(sinf_id)
    if ism in data:
        data[ism]['ball'] = data[ism].get('ball', 0) + 10
        save_data(sinf_id, data)

    return jsonify({
        'success': True,
        'javoblar': javoblar,
        'bonus': 10,
        'yangi_ball': data[ism]['ball'] if ism in data else 0
    })

@app.route('/savol_olish')
def savol_olish():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'error': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    bosqich = data[ism].get('bosqich', 1)
    mavsum = data[ism].get('mavsum', 1)

    bosqich_guruh = ((bosqich - 1) % 20) // 3
    vaqt = 30 - (bosqich_guruh * 4)
    if vaqt < 10:
        vaqt = 10

    # Sinf darajasiga mos savollarni olish
    savollar = get_savollar(sinf_id)

    if 'soralgan_savollar' not in session:
        session['soralgan_savollar'] = []

    soralgan = session['soralgan_savollar']
    qolgan_indekslar = [i for i in range(len(savollar)) if i not in soralgan]

    if len(qolgan_indekslar) == 0:
        session['soralgan_savollar'] = []
        qolgan_indekslar = list(range(len(savollar)))

    savol_index = random.choice(qolgan_indekslar)
    session['soralgan_savollar'] = soralgan + [savol_index]
    session.modified = True

    savol = savollar[savol_index].copy()
    savol['vaqt'] = vaqt
    savol['bosqich'] = bosqich
    savol['mavsum'] = mavsum
    savol['index'] = savol_index

    return jsonify(savol)

@app.route('/javob_tekshirish', methods=['POST'])
def javob_tekshirish():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'error': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    javob = int(request.form.get('javob', -1))
    togri = int(request.form.get('togri', -1))

    if javob == togri:
        data[ism]['ball'] = data[ism].get('ball', 0) + 1
        data[ism]['bosqich'] = data[ism].get('bosqich', 1) + 1

        if data[ism]['bosqich'] > 20:
            data[ism]['bosqich'] = 1
            data[ism]['mavsum'] = data[ism].get('mavsum', 1) + 1

        save_data(sinf_id, data)
        return jsonify({
            'togri': True,
            'ball': data[ism]['ball'],
            'bosqich': data[ism]['bosqich'],
            'mavsum': data[ism]['mavsum']
        })
    else:
        return jsonify({'togri': False, 'ball': data[ism]['ball']})

@app.route('/bonus_ishlatish', methods=['POST'])
def bonus_ishlatish():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'error': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    bonus_id = request.form.get('bonus_id')

    if 'bonuslar' in data[ism] and bonus_id in data[ism]['bonuslar']:
        if data[ism]['bonuslar'][bonus_id] > 0:
            data[ism]['bonuslar'][bonus_id] -= 1
            save_data(sinf_id, data)
            return jsonify({'success': True, 'qoldi': data[ism]['bonuslar'][bonus_id]})

    return jsonify({'success': False, 'xato': 'Bonus mavjud emas'})

@app.route('/chat')
def chat():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    chat_xabarlari = load_chat(sinf_id)
    # Test va VIP accountlardan kelgan xabarlarni yashirish (VIP faqat do'stlari ko'radi)
    user_friends = data[ism].get('dostlar', [])
    filtered_xabarlar = []
    for x in chat_xabarlari:
        kimdan = x.get('kimdan', '')
        if kimdan in TEST_ACCOUNTS:
            continue
        if kimdan in VIP_ACCOUNTS or data.get(kimdan, {}).get('vip_account', False):
            if kimdan != ism and ism not in data.get(kimdan, {}).get('dostlar', []):
                continue
        filtered_xabarlar.append(x)

    # Online users - VIP faqat do'stlariga ko'rinadi
    online_users = {}
    for k, v in data.items():
        if not v.get('online', False):
            continue
        if v.get('test_account', False) or k in TEST_ACCOUNTS:
            continue
        if v.get('vip_account', False) or k in VIP_ACCOUNTS:
            if k != ism and ism not in v.get('dostlar', []):
                continue
        online_users[k] = v

    return render_template('chat.html', ism=ism, foydalanuvchi=data[ism], online_users=online_users, xabarlar=filtered_xabarlar)

@app.route('/reyting')
def reyting():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    if ism not in data:
        return redirect(url_for('sinflar'))

    # Barcha o'quvchilarni ball bo'yicha tartiblash (test va VIP accountlarni yashirish)
    players = []
    for name, info in data.items():
        # Test accountlarni yashirish
        if info.get('test_account', False) or name in TEST_ACCOUNTS:
            continue
        # VIP accountlarni faqat do'stlariga ko'rsatish
        if info.get('vip_account', False) or name in VIP_ACCOUNTS:
            if name != ism and ism not in info.get('dostlar', []):
                continue
        players.append({
            'ism': name,
            'ball': info.get('ball', 0),
            'mavsum': info.get('mavsum', 1),
            'bosqich': info.get('bosqich', 1),
            'avatar': info.get('avatar', 'oddiy'),
            'jins': info.get('jins', 'ogil')
        })

    # Ball bo'yicha tartiblash (kattadan kichikka)
    players.sort(key=lambda x: x['ball'], reverse=True)

    # Foydalanuvchining o'rnini topish
    my_rank = 1
    for i, player in enumerate(players):
        if player['ism'] == ism:
            my_rank = i + 1
            break

    # Sinf nomini olish
    sinflar = load_sinflar()
    sinf_nomi = sinf_id
    if sinf_id in sinflar:
        sinf_nomi = sinflar[sinf_id].get('nomi', sinf_id)

    return render_template('reyting.html', ism=ism, foydalanuvchi=data[ism],
                         top_players=players[:10], my_rank=my_rank, sinf_nomi=sinf_nomi)

@app.route('/kunlik_bonus')
def kunlik_bonus():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    if ism not in data:
        return jsonify({'success': False, 'xato': 'Foydalanuvchi topilmadi'})

    bugun = str(date.today())
    oxirgi_bonus = data[ism].get('oxirgi_bonus', '')

    if oxirgi_bonus == bugun:
        return jsonify({'success': False, 'xato': 'Bugun bonus allaqachon olingan!', 'olingan': True})

    # Bonus berish (1-10 ball orasida)
    bonus = random.randint(5, 15)
    data[ism]['ball'] = data[ism].get('ball', 0) + bonus
    data[ism]['oxirgi_bonus'] = bugun

    # Streak (ketma-ket kunlar)
    streak = data[ism].get('bonus_streak', 0)
    if oxirgi_bonus:
        from datetime import timedelta
        kecha = str(date.today() - timedelta(days=1))
        if oxirgi_bonus == kecha:
            streak += 1
        else:
            streak = 1
    else:
        streak = 1

    data[ism]['bonus_streak'] = streak

    # Streak bonusi
    if streak >= 7:
        bonus += 10  # Haftalik bonus
        data[ism]['ball'] += 10

    save_data(sinf_id, data)

    return jsonify({
        'success': True,
        'bonus': bonus,
        'yangi_ball': data[ism]['ball'],
        'streak': streak
    })

# Test account uchun coin berish
@app.route('/coin_berish', methods=['POST'])
def coin_berish():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']

    # Faqat test va VIP accountlar uchun
    if not session.get('test_account', False) and not session.get('vip_account', False):
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req_data = request.get_json()
    qabul_qiluvchi = req_data.get('qabul_qiluvchi', '').strip()
    miqdor = int(req_data.get('miqdor', 0))

    if miqdor <= 0:
        return jsonify({'success': False, 'xato': 'Noto\'g\'ri miqdor'})

    data = load_data(sinf_id)

    if qabul_qiluvchi not in data:
        return jsonify({'success': False, 'xato': 'Foydalanuvchi topilmadi'})

    # Coin qo'shish
    data[qabul_qiluvchi]['ball'] = data[qabul_qiluvchi].get('ball', 0) + miqdor

    # Test account coinini qayta tiklash
    if ism in data:
        data[ism]['ball'] = 999999

    save_data(sinf_id, data)

    return jsonify({
        'success': True,
        'yangi_ball': data[qabul_qiluvchi]['ball'],
        'xabar': f'{qabul_qiluvchi}ga {miqdor} coin berildi!'
    })

@app.route('/bonus_tekshir')
def bonus_tekshir():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'mavjud': False})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    if ism not in data:
        return jsonify({'mavjud': False})

    bugun = str(date.today())
    oxirgi_bonus = data[ism].get('oxirgi_bonus', '')
    streak = data[ism].get('bonus_streak', 0)

    return jsonify({
        'mavjud': oxirgi_bonus != bugun,
        'streak': streak
    })

# Do'stlar tizimi
@app.route('/dostlar')
def dostlar():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    if ism not in data:
        return redirect(url_for('sinflar'))

    # Do'stlar ro'yxati (test accountlarni yashirish, VIP do'stlar ko'rinadi)
    my_friends = data[ism].get('dostlar', [])
    friends_data = []
    for f in my_friends:
        if f in data and f not in TEST_ACCOUNTS and not data[f].get('test_account', False):
            friends_data.append({'ism': f, **data[f]})

    # Barcha foydalanuvchilar (do'st bo'lmaganlar, VIP yashirin)
    all_users = []
    for name, info in data.items():
        if name == ism or name in my_friends:
            continue
        if info.get('test_account', False) or name in TEST_ACCOUNTS:
            continue
        # VIP accountlarni yashirish (boshqalar ro'yxatidan)
        if info.get('vip_account', False) or name in VIP_ACCOUNTS:
            continue
        all_users.append({'ism': name, **info})

    return render_template('dostlar.html', ism=ism, foydalanuvchi=data[ism],
                         dostlar=friends_data, boshqalar=all_users)

@app.route('/dost_qoshish', methods=['POST'])
def dost_qoshish():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req_data = request.get_json()
    dost_ism = req_data.get('dost_ism')

    if dost_ism not in data:
        return jsonify({'success': False, 'xato': 'Foydalanuvchi topilmadi'})

    if 'dostlar' not in data[ism]:
        data[ism]['dostlar'] = []

    if dost_ism in data[ism]['dostlar']:
        return jsonify({'success': False, 'xato': 'Allaqachon do\'stingiz'})

    data[ism]['dostlar'].append(dost_ism)

    # Ikki tomonlama do'stlik
    if 'dostlar' not in data[dost_ism]:
        data[dost_ism]['dostlar'] = []
    if ism not in data[dost_ism]['dostlar']:
        data[dost_ism]['dostlar'].append(ism)

    save_data(sinf_id, data)
    return jsonify({'success': True, 'xabar': f'{dost_ism} do\'stlarga qo\'shildi!'})

@app.route('/dost_ochirish', methods=['POST'])
def dost_ochirish():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req_data = request.get_json()
    dost_ism = req_data.get('dost_ism')

    if 'dostlar' in data[ism] and dost_ism in data[ism]['dostlar']:
        data[ism]['dostlar'].remove(dost_ism)

    if 'dostlar' in data.get(dost_ism, {}) and ism in data[dost_ism]['dostlar']:
        data[dost_ism]['dostlar'].remove(ism)

    save_data(sinf_id, data)
    return jsonify({'success': True})

# Sovg'a yuborish
@app.route('/sovga_yuborish', methods=['POST'])
def sovga_yuborish():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req_data = request.get_json()
    qabul_qiluvchi = req_data.get('qabul_qiluvchi')
    miqdor = int(req_data.get('miqdor', 0))

    if miqdor <= 0:
        return jsonify({'success': False, 'xato': 'Noto\'g\'ri miqdor'})

    if qabul_qiluvchi not in data:
        return jsonify({'success': False, 'xato': 'Foydalanuvchi topilmadi'})

    if data[ism].get('ball', 0) < miqdor:
        return jsonify({'success': False, 'xato': 'Ball yetarli emas!'})

    # Sovg'a yuborish
    data[ism]['ball'] -= miqdor
    data[qabul_qiluvchi]['ball'] = data[qabul_qiluvchi].get('ball', 0) + miqdor

    # Bildirishnoma qo'shish
    if 'bildirishnomalar' not in data[qabul_qiluvchi]:
        data[qabul_qiluvchi]['bildirishnomalar'] = []
    data[qabul_qiluvchi]['bildirishnomalar'].append({
        'tur': 'sovga',
        'kimdan': ism,
        'miqdor': miqdor,
        'vaqt': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'oqilgan': False
    })

    save_data(sinf_id, data)
    return jsonify({
        'success': True,
        'xabar': f'{qabul_qiluvchi}ga {miqdor} ball sovg\'a qilindi!',
        'yangi_ball': data[ism]['ball']
    })

# E'lonlar
ELONLAR_FILE = 'elonlar.json'

def load_elonlar(sinf_id):
    sinf_path = get_sinf_path(sinf_id)
    elon_file = os.path.join(sinf_path, 'elonlar.json')
    if os.path.exists(elon_file):
        with open(elon_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_elonlar(sinf_id, elonlar):
    sinf_path = get_sinf_path(sinf_id)
    os.makedirs(sinf_path, exist_ok=True)
    elon_file = os.path.join(sinf_path, 'elonlar.json')
    with open(elon_file, 'w', encoding='utf-8') as f:
        json.dump(elonlar, f, ensure_ascii=False, indent=2)

@app.route('/elonlar')
def elonlar():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    elonlar_data = load_elonlar(sinf_id)

    return render_template('elonlar.html', ism=ism, foydalanuvchi=data[ism],
                         elonlar=elonlar_data, admin=session.get('admin', False))

@app.route('/elon_qoshish', methods=['POST'])
def elon_qoshish():
    if not session.get('admin', False):
        return jsonify({'success': False, 'xato': 'Faqat admin!'})

    sinf_id = session['sinf_id']
    req_data = request.get_json()

    elon = {
        'id': str(datetime.now().timestamp()),
        'sarlavha': req_data.get('sarlavha', ''),
        'matn': req_data.get('matn', ''),
        'muhim': req_data.get('muhim', False),
        'sana': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'muallif': session['foydalanuvchi']
    }

    elonlar = load_elonlar(sinf_id)
    elonlar.insert(0, elon)
    save_elonlar(sinf_id, elonlar)

    return jsonify({'success': True})

# Yutuqlar (Achievements)
YUTUQLAR = {
    'birinchi_kirish': {'nomi': 'Xush kelibsiz!', 'tavsif': 'Birinchi marta tizimga kirdingiz', 'icon': '🎉', 'ball': 5},
    'ball_100': {'nomi': '100 ball', 'tavsif': '100 ball to\'pladingiz', 'icon': '💯', 'ball': 10},
    'ball_500': {'nomi': '500 ball', 'tavsif': '500 ball to\'pladingiz', 'icon': '🏆', 'ball': 25},
    'ball_1000': {'nomi': '1000 ball', 'tavsif': '1000 ball to\'pladingiz', 'icon': '👑', 'ball': 50},
    'dost_5': {'nomi': 'Do\'stona', 'tavsif': '5 ta do\'st orttirdingiz', 'icon': '👥', 'ball': 15},
    'dost_10': {'nomi': 'Mashhur', 'tavsif': '10 ta do\'st orttirdingiz', 'icon': '🌟', 'ball': 30},
    'mavsum_5': {'nomi': 'Tajribali', 'tavsif': '5-mavsumga yetdingiz', 'icon': '📚', 'ball': 20},
    'mavsum_10': {'nomi': 'Professional', 'tavsif': '10-mavsumga yetdingiz', 'icon': '🎓', 'ball': 50},
    'zar_jackpot': {'nomi': 'Omadli!', 'tavsif': 'Zar o\'yinida ikki 6 tashladingiz', 'icon': '🎲', 'ball': 20},
    'sovga_beruvchi': {'nomi': 'Saxiy', 'tavsif': 'Birinchi sovg\'angizni yubordingiz', 'icon': '🎁', 'ball': 10},
    'kunlik_7': {'nomi': 'Faol', 'tavsif': '7 kun ketma-ket kirdingiz', 'icon': '🔥', 'ball': 25},
}

def check_yutuqlar(sinf_id, ism):
    """Yutuqlarni tekshirish va berish"""
    data = load_data(sinf_id)
    if ism not in data:
        return

    user = data[ism]
    if 'yutuqlar' not in user:
        user['yutuqlar'] = []

    yangi_yutuqlar = []

    # Ball yutuqlari
    ball = user.get('ball', 0)
    if ball >= 100 and 'ball_100' not in user['yutuqlar']:
        user['yutuqlar'].append('ball_100')
        user['ball'] += YUTUQLAR['ball_100']['ball']
        yangi_yutuqlar.append('ball_100')
    if ball >= 500 and 'ball_500' not in user['yutuqlar']:
        user['yutuqlar'].append('ball_500')
        user['ball'] += YUTUQLAR['ball_500']['ball']
        yangi_yutuqlar.append('ball_500')
    if ball >= 1000 and 'ball_1000' not in user['yutuqlar']:
        user['yutuqlar'].append('ball_1000')
        user['ball'] += YUTUQLAR['ball_1000']['ball']
        yangi_yutuqlar.append('ball_1000')

    # Do'st yutuqlari
    dostlar = len(user.get('dostlar', []))
    if dostlar >= 5 and 'dost_5' not in user['yutuqlar']:
        user['yutuqlar'].append('dost_5')
        user['ball'] += YUTUQLAR['dost_5']['ball']
        yangi_yutuqlar.append('dost_5')
    if dostlar >= 10 and 'dost_10' not in user['yutuqlar']:
        user['yutuqlar'].append('dost_10')
        user['ball'] += YUTUQLAR['dost_10']['ball']
        yangi_yutuqlar.append('dost_10')

    # Mavsum yutuqlari
    mavsum = user.get('mavsum', 1)
    if mavsum >= 5 and 'mavsum_5' not in user['yutuqlar']:
        user['yutuqlar'].append('mavsum_5')
        user['ball'] += YUTUQLAR['mavsum_5']['ball']
        yangi_yutuqlar.append('mavsum_5')
    if mavsum >= 10 and 'mavsum_10' not in user['yutuqlar']:
        user['yutuqlar'].append('mavsum_10')
        user['ball'] += YUTUQLAR['mavsum_10']['ball']
        yangi_yutuqlar.append('mavsum_10')

    # Kunlik bonus yutuqi
    streak = user.get('bonus_streak', 0)
    if streak >= 7 and 'kunlik_7' not in user['yutuqlar']:
        user['yutuqlar'].append('kunlik_7')
        user['ball'] += YUTUQLAR['kunlik_7']['ball']
        yangi_yutuqlar.append('kunlik_7')

    if yangi_yutuqlar:
        save_data(sinf_id, data)

    return yangi_yutuqlar

@app.route('/yutuqlar')
def yutuqlar_sahifa():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    check_yutuqlar(sinf_id, ism)
    data = load_data(sinf_id)  # Yangilangan ma'lumotlarni olish

    user_yutuqlar = data[ism].get('yutuqlar', [])

    return render_template('yutuqlar.html', ism=ism, foydalanuvchi=data[ism],
                         barcha_yutuqlar=YUTUQLAR, user_yutuqlar=user_yutuqlar)

# Statistika
@app.route('/statistika')
def statistika():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    user = data[ism]

    # Statistikani hisoblash
    stats = {
        'ball': user.get('ball', 0),
        'mavsum': user.get('mavsum', 1),
        'bosqich': user.get('bosqich', 1),
        'dostlar': len(user.get('dostlar', [])),
        'yutuqlar': len(user.get('yutuqlar', [])),
        'gadjetlar': len(user.get('gadjetlar', [])),
        'bonus_streak': user.get('bonus_streak', 0),
    }

    # Reytingdagi o'rni
    players = [(name, info.get('ball', 0)) for name, info in data.items() if not info.get('test_account', False) and name not in TEST_ACCOUNTS]
    players.sort(key=lambda x: x[1], reverse=True)
    stats['reyting'] = next((i+1 for i, (name, _) in enumerate(players) if name == ism), 0)
    stats['jami_oyinchilar'] = len(players)

    return render_template('statistika.html', ism=ism, foydalanuvchi=data[ism], stats=stats)

# Bildirishnomalar
@app.route('/bildirishnomalar')
def bildirishnomalar():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    # Test accountlardan kelgan bildirishnomalarni yashirish
    notiflar = data[ism].get('bildirishnomalar', [])
    notiflar = [n for n in notiflar if n.get('kimdan', '') not in TEST_ACCOUNTS]

    return render_template('bildirishnomalar.html', ism=ism, foydalanuvchi=data[ism],
                         bildirishnomalar=notiflar)

@app.route('/bildirishnoma_oqildi', methods=['POST'])
def bildirishnoma_oqildi():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    # Barcha bildirishnomalarni o'qilgan deb belgilash
    if 'bildirishnomalar' in data[ism]:
        for notif in data[ism]['bildirishnomalar']:
            notif['oqilgan'] = True
        save_data(sinf_id, data)

    return jsonify({'success': True})

@app.route('/bildirishnoma_soni')
def bildirishnoma_soni():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'soni': 0})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    notiflar = data[ism].get('bildirishnomalar', [])
    oqilmagan = sum(1 for n in notiflar if not n.get('oqilgan', False))

    return jsonify({'soni': oqilmagan})

# Admin panel - Yangi tizim
def check_admin():
    """Admin ekanligini tekshirish"""
    if not session.get('admin'):
        return None
    ism = session.get('foydalanuvchi')
    if ism not in ADMINS:
        return None
    return ADMINS[ism]

def has_permission(permission):
    """Admin ruxsatini tekshirish"""
    admin = check_admin()
    if not admin:
        return False
    return permission in admin.get('ruxsatlar', [])

@app.route('/admin_panel')
def admin_panel():
    admin = check_admin()
    if not admin:
        return redirect(url_for('sinflar'))

    sinf_id = session['sinf_id']
    admin_ism = session['foydalanuvchi']
    admin_tur = admin['tur']

    # Barcha sinflardan foydalanuvchilarni olish (test accountlarni yashirish)
    sinflar = load_sinflar()
    all_users = {}
    for sid in sinflar:
        data = load_data(sid)
        for username, info in data.items():
            # Test accountlarni yashirish
            if username in TEST_ACCOUNTS or info.get('test_account', False):
                continue
            all_users[f"{sid}:{username}"] = {**info, 'sinf_id': sid, 'ism': username}

    # Bloklangan foydalanuvchilar
    blocked = load_blocked()

    # Statistika
    total_users = len(all_users)
    online_users = sum(1 for u in all_users.values() if u.get('online', False))
    total_balls = sum(u.get('ball', 0) for u in all_users.values())
    blocked_count = len(blocked.get('blocked', [])) + len(blocked.get('temp_blocked', {}))

    return render_template('admin_panel.html',
                         admin_ism=admin_ism,
                         admin_tur=admin_tur,
                         users=all_users,
                         sinflar=sinflar,
                         blocked=blocked,
                         total_users=total_users,
                         online_users=online_users,
                         total_balls=total_balls,
                         blocked_count=blocked_count,
                         ruxsatlar=admin['ruxsatlar'])

@app.route('/admin/ball', methods=['POST'])
def admin_ball():
    if not has_permission('coin_qoshish') and not has_permission('coin_ayirish'):
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req_data = request.get_json()
    sinf_id = req_data.get('sinf_id')
    username = req_data.get('username')
    ball = req_data.get('ball', 0)
    action = req_data.get('action', 'set')  # set, add, remove

    data = load_data(sinf_id)
    if username not in data:
        return jsonify({'success': False, 'xato': 'Foydalanuvchi topilmadi'})

    if action == 'add':
        if not has_permission('coin_qoshish'):
            return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})
        data[username]['ball'] = data[username].get('ball', 0) + ball
    elif action == 'remove':
        if not has_permission('coin_ayirish'):
            return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})
        data[username]['ball'] = max(0, data[username].get('ball', 0) - ball)
    else:
        data[username]['ball'] = ball

    save_data(sinf_id, data)
    return jsonify({'success': True, 'yangi_ball': data[username]['ball']})

@app.route('/admin/qarz', methods=['POST'])
def admin_qarz():
    if not has_permission('qarzga_tiqish'):
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req_data = request.get_json()
    sinf_id = req_data.get('sinf_id')
    username = req_data.get('username')
    qarz_miqdori = req_data.get('qarz', 0)

    data = load_data(sinf_id)
    if username not in data:
        return jsonify({'success': False, 'xato': 'Foydalanuvchi topilmadi'})

    # Manfiy qiymatga o'tkazish (qarzga tiqish)
    data[username]['ball'] = -abs(qarz_miqdori)
    save_data(sinf_id, data)

    return jsonify({'success': True, 'yangi_ball': data[username]['ball']})

@app.route('/admin/bosqich', methods=['POST'])
def admin_bosqich():
    req_data = request.get_json()
    sinf_id = req_data.get('sinf_id')
    username = req_data.get('username')
    action = req_data.get('action')  # kotarish, tushirish

    if action == 'kotarish' and not has_permission('bosqich_kotarish'):
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})
    if action == 'tushirish' and not has_permission('bosqich_tushirish'):
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    data = load_data(sinf_id)
    if username not in data:
        return jsonify({'success': False, 'xato': 'Foydalanuvchi topilmadi'})

    if action == 'kotarish':
        data[username]['bosqich'] = data[username].get('bosqich', 1) + 1
        if data[username]['bosqich'] > 20:
            data[username]['bosqich'] = 1
            data[username]['mavsum'] = data[username].get('mavsum', 1) + 1
    elif action == 'tushirish':
        data[username]['bosqich'] = max(1, data[username].get('bosqich', 1) - 1)

    save_data(sinf_id, data)
    return jsonify({'success': True, 'bosqich': data[username]['bosqich'], 'mavsum': data[username].get('mavsum', 1)})

@app.route('/admin/password', methods=['POST'])
def admin_password():
    if not has_permission('parol_tiklash'):
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req_data = request.get_json()
    sinf_id = req_data.get('sinf_id')
    username = req_data.get('username')
    password = req_data.get('password', '')

    data = load_data(sinf_id)
    if username not in data:
        return jsonify({'success': False, 'xato': 'Foydalanuvchi topilmadi'})

    if len(password) < 3:
        return jsonify({'success': False, 'xato': 'Parol kamida 3 ta belgi bo\'lishi kerak'})

    data[username]['parol'] = password
    save_data(sinf_id, data)
    return jsonify({'success': True})

@app.route('/admin/delete', methods=['POST'])
def admin_delete():
    if not has_permission('ochirish'):
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req_data = request.get_json()
    sinf_id = req_data.get('sinf_id')
    username = req_data.get('username')

    data = load_data(sinf_id)
    if username not in data:
        return jsonify({'success': False, 'xato': 'Foydalanuvchi topilmadi'})

    del data[username]
    save_data(sinf_id, data)
    update_sinf_count(sinf_id)
    return jsonify({'success': True})

@app.route('/admin/block', methods=['POST'])
def admin_block():
    if not has_permission('bloklash'):
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req_data = request.get_json()
    sinf_id = req_data.get('sinf_id')
    username = req_data.get('username')

    blocked = load_blocked()
    key = f"{sinf_id}:{username}"

    if key not in blocked['blocked']:
        blocked['blocked'].append(key)
        save_blocked(blocked)

    return jsonify({'success': True})

@app.route('/admin/unblock', methods=['POST'])
def admin_unblock():
    if not has_permission('blokdan_chiqarish'):
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req_data = request.get_json()
    sinf_id = req_data.get('sinf_id')
    username = req_data.get('username')

    blocked = load_blocked()
    key = f"{sinf_id}:{username}"

    if key in blocked['blocked']:
        blocked['blocked'].remove(key)
    if key in blocked.get('temp_blocked', {}):
        del blocked['temp_blocked'][key]
    save_blocked(blocked)

    return jsonify({'success': True})

@app.route('/admin/temp_block', methods=['POST'])
def admin_temp_block():
    if not has_permission('vaqtinchalik_bloklash'):
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req_data = request.get_json()
    sinf_id = req_data.get('sinf_id')
    username = req_data.get('username')
    hours = req_data.get('hours', 24)

    from datetime import timedelta
    blocked = load_blocked()
    key = f"{sinf_id}:{username}"

    end_time = datetime.now() + timedelta(hours=hours)
    blocked['temp_blocked'][key] = end_time.isoformat()
    save_blocked(blocked)

    return jsonify({'success': True, 'end_time': end_time.isoformat()})

@app.route('/admin/block_admin', methods=['POST'])
def admin_block_admin():
    if not has_permission('admin_bloklash'):
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req_data = request.get_json()
    admin_name = req_data.get('admin_name')
    password = req_data.get('password')

    # Yopiq admin parolini tekshirish
    if password != ADMINS['HAKER']['parol']:
        return jsonify({'success': False, 'xato': 'Parol noto\'g\'ri!'})

    if admin_name == 'HAKER':
        return jsonify({'success': False, 'xato': 'O\'zingizni bloklash mumkin emas!'})

    blocked = load_blocked()
    if admin_name not in blocked['admin_blocked']:
        blocked['admin_blocked'].append(admin_name)
        save_blocked(blocked)

    return jsonify({'success': True})

@app.route('/admin/unblock_admin', methods=['POST'])
def admin_unblock_admin():
    if not has_permission('admin_bloklash'):
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req_data = request.get_json()
    admin_name = req_data.get('admin_name')

    blocked = load_blocked()
    if admin_name in blocked['admin_blocked']:
        blocked['admin_blocked'].remove(admin_name)
        save_blocked(blocked)

    return jsonify({'success': True})

@app.route('/admin/read_messages', methods=['POST'])
def admin_read_messages():
    if not has_permission('xabar_oqish'):
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req_data = request.get_json()
    sinf_id = req_data.get('sinf_id')

    xabarlar = load_chat(sinf_id)
    return jsonify({'success': True, 'xabarlar': xabarlar})

@app.route('/admin/sinf_tanlash', methods=['POST'])
def admin_sinf_tanlash():
    admin = check_admin()
    if not admin:
        return jsonify({'success': False, 'xato': 'Admin emassiz'})

    req_data = request.get_json()
    sinf_id = req_data.get('sinf_id')

    session['sinf_id'] = sinf_id
    return jsonify({'success': True})

@app.route('/admin/export')
def admin_export():
    admin = check_admin()
    if not admin:
        return redirect(url_for('sinflar'))

    sinf_id = request.args.get('sinf_id', session.get('sinf_id'))
    data = load_data(sinf_id)

    response = app.response_class(
        response=json.dumps(data, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json'
    )
    response.headers['Content-Disposition'] = f'attachment; filename={sinf_id}_export.json'
    return response

# Eski /admin route ni yo'naltirish
@app.route('/admin')
def admin():
    return redirect(url_for('admin_panel'))

@app.route('/sozlamalar')
def sozlamalar():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    if ism not in data:
        return redirect(url_for('sinflar'))

    return render_template('sozlamalar.html', ism=ism, foydalanuvchi=data[ism])

@app.route('/sozlamalar/profil', methods=['POST'])
def sozlamalar_profil():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req_data = request.get_json()
    yangi_ism = req_data.get('ism', '').strip()
    yangi_malumot = req_data.get('malumot', '')

    if ism not in data:
        return jsonify({'success': False, 'xato': 'Foydalanuvchi topilmadi'})

    ism_ozgardi = False

    # Ism o'zgartirish
    if yangi_ism and yangi_ism != ism:
        if yangi_ism in data:
            return jsonify({'success': False, 'xato': 'Bu ism band!'})

        # Eski ismni yangi ismga o'zgartirish
        data[yangi_ism] = data.pop(ism)
        session['foydalanuvchi'] = yangi_ism
        ism_ozgardi = True

    # Ma'lumot o'zgartirish
    current_ism = yangi_ism if ism_ozgardi else ism
    data[current_ism]['malumot'] = yangi_malumot

    save_data(sinf_id, data)
    return jsonify({'success': True, 'message': 'Profil yangilandi!', 'ism_ozgardi': ism_ozgardi})

@app.route('/sozlamalar/parol', methods=['POST'])
def sozlamalar_parol():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req_data = request.get_json()
    eski_parol = req_data.get('eski_parol', '')
    yangi_parol = req_data.get('yangi_parol', '')

    if ism not in data:
        return jsonify({'success': False, 'xato': 'Foydalanuvchi topilmadi'})

    if data[ism]['parol'] != eski_parol:
        return jsonify({'success': False, 'xato': 'Joriy parol noto\'g\'ri!'})

    if len(yangi_parol) < 3:
        return jsonify({'success': False, 'xato': 'Parol kamida 3 ta belgi bo\'lishi kerak!'})

    data[ism]['parol'] = yangi_parol
    save_data(sinf_id, data)

    return jsonify({'success': True, 'message': 'Parol o\'zgartirildi!'})

@app.route('/chiqish')
def chiqish():
    if 'foydalanuvchi' in session and 'sinf_id' in session:
        ism = session['foydalanuvchi']
        sinf_id = session['sinf_id']
        data = load_data(sinf_id)
        if ism in data:
            data[ism]['online'] = False
            save_data(sinf_id, data)

    session.clear()
    return redirect(url_for('sinflar'))

# SocketIO events
@socketio.on('connect')
def handle_connect():
    print('Foydalanuvchi ulandi')

@socketio.on('disconnect')
def handle_disconnect():
    print('Foydalanuvchi uzildi')
    # Qog'oz o'yini xonasidan chiqarish
    for room_code, room in list(QOGOZ_ROOMS.items()):
        for i, player in enumerate(room['players']):
            if player.get('sid') == request.sid:
                room['players'].remove(player)

                if room['started']:
                    # O'yin boshlangan bo'lsa, o'yinni bekor qilish
                    emit('qogoz_oyinchi_chiqdi', {
                        'oyin_bekor': True,
                        'chiqgan': player['ism']
                    }, room=f'qogoz_{room_code}')
                    del QOGOZ_ROOMS[room_code]
                else:
                    # O'yin boshlanmagan bo'lsa, o'yinchilar ro'yxatini yangilash
                    if len(room['players']) == 0:
                        del QOGOZ_ROOMS[room_code]
                    else:
                        players_list = [{'ism': p['ism']} for p in room['players']]
                        emit('qogoz_oyinchi_chiqdi', {
                            'oyin_bekor': False,
                            'players': players_list
                        }, room=f'qogoz_{room_code}')
                return

@socketio.on('join')
def handle_join(data):
    username = data.get('username')
    sinf_id = session.get('sinf_id', 'bizning_sinf')
    room = f'chat_{sinf_id}'
    join_room(room)
    emit('user_joined', {'username': username}, room=room)

@socketio.on('leave')
def handle_leave(data):
    username = data.get('username')
    sinf_id = session.get('sinf_id', 'bizning_sinf')
    room = f'chat_{sinf_id}'
    leave_room(room)
    emit('user_left', {'username': username}, room=room)

@socketio.on('send_message')
def handle_message(data):
    username = data.get('username')
    message = data.get('message')
    sinf_id = session.get('sinf_id', 'bizning_sinf')

    xabar = {
        'username': username,
        'message': message,
        'time': data.get('time', '')
    }

    chat_xabarlari = load_chat(sinf_id)
    chat_xabarlari.append(xabar)
    save_chat(sinf_id, chat_xabarlari)

    room = f'chat_{sinf_id}'
    emit('new_message', xabar, room=room)

# Qog'oz o'yini Socket eventlari
@socketio.on('qogoz_xona_yaratish')
def handle_qogoz_create(data):
    ism = data.get('ism')
    sinf_id = data.get('sinf_id')

    # Yangi xona kodi yaratish
    room_code = generate_room_code()
    while room_code in QOGOZ_ROOMS:
        room_code = generate_room_code()

    # Xonani yaratish
    QOGOZ_ROOMS[room_code] = {
        'players': [{'ism': ism, 'sinf_id': sinf_id, 'sid': request.sid}],
        'answers': [],
        'current_turn': 0,
        'question_index': 0,
        'started': False
    }

    join_room(f'qogoz_{room_code}')
    emit('qogoz_xona_yaratildi', {
        'room_code': room_code,
        'players': [{'ism': ism}]
    })

@socketio.on('qogoz_xonaga_qoshilish')
def handle_qogoz_join(data):
    ism = data.get('ism')
    sinf_id = data.get('sinf_id')
    room_code = data.get('room_code', '').upper()

    if room_code not in QOGOZ_ROOMS:
        emit('qogoz_xato', {'xabar': 'Xona topilmadi!'})
        return

    room = QOGOZ_ROOMS[room_code]

    if room['started']:
        emit('qogoz_xato', {'xabar': "O'yin allaqachon boshlangan!"})
        return

    if len(room['players']) >= 10:
        emit('qogoz_xato', {'xabar': "Xona to'lgan! (max 10 o'yinchi)"})
        return

    # Agar bu o'yinchi allaqachon bo'lsa
    for p in room['players']:
        if p['ism'] == ism and p['sinf_id'] == sinf_id:
            emit('qogoz_xato', {'xabar': "Siz allaqachon xonadasiz!"})
            return

    # O'yinchini qo'shish
    room['players'].append({'ism': ism, 'sinf_id': sinf_id, 'sid': request.sid})
    join_room(f'qogoz_{room_code}')

    players_list = [{'ism': p['ism']} for p in room['players']]

    emit('qogoz_qoshildi', {
        'room_code': room_code,
        'players': players_list
    })

    # Boshqa o'yinchilarga xabar berish
    emit('qogoz_oyinchilar_yangilandi', {
        'players': players_list
    }, room=f'qogoz_{room_code}', include_self=False)

@socketio.on('qogoz_oyin_boshlash')
def handle_qogoz_start(data):
    room_code = data.get('room_code')

    if room_code not in QOGOZ_ROOMS:
        emit('qogoz_xato', {'xabar': 'Xona topilmadi!'})
        return

    room = QOGOZ_ROOMS[room_code]

    if len(room['players']) < 5:
        emit('qogoz_xato', {'xabar': "Kamida 5 ta o'yinchi kerak!"})
        return

    room['started'] = True
    room['current_turn'] = 0
    room['question_index'] = 0
    room['answers'] = []

    # Har bir o'yinchiga uning navbat raqamini yuborish
    for i, player in enumerate(room['players']):
        socketio.emit('qogoz_oyin_boshlandi', {
            'my_turn': i,
            'current_turn': 0,
            'question_index': 0,
            'current_player': room['players'][0]['ism']
        }, room=player['sid'])

@socketio.on('qogoz_javob')
def handle_qogoz_answer(data):
    room_code = data.get('room_code')
    javob = data.get('javob', '...')

    if room_code not in QOGOZ_ROOMS:
        return

    room = QOGOZ_ROOMS[room_code]
    current_turn = room['current_turn']

    # Javobni saqlash
    room['answers'].append({
        'ism': room['players'][current_turn]['ism'],
        'javob': javob
    })

    # Keyingi savol/navbat
    room['question_index'] += 1

    if room['question_index'] >= 5:
        # O'yin tugadi - barcha o'yinchilarga 10 ball qo'shish
        for player in room['players']:
            player_sinf = player.get('sinf_id', 'bizning_sinf')
            player_ism = player['ism']
            data = load_data(player_sinf)
            if player_ism in data:
                data[player_ism]['ball'] = data[player_ism].get('ball', 0) + 10
                save_data(player_sinf, data)

        # Hikoyani ko'rsatish
        emit('qogoz_hikoya', {
            'javoblar': room['answers'],
            'bonus': 10
        }, room=f'qogoz_{room_code}')

        # Xonani tozalash
        del QOGOZ_ROOMS[room_code]
    else:
        # Keyingi o'yinchiga o'tish
        room['current_turn'] = (current_turn + 1) % len(room['players'])

        # Agar 5 ta savoldan ko'p o'yinchi bo'lsa, faqat birinchi 5 tasi javob beradi
        if room['current_turn'] >= 5:
            room['current_turn'] = room['question_index']

        emit('qogoz_keyingi_savol', {
            'current_turn': room['current_turn'],
            'question_index': room['question_index'],
            'current_player': room['players'][room['current_turn']]['ism']
        }, room=f'qogoz_{room_code}')

# ==================== YANGI FUNKSIYALAR ====================

# 1. Matematika musobaqasi
@app.route('/matematika_oyin')
def matematika_oyin():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    return render_template('matematika_oyin.html', ism=ism, foydalanuvchi=data[ism])

@app.route('/matematika_javob', methods=['POST'])
def matematika_javob():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req = request.get_json()
    togri_soni = req.get('togri', 0)

    # Ball hisoblash - har bir to'g'ri javob uchun 2 ball
    ball = togri_soni * 2
    data[ism]['ball'] += ball

    # Rekordni saqlash
    if 'matematika_rekord' not in data[ism]:
        data[ism]['matematika_rekord'] = 0
    if togri_soni > data[ism]['matematika_rekord']:
        data[ism]['matematika_rekord'] = togri_soni

    save_data(sinf_id, data)
    return jsonify({'success': True, 'ball': ball, 'rekord': data[ism]['matematika_rekord']})

# 2. So'z o'yini
SOZ_ROYXATI = ['matematika', 'informatika', 'kompyuter', 'dasturlash', 'telefon', 'kitob',
               'maktab', 'sinf', 'oquvchi', 'ustoz', 'fan', 'bilim', 'hayot', 'dunyo',
               'ozbekiston', 'toshkent', 'oila', 'dost', 'bolalar', 'sport', 'futbol',
               'musiqa', 'rasm', 'tabiat', 'hayvon', 'qush', 'daryo', 'toglar', 'quyosh']

@app.route('/soz_oyin')
def soz_oyin():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    # Tasodifiy so'z tanlash
    soz = random.choice(SOZ_ROYXATI)
    harflar = list(soz)
    random.shuffle(harflar)

    return render_template('soz_oyin.html', ism=ism, foydalanuvchi=data[ism],
                         harflar=harflar, soz=soz)

@app.route('/soz_tekshir', methods=['POST'])
def soz_tekshir():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req = request.get_json()
    javob = req.get('javob', '').lower().strip()
    togri_javob = req.get('togri', '').lower().strip()

    if javob == togri_javob:
        data[ism]['ball'] += 15
        save_data(sinf_id, data)
        return jsonify({'success': True, 'togri': True, 'ball': 15})

    return jsonify({'success': True, 'togri': False})

# 3. Viktorina
VIKTORINA_SAVOLLAR = {
    'tarix': [
        {'savol': 'Amir Temur qachon tug\'ilgan?', 'javoblar': ['1336', '1405', '1370', '1300'], 'togri': 0},
        {'savol': 'O\'zbekiston qachon mustaqillikka erishdi?', 'javoblar': ['1990', '1991', '1992', '1989'], 'togri': 1},
        {'savol': 'Birinchi prezidentimiz kim?', 'javoblar': ['Sh.Mirziyoyev', 'I.Karimov', 'A.Aripov', 'N.Muhammadiyev'], 'togri': 1},
    ],
    'geografiya': [
        {'savol': 'O\'zbekiston poytaxti qayer?', 'javoblar': ['Samarqand', 'Toshkent', 'Buxoro', 'Xiva'], 'togri': 1},
        {'savol': 'Eng baland tog\' cho\'qqisi?', 'javoblar': ['Elbrus', 'Everest', 'Kilimanjaro', 'Monblan'], 'togri': 1},
        {'savol': 'Eng katta okean?', 'javoblar': ['Atlantika', 'Tinch', 'Hind', 'Shimoliy Muz'], 'togri': 1},
    ],
    'fan': [
        {'savol': 'Suvning formulasi?', 'javoblar': ['CO2', 'H2O', 'NaCl', 'O2'], 'togri': 1},
        {'savol': 'Yorug\'lik tezligi?', 'javoblar': ['300 km/s', '300000 km/s', '30000 km/s', '3000 km/s'], 'togri': 1},
        {'savol': 'Eng kichik zarracha?', 'javoblar': ['Atom', 'Molekula', 'Kvark', 'Elektron'], 'togri': 2},
    ],
    'sport': [
        {'savol': 'Futbolda nechta o\'yinchi?', 'javoblar': ['10', '11', '12', '9'], 'togri': 1},
        {'savol': 'Olimpiya o\'yinlari necha yilda bir marta?', 'javoblar': ['2', '3', '4', '5'], 'togri': 2},
        {'savol': 'Basketbol halqasi balandligi?', 'javoblar': ['3.05m', '2.5m', '3.5m', '2.8m'], 'togri': 0},
    ]
}

@app.route('/viktorina')
def viktorina():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    return render_template('viktorina.html', ism=ism, foydalanuvchi=data[ism],
                         mavzular=list(VIKTORINA_SAVOLLAR.keys()))

@app.route('/viktorina_savollar/<mavzu>')
def viktorina_savollar(mavzu):
    if mavzu not in VIKTORINA_SAVOLLAR:
        return jsonify({'success': False})

    savollar = VIKTORINA_SAVOLLAR[mavzu].copy()
    random.shuffle(savollar)
    return jsonify({'success': True, 'savollar': savollar[:5]})

@app.route('/viktorina_yakunla', methods=['POST'])
def viktorina_yakunla():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req = request.get_json()
    togri_soni = req.get('togri', 0)

    ball = togri_soni * 5
    data[ism]['ball'] += ball
    save_data(sinf_id, data)

    return jsonify({'success': True, 'ball': ball})

# 4. Xotira o'yini
@app.route('/xotira_oyin')
def xotira_oyin():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    return render_template('xotira_oyin.html', ism=ism, foydalanuvchi=data[ism])

@app.route('/xotira_yakunla', methods=['POST'])
def xotira_yakunla():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req = request.get_json()
    urinishlar = req.get('urinishlar', 100)
    vaqt = req.get('vaqt', 0)

    # Ball - kam urinish va kam vaqt yaxshi
    ball = max(5, 30 - urinishlar // 2)
    data[ism]['ball'] += ball

    # Rekord
    if 'xotira_rekord' not in data[ism]:
        data[ism]['xotira_rekord'] = 999
    if urinishlar < data[ism]['xotira_rekord']:
        data[ism]['xotira_rekord'] = urinishlar

    save_data(sinf_id, data)
    return jsonify({'success': True, 'ball': ball, 'rekord': data[ism]['xotira_rekord']})

# 5. Haftalik/Oylik reyting
@app.route('/reyting_vaqt/<tur>')
def reyting_vaqt(tur):
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    # Vaqt bo'yicha filtrlash
    from datetime import timedelta
    bugun = date.today()

    if tur == 'hafta':
        boshlanish = bugun - timedelta(days=bugun.weekday())
    elif tur == 'oy':
        boshlanish = bugun.replace(day=1)
    else:
        boshlanish = date(2020, 1, 1)  # Barcha vaqt

    # Reyting hisoblash (ball_tarix dan)
    reyting = []
    for foydalanuvchi, malumot in data.items():
        if foydalanuvchi in TEST_ACCOUNTS or malumot.get('test_account', False):
            continue

        # Ball tarixidan hisoblash
        ball_tarix = malumot.get('ball_tarix', {})
        davr_ball = 0
        for sana_str, ball in ball_tarix.items():
            try:
                sana = date.fromisoformat(sana_str)
                if sana >= boshlanish:
                    davr_ball += ball
            except:
                pass

        reyting.append({
            'ism': foydalanuvchi,
            'ball': davr_ball,
            'jami_ball': malumot.get('ball', 0)
        })

    reyting.sort(key=lambda x: x['ball'], reverse=True)

    return render_template('reyting_vaqt.html', ism=ism, foydalanuvchi=data[ism],
                         reyting=reyting[:20], tur=tur)

# 6. Jamoaviy topshiriqlar
JAMOA_TOPSHIRIQLAR = [
    {'id': 1, 'nomi': 'Birgalikda 1000 ball', 'maqsad': 1000, 'mukofot': 50, 'tavsif': 'Sinf bo\'lib 1000 ball yig\'ing'},
    {'id': 2, 'nomi': 'Test ustasi', 'maqsad': 100, 'mukofot': 30, 'tavsif': '100 ta test yechilsin'},
    {'id': 3, 'nomi': 'Faol hafta', 'maqsad': 20, 'mukofot': 25, 'tavsif': 'Haftasiga 20 ta o\'yin o\'ynalsin'},
]

@app.route('/jamoa_topshiriq')
def jamoa_topshiriq():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    # Sinf progress
    sinf_path = get_sinf_path(sinf_id)
    jamoa_file = os.path.join(sinf_path, 'jamoa_progress.json')

    if os.path.exists(jamoa_file):
        with open(jamoa_file, 'r', encoding='utf-8') as f:
            progress = json.load(f)
    else:
        progress = {str(t['id']): 0 for t in JAMOA_TOPSHIRIQLAR}

    topshiriqlar = []
    for t in JAMOA_TOPSHIRIQLAR:
        t_copy = t.copy()
        t_copy['progress'] = progress.get(str(t['id']), 0)
        t_copy['bajarilgan'] = t_copy['progress'] >= t['maqsad']
        topshiriqlar.append(t_copy)

    return render_template('jamoa_topshiriq.html', ism=ism, foydalanuvchi=data[ism],
                         topshiriqlar=topshiriqlar)

# 7. Kundalik bonus
@app.route('/kundalik_bonus', methods=['POST'])
def kundalik_bonus():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    bugun = str(date.today())

    # Tekshirish
    if data[ism].get('oxirgi_bonus') == bugun:
        return jsonify({'success': False, 'xato': 'Bugun bonus allaqachon olindi!'})

    # Streak hisoblash
    oxirgi = data[ism].get('oxirgi_bonus', '')
    if oxirgi:
        try:
            oxirgi_sana = date.fromisoformat(oxirgi)
            farq = (date.today() - oxirgi_sana).days
            if farq == 1:
                data[ism]['bonus_streak'] = data[ism].get('bonus_streak', 0) + 1
            elif farq > 1:
                data[ism]['bonus_streak'] = 1
        except:
            data[ism]['bonus_streak'] = 1
    else:
        data[ism]['bonus_streak'] = 1

    # Ball - streak ga qarab
    streak = data[ism]['bonus_streak']
    ball = min(5 + streak * 2, 25)  # Max 25 ball

    data[ism]['ball'] += ball
    data[ism]['oxirgi_bonus'] = bugun

    # Ball tarixga qo'shish
    if 'ball_tarix' not in data[ism]:
        data[ism]['ball_tarix'] = {}
    data[ism]['ball_tarix'][bugun] = data[ism]['ball_tarix'].get(bugun, 0) + ball

    save_data(sinf_id, data)

    return jsonify({'success': True, 'ball': ball, 'streak': streak})

# 8. Profil rasmi tanlash
AVATARLAR = [
    'ogil.svg', 'qiz.svg', 'robot.svg', 'alien.svg', 'ninja.svg',
    'sherlock.svg', 'pirat.svg', 'kosmonavt.svg', 'super_qahramon.svg', 'olim.svg'
]

@app.route('/avatar_tanlash')
def avatar_tanlash():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    return render_template('avatar_tanlash.html', ism=ism, foydalanuvchi=data[ism],
                         avatarlar=AVATARLAR)

@app.route('/avatar_saqlash', methods=['POST'])
def avatar_saqlash():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req = request.get_json()
    avatar = req.get('avatar', 'ogil.svg')

    if avatar in AVATARLAR:
        data[ism]['avatar'] = avatar
        save_data(sinf_id, data)
        return jsonify({'success': True})

    return jsonify({'success': False})

# 9. Mavzular (Themes)
MAVZULAR = {
    'default': {'nomi': 'Standart', 'rang': '#667eea'},
    'qizil': {'nomi': 'Qizil', 'rang': '#e74c3c'},
    'yashil': {'nomi': 'Yashil', 'rang': '#27ae60'},
    'sariq': {'nomi': 'Sariq', 'rang': '#f39c12'},
    'pushti': {'nomi': 'Pushti', 'rang': '#e91e63'},
    'qoramtir': {'nomi': 'Qoramtir', 'rang': '#2c3e50'},
    'osmon': {'nomi': 'Osmon', 'rang': '#3498db'},
    'binafsha': {'nomi': 'Binafsha', 'rang': '#9b59b6'},
}

@app.route('/mavzu_tanlash')
def mavzu_tanlash():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    return render_template('mavzu_tanlash.html', ism=ism, foydalanuvchi=data[ism],
                         mavzular=MAVZULAR)

@app.route('/mavzu_saqlash', methods=['POST'])
def mavzu_saqlash():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req = request.get_json()
    mavzu = req.get('mavzu', 'default')

    if mavzu in MAVZULAR:
        data[ism]['mavzu'] = mavzu
        save_data(sinf_id, data)
        return jsonify({'success': True, 'rang': MAVZULAR[mavzu]['rang']})

    return jsonify({'success': False})

# 10. Maqsadlar
@app.route('/maqsadlar')
def maqsadlar():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    user_maqsadlar = data[ism].get('maqsadlar', [])

    return render_template('maqsadlar.html', ism=ism, foydalanuvchi=data[ism],
                         maqsadlar=user_maqsadlar)

@app.route('/maqsad_qoshish', methods=['POST'])
def maqsad_qoshish():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req = request.get_json()
    nomi = req.get('nomi', '').strip()
    maqsad_ball = req.get('ball', 100)

    if not nomi or maqsad_ball < 10:
        return jsonify({'success': False, 'xato': 'Noto\'g\'ri ma\'lumot'})

    if 'maqsadlar' not in data[ism]:
        data[ism]['maqsadlar'] = []

    if len(data[ism]['maqsadlar']) >= 5:
        return jsonify({'success': False, 'xato': 'Maksimum 5 ta maqsad'})

    data[ism]['maqsadlar'].append({
        'id': len(data[ism]['maqsadlar']) + 1,
        'nomi': nomi,
        'maqsad': maqsad_ball,
        'boshlangich': data[ism]['ball'],
        'yaratilgan': str(date.today())
    })

    save_data(sinf_id, data)
    return jsonify({'success': True})

@app.route('/maqsad_ochirish', methods=['POST'])
def maqsad_ochirish():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    req = request.get_json()
    maqsad_id = req.get('id', 0)

    if 'maqsadlar' in data[ism]:
        data[ism]['maqsadlar'] = [m for m in data[ism]['maqsadlar'] if m['id'] != maqsad_id]
        save_data(sinf_id, data)

    return jsonify({'success': True})

# ==================== MAFIYA O'YINI ====================
MAFIYA_ROOMS = {}

MAFIYA_ROLLAR = {
    'mafiya': {'nomi': 'Mafiya', 'icon': '🔪', 'tavsif': 'Kechasi odamlarni o\'ldiradi'},
    'doktor': {'nomi': 'Doktor', 'icon': '💉', 'tavsif': 'Kechasi biror kishini saqlaydi'},
    'sheriff': {'nomi': 'Sheriff', 'icon': '🔍', 'tavsif': 'Kechasi biror kishini tekshiradi'},
    'fuqaro': {'nomi': 'Fuqaro', 'icon': '👤', 'tavsif': 'Mafiyani topishga harakat qiladi'},
}

# AI Bot nomlari
AI_NAMES = ['🤖 Akbar', '🤖 Laziz', '🤖 Dilshod', '🤖 Nodira', '🤖 Gulnora',
            '🤖 Sardor', '🤖 Madina', '🤖 Jasur', '🤖 Zarina', '🤖 Bobur']

@app.route('/mafiya_oyin')
def mafiya_oyin():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    return render_template('mafiya_oyin.html', ism=ism, foydalanuvchi=data[ism])

def mafiya_rollarni_taqsimla(oyinchilar):
    """O'yinchilar soniga qarab rollarni taqsimlash"""
    import random
    soni = len(oyinchilar)
    rollar = []

    # Mafiya soni
    mafiya_soni = max(1, soni // 4)
    rollar.extend(['mafiya'] * mafiya_soni)

    # Doktor va Sheriff (5+ o'yinchi bo'lsa)
    if soni >= 5:
        rollar.append('doktor')
    if soni >= 6:
        rollar.append('sheriff')

    # Qolganlar fuqaro
    fuqaro_soni = soni - len(rollar)
    rollar.extend(['fuqaro'] * fuqaro_soni)

    random.shuffle(rollar)

    natija = {}
    for i, oyinchi in enumerate(oyinchilar):
        natija[oyinchi] = rollar[i]

    return natija

@socketio.on('mafiya_xona_yaratish')
def mafiya_xona_yaratish(data):
    ism = session.get('foydalanuvchi')
    if not ism:
        return

    room_code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))

    MAFIYA_ROOMS[room_code] = {
        'host': ism,
        'players': [{'ism': ism, 'sid': request.sid, 'tirik': True, 'rol': None, 'ovoz': None}],
        'status': 'waiting',  # waiting, night, day, voting, finished
        'rollar': {},
        'kecha': 0,
        'mafiya_target': None,
        'doktor_target': None,
        'sheriff_target': None,
        'votes': {},
        'history': [],
        'winner': None
    }

    join_room(f'mafiya_{room_code}')
    emit('mafiya_xona_yaratildi', {'room_code': room_code, 'host': ism})

@socketio.on('mafiya_qoshilish')
def mafiya_qoshilish(data):
    ism = session.get('foydalanuvchi')
    room_code = data.get('room_code', '').upper()

    if not ism or room_code not in MAFIYA_ROOMS:
        emit('mafiya_xato', {'xabar': 'Xona topilmadi!'})
        return

    room = MAFIYA_ROOMS[room_code]

    if room['status'] != 'waiting':
        emit('mafiya_xato', {'xabar': 'O\'yin allaqachon boshlangan!'})
        return

    if len(room['players']) >= 10:
        emit('mafiya_xato', {'xabar': 'Xona to\'la! (max 10)'})
        return

    if any(p['ism'] == ism for p in room['players']):
        emit('mafiya_xato', {'xabar': 'Siz allaqachon xonadasiz!'})
        return

    room['players'].append({'ism': ism, 'sid': request.sid, 'tirik': True, 'rol': None, 'ovoz': None})
    join_room(f'mafiya_{room_code}')

    emit('mafiya_qoshildi', {
        'room_code': room_code,
        'players': [p['ism'] for p in room['players']],
        'host': room['host']
    }, room=f'mafiya_{room_code}')

@socketio.on('mafiya_bot_qoshish')
def mafiya_bot_qoshish(data):
    ism = session.get('foydalanuvchi')
    room_code = data.get('room_code')

    if room_code not in MAFIYA_ROOMS:
        return

    room = MAFIYA_ROOMS[room_code]

    if room['host'] != ism:
        emit('mafiya_xato', {'xabar': 'Faqat host bot qo\'sha oladi!'})
        return

    if len(room['players']) >= 10:
        emit('mafiya_xato', {'xabar': 'Xona to\'la!'})
        return

    # Mavjud bo'lmagan bot nomini tanlash
    mavjud_ismlar = [p['ism'] for p in room['players']]
    bot_nomi = None
    for name in AI_NAMES:
        if name not in mavjud_ismlar:
            bot_nomi = name
            break

    if not bot_nomi:
        emit('mafiya_xato', {'xabar': 'Botlar tugadi!'})
        return

    room['players'].append({
        'ism': bot_nomi,
        'sid': None,
        'tirik': True,
        'rol': None,
        'ovoz': None,
        'is_bot': True
    })

    emit('mafiya_qoshildi', {
        'room_code': room_code,
        'players': [p['ism'] for p in room['players']],
        'host': room['host']
    }, room=f'mafiya_{room_code}')

def mafiya_ai_kecha_harakat(room_code):
    """AI botlarning kecha harakatlari"""
    room = MAFIYA_ROOMS[room_code]

    tirik_botlar = [p for p in room['players'] if p['tirik'] and p.get('is_bot')]
    tirik_oyinchilar = [p['ism'] for p in room['players'] if p['tirik']]

    for bot in tirik_botlar:
        rol = bot['rol']

        if rol == 'mafiya' and not room['mafiya_target']:
            # Mafiya bot - tasodifiy fuqaroni tanlash
            targets = [p for p in tirik_oyinchilar if room['rollar'].get(p) != 'mafiya']
            if targets:
                room['mafiya_target'] = random.choice(targets)

        elif rol == 'doktor' and not room['doktor_target']:
            # Doktor bot - tasodifiy saqlash
            room['doktor_target'] = random.choice(tirik_oyinchilar)

        elif rol == 'sheriff' and not room['sheriff_target']:
            # Sheriff bot - tasodifiy tekshirish
            targets = [p for p in tirik_oyinchilar if p != bot['ism']]
            if targets:
                room['sheriff_target'] = random.choice(targets)

def mafiya_ai_ovoz_berish(room_code):
    """AI botlarning kunduzi ovoz berishi"""
    room = MAFIYA_ROOMS[room_code]

    tirik_botlar = [p for p in room['players'] if p['tirik'] and p.get('is_bot')]
    tirik_oyinchilar = [p['ism'] for p in room['players'] if p['tirik']]

    for bot in tirik_botlar:
        if bot['ism'] not in room['votes']:
            # Tasodifiy ovoz berish (o'zidan boshqa)
            targets = [p for p in tirik_oyinchilar if p != bot['ism']]
            if targets:
                room['votes'][bot['ism']] = random.choice(targets)

@socketio.on('mafiya_boshlash')
def mafiya_boshlash(data):
    ism = session.get('foydalanuvchi')
    room_code = data.get('room_code')

    if room_code not in MAFIYA_ROOMS:
        return

    room = MAFIYA_ROOMS[room_code]

    if room['host'] != ism:
        emit('mafiya_xato', {'xabar': 'Faqat host boshlashi mumkin!'})
        return

    if len(room['players']) < 4:
        emit('mafiya_xato', {'xabar': 'Kamida 4 o\'yinchi kerak!'})
        return

    # Rollarni taqsimlash
    oyinchilar = [p['ism'] for p in room['players']]
    room['rollar'] = mafiya_rollarni_taqsimla(oyinchilar)

    for player in room['players']:
        player['rol'] = room['rollar'][player['ism']]

    room['status'] = 'night'
    room['kecha'] = 1

    # Har bir o'yinchiga o'z rolini yuborish
    for player in room['players']:
        rol = player['rol']
        socketio.emit('mafiya_rol_berildi', {
            'rol': rol,
            'rol_info': MAFIYA_ROLLAR[rol],
            'kecha': room['kecha']
        }, room=player['sid'])

    emit('mafiya_boshlandi', {
        'kecha': room['kecha'],
        'tirik_oyinchilar': [p['ism'] for p in room['players'] if p['tirik']]
    }, room=f'mafiya_{room_code}')

@socketio.on('mafiya_kecha_harakat')
def mafiya_kecha_harakat(data):
    ism = session.get('foydalanuvchi')
    room_code = data.get('room_code')
    target = data.get('target')

    if room_code not in MAFIYA_ROOMS:
        return

    room = MAFIYA_ROOMS[room_code]
    player = next((p for p in room['players'] if p['ism'] == ism), None)

    if not player or not player['tirik']:
        return

    rol = player['rol']

    if rol == 'mafiya':
        room['mafiya_target'] = target
        emit('mafiya_harakat_qabul', {'xabar': f'{target} ni tanladingiz'})
    elif rol == 'doktor':
        room['doktor_target'] = target
        emit('mafiya_harakat_qabul', {'xabar': f'{target} ni saqlaysiz'})
    elif rol == 'sheriff':
        room['sheriff_target'] = target
        # Sheriffga natijani ko'rsatish
        target_rol = room['rollar'].get(target)
        if target_rol == 'mafiya':
            emit('mafiya_sheriff_natija', {'target': target, 'natija': 'mafiya', 'xabar': f'{target} MAFIYA!'})
        else:
            emit('mafiya_sheriff_natija', {'target': target, 'natija': 'tinch', 'xabar': f'{target} tinch fuqaro'})

    # AI botlar harakat qilsin
    mafiya_ai_kecha_harakat(room_code)

    # Barcha harakatlar tugadimi tekshirish
    mafiya_kechani_yakunla(room_code)

def mafiya_kechani_yakunla(room_code):
    room = MAFIYA_ROOMS[room_code]

    # AI botlar harakat qilsin (agar qilmagan bo'lsa)
    mafiya_ai_kecha_harakat(room_code)

    # Mafiya tanladi mi?
    mafiyalar = [p for p in room['players'] if p['tirik'] and p['rol'] == 'mafiya']
    doktor = next((p for p in room['players'] if p['tirik'] and p['rol'] == 'doktor'), None)
    sheriff = next((p for p in room['players'] if p['tirik'] and p['rol'] == 'sheriff'), None)

    # Barcha harakat qildimi?
    if not room['mafiya_target']:
        return
    if doktor and not room['doktor_target']:
        return
    if sheriff and not room['sheriff_target']:
        return

    # Kechani yakunlash
    olgan = None
    if room['mafiya_target'] != room['doktor_target']:
        olgan = room['mafiya_target']
        # O'yinchini o'ldirish
        for p in room['players']:
            if p['ism'] == olgan:
                p['tirik'] = False
                break

    room['history'].append({
        'kecha': room['kecha'],
        'olgan': olgan,
        'saqlangan': room['doktor_target'] if room['mafiya_target'] == room['doktor_target'] else None
    })

    # Kunduzga o'tish
    room['status'] = 'day'
    room['mafiya_target'] = None
    room['doktor_target'] = None
    room['sheriff_target'] = None
    room['votes'] = {}

    tirik = [p['ism'] for p in room['players'] if p['tirik']]

    # G'olibni tekshirish
    winner = mafiya_golibni_tekshir(room)
    if winner:
        room['status'] = 'finished'
        room['winner'] = winner
        socketio.emit('mafiya_tugadi', {
            'winner': winner,
            'rollar': room['rollar']
        }, room=f'mafiya_{room_code}')
        return

    socketio.emit('mafiya_kunduz', {
        'kecha': room['kecha'],
        'olgan': olgan,
        'tirik_oyinchilar': tirik
    }, room=f'mafiya_{room_code}')

def mafiya_golibni_tekshir(room):
    tirik = [p for p in room['players'] if p['tirik']]
    mafiyalar = [p for p in tirik if p['rol'] == 'mafiya']
    tinchlar = [p for p in tirik if p['rol'] != 'mafiya']

    if len(mafiyalar) == 0:
        return 'fuqarolar'
    if len(mafiyalar) >= len(tinchlar):
        return 'mafiya'
    return None

@socketio.on('mafiya_ovoz_berish')
def mafiya_ovoz_berish(data):
    ism = session.get('foydalanuvchi')
    room_code = data.get('room_code')
    target = data.get('target')

    if room_code not in MAFIYA_ROOMS:
        return

    room = MAFIYA_ROOMS[room_code]
    player = next((p for p in room['players'] if p['ism'] == ism), None)

    if not player or not player['tirik']:
        return

    room['votes'][ism] = target

    # AI botlar ham ovoz bersin
    mafiya_ai_ovoz_berish(room_code)

    # Hamma ovoz berdimi?
    tirik = [p for p in room['players'] if p['tirik']]
    if len(room['votes']) >= len(tirik):
        mafiya_ovozni_yakunla(room_code)
    else:
        socketio.emit('mafiya_ovoz_yangilandi', {
            'ovoz_soni': len(room['votes']),
            'jami': len(tirik)
        }, room=f'mafiya_{room_code}')

def mafiya_ovozni_yakunla(room_code):
    room = MAFIYA_ROOMS[room_code]

    # Ovozlarni hisoblash
    ovoz_soni = {}
    for voter, target in room['votes'].items():
        ovoz_soni[target] = ovoz_soni.get(target, 0) + 1

    # Eng ko'p ovoz olgan
    max_ovoz = max(ovoz_soni.values()) if ovoz_soni else 0
    chiqarilganlar = [k for k, v in ovoz_soni.items() if v == max_ovoz]

    chiqarilgan = None
    if len(chiqarilganlar) == 1 and max_ovoz > 1:
        chiqarilgan = chiqarilganlar[0]
        for p in room['players']:
            if p['ism'] == chiqarilgan:
                p['tirik'] = False
                break

    # G'olibni tekshirish
    winner = mafiya_golibni_tekshir(room)
    if winner:
        room['status'] = 'finished'
        room['winner'] = winner
        socketio.emit('mafiya_tugadi', {
            'winner': winner,
            'rollar': room['rollar'],
            'chiqarilgan': chiqarilgan,
            'ovozlar': room['votes']
        }, room=f'mafiya_{room_code}')
        return

    # Keyingi kechaga o'tish
    room['status'] = 'night'
    room['kecha'] += 1
    room['votes'] = {}

    tirik = [p['ism'] for p in room['players'] if p['tirik']]

    socketio.emit('mafiya_kecha', {
        'kecha': room['kecha'],
        'chiqarilgan': chiqarilgan,
        'ovozlar': ovoz_soni,
        'tirik_oyinchilar': tirik
    }, room=f'mafiya_{room_code}')

@socketio.on('mafiya_xonadan_chiqish')
def mafiya_xonadan_chiqish(data):
    ism = session.get('foydalanuvchi')
    room_code = data.get('room_code')

    if room_code not in MAFIYA_ROOMS:
        return

    room = MAFIYA_ROOMS[room_code]
    leave_room(f'mafiya_{room_code}')

    room['players'] = [p for p in room['players'] if p['ism'] != ism]

    if len(room['players']) == 0:
        del MAFIYA_ROOMS[room_code]
    else:
        if room['host'] == ism and room['players']:
            room['host'] = room['players'][0]['ism']

        socketio.emit('mafiya_oyinchi_chiqdi', {
            'ism': ism,
            'players': [p['ism'] for p in room['players']],
            'host': room['host']
        }, room=f'mafiya_{room_code}')

# ================= YANGI FUNKSIYALAR =================

# 1. SUDOKU O'YINI
@app.route('/sudoku')
def sudoku():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    return render_template('sudoku.html', ism=ism, foydalanuvchi=data[ism])

@app.route('/sudoku_yutuq', methods=['POST'])
def sudoku_yutuq():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    req = request.get_json()
    qiyinlik = req.get('qiyinlik', 'oson')
    ball = {'oson': 20, 'orta': 40, 'qiyin': 70}.get(qiyinlik, 20)
    data[ism]['ball'] = data[ism].get('ball', 0) + ball
    save_data(sinf_id, data)
    return jsonify({'success': True, 'ball': ball})

# 2. 2048 O'YINI
@app.route('/game2048')
def game2048():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    return render_template('game2048.html', ism=ism, foydalanuvchi=data[ism])

@app.route('/game2048_yutuq', methods=['POST'])
def game2048_yutuq():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    req = request.get_json()
    score = req.get('score', 0)
    ball = min(score // 100, 50)  # Har 100 ochko uchun 1 ball, max 50
    data[ism]['ball'] = data[ism].get('ball', 0) + ball
    save_data(sinf_id, data)
    return jsonify({'success': True, 'ball': ball})

# 3. HANGMAN (OSILGAN ODAM)
HANGMAN_SOZLAR = [
    'kompyuter', 'dasturlash', 'matematika', 'kitob', 'maktab', 'o\'qituvchi',
    'talaba', 'universitet', 'bilim', 'fan', 'tarix', 'geografiya', 'fizika',
    'kimyo', 'biologiya', 'adabiyot', 'sport', 'futbol', 'shaxmat', 'musiqa'
]

@app.route('/hangman')
def hangman():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    return render_template('hangman.html', ism=ism, foydalanuvchi=data[ism])

@app.route('/hangman_soz')
def hangman_soz():
    import random
    soz = random.choice(HANGMAN_SOZLAR)
    return jsonify({'soz': soz})

@app.route('/hangman_yutuq', methods=['POST'])
def hangman_yutuq():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    ball = 15
    data[ism]['ball'] = data[ism].get('ball', 0) + ball
    save_data(sinf_id, data)
    return jsonify({'success': True, 'ball': ball})

# 4. TIC-TAC-TOE ONLINE
TICTACTOE_ROOMS = {}

@app.route('/tictactoe')
def tictactoe():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    return render_template('tictactoe.html', ism=ism, foydalanuvchi=data[ism])

@socketio.on('ttt_xona_yaratish')
def ttt_xona_yaratish():
    ism = session.get('foydalanuvchi')
    room_code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))
    TICTACTOE_ROOMS[room_code] = {
        'players': [ism],
        'board': ['' for _ in range(9)],
        'turn': 'X',
        'symbols': {ism: 'X'},
        'status': 'waiting'
    }
    join_room(f'ttt_{room_code}')
    emit('ttt_xona_yaratildi', {'room_code': room_code, 'symbol': 'X'})

@socketio.on('ttt_qoshilish')
def ttt_qoshilish(data):
    ism = session.get('foydalanuvchi')
    room_code = data.get('room_code', '').upper()
    if room_code not in TICTACTOE_ROOMS:
        emit('ttt_xato', {'xabar': 'Xona topilmadi'})
        return
    room = TICTACTOE_ROOMS[room_code]
    if len(room['players']) >= 2:
        emit('ttt_xato', {'xabar': 'Xona to\'lgan'})
        return
    room['players'].append(ism)
    room['symbols'][ism] = 'O'
    room['status'] = 'playing'
    join_room(f'ttt_{room_code}')
    emit('ttt_qoshildi', {'room_code': room_code, 'symbol': 'O'})
    socketio.emit('ttt_boshlandi', {
        'players': room['players'],
        'turn': room['turn']
    }, room=f'ttt_{room_code}')

@socketio.on('ttt_yurish')
def ttt_yurish(data):
    ism = session.get('foydalanuvchi')
    room_code = data.get('room_code')
    index = data.get('index')
    if room_code not in TICTACTOE_ROOMS:
        return
    room = TICTACTOE_ROOMS[room_code]
    symbol = room['symbols'].get(ism)
    if room['turn'] != symbol or room['board'][index] != '':
        return
    room['board'][index] = symbol
    room['turn'] = 'O' if symbol == 'X' else 'X'

    # G'olibni tekshirish
    win_patterns = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    winner = None
    for p in win_patterns:
        if room['board'][p[0]] == room['board'][p[1]] == room['board'][p[2]] != '':
            winner = room['board'][p[0]]
            break

    draw = all(c != '' for c in room['board']) and not winner

    socketio.emit('ttt_yangilandi', {
        'board': room['board'],
        'turn': room['turn'],
        'winner': winner,
        'draw': draw
    }, room=f'ttt_{room_code}')

# 5. QUIZ BATTLE
QUIZ_BATTLES = {}
QUIZ_SAVOLLAR = [
    {'savol': 'O\'zbekiston poytaxti qaysi?', 'javoblar': ['Toshkent', 'Samarqand', 'Buxoro', 'Xiva'], 'togri': 0},
    {'savol': '2 + 2 * 2 = ?', 'javoblar': ['6', '8', '4', '10'], 'togri': 0},
    {'savol': 'Eng katta sayyora qaysi?', 'javoblar': ['Yupiter', 'Saturn', 'Yer', 'Mars'], 'togri': 0},
    {'savol': 'Suv qanday formulaga ega?', 'javoblar': ['H2O', 'CO2', 'O2', 'NaCl'], 'togri': 0},
    {'savol': 'Alisher Navoiy qaysi asrda yashagan?', 'javoblar': ['15-asr', '14-asr', '16-asr', '17-asr'], 'togri': 0},
]

@app.route('/quiz_battle')
def quiz_battle():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    if ism not in data:
        session.clear()
        return redirect(url_for('sinflar'))
    return render_template('quiz_battle.html', ism=ism, foydalanuvchi=data[ism])

@socketio.on('quiz_xona_yaratish')
def quiz_xona_yaratish():
    ism = session.get('foydalanuvchi')
    room_code = ''.join(random.choices('0123456789', k=6))
    QUIZ_BATTLES[room_code] = {
        'players': {ism: 0},
        'host': ism,
        'savol_index': 0,
        'savollar': random.sample(QUIZ_SAVOLLAR, min(5, len(QUIZ_SAVOLLAR))),
        'javoblar': {},
        'status': 'waiting'
    }
    join_room(f'quiz_{room_code}')
    emit('quiz_xona_yaratildi', {'room_code': room_code})

@socketio.on('quiz_qoshilish')
def quiz_qoshilish(data):
    ism = session.get('foydalanuvchi')
    room_code = data.get('room_code')
    if room_code not in QUIZ_BATTLES:
        emit('quiz_xato', {'xabar': 'Xona topilmadi'})
        return
    room = QUIZ_BATTLES[room_code]
    room['players'][ism] = 0
    join_room(f'quiz_{room_code}')
    socketio.emit('quiz_oyinchi_qoshildi', {
        'players': list(room['players'].keys())
    }, room=f'quiz_{room_code}')

@socketio.on('quiz_boshlash')
def quiz_boshlash(data):
    room_code = data.get('room_code')
    if room_code not in QUIZ_BATTLES:
        return
    room = QUIZ_BATTLES[room_code]
    room['status'] = 'playing'
    savol = room['savollar'][0]
    socketio.emit('quiz_savol', {
        'savol': savol['savol'],
        'javoblar': savol['javoblar'],
        'index': 0
    }, room=f'quiz_{room_code}')

@socketio.on('quiz_javob')
def quiz_javob(data):
    ism = session.get('foydalanuvchi')
    room_code = data.get('room_code')
    javob = data.get('javob')
    if room_code not in QUIZ_BATTLES:
        return
    room = QUIZ_BATTLES[room_code]
    savol = room['savollar'][room['savol_index']]
    if javob == savol['togri']:
        room['players'][ism] = room['players'].get(ism, 0) + 10
    room['javoblar'][ism] = javob

    if len(room['javoblar']) >= len(room['players']):
        room['savol_index'] += 1
        room['javoblar'] = {}
        if room['savol_index'] >= len(room['savollar']):
            socketio.emit('quiz_tugadi', {
                'natijalar': room['players']
            }, room=f'quiz_{room_code}')
        else:
            savol = room['savollar'][room['savol_index']]
            socketio.emit('quiz_savol', {
                'savol': savol['savol'],
                'javoblar': savol['javoblar'],
                'index': room['savol_index']
            }, room=f'quiz_{room_code}')

# 6. SINF DEVORI
@app.route('/devor')
def devor():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    # Devor postlarini yuklash
    devor_file = os.path.join('maktablar', sinf_id, 'devor.json')
    postlar = []
    if os.path.exists(devor_file):
        with open(devor_file, 'r', encoding='utf-8') as f:
            postlar = json.load(f)
    # Test accountlardan kelgan postlarni yashirish
    postlar = [p for p in postlar if p.get('muallif', '') not in TEST_ACCOUNTS]

    return render_template('devor.html', ism=ism, foydalanuvchi=data[ism], postlar=postlar)

@app.route('/devor_post', methods=['POST'])
def devor_post():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    req = request.get_json()
    matn = req.get('matn', '').strip()
    if not matn:
        return jsonify({'success': False, 'xato': 'Matn bo\'sh'})

    devor_file = os.path.join('maktablar', sinf_id, 'devor.json')
    postlar = []
    if os.path.exists(devor_file):
        with open(devor_file, 'r', encoding='utf-8') as f:
            postlar = json.load(f)

    post = {
        'id': len(postlar) + 1,
        'muallif': ism,
        'matn': matn,
        'vaqt': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'yoqtirishlar': [],
        'izohlar': []
    }
    postlar.insert(0, post)

    with open(devor_file, 'w', encoding='utf-8') as f:
        json.dump(postlar, f, ensure_ascii=False, indent=2)

    return jsonify({'success': True})

@app.route('/devor_yoqtirish', methods=['POST'])
def devor_yoqtirish():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    req = request.get_json()
    post_id = req.get('post_id')

    devor_file = os.path.join('maktablar', sinf_id, 'devor.json')
    if not os.path.exists(devor_file):
        return jsonify({'success': False})

    with open(devor_file, 'r', encoding='utf-8') as f:
        postlar = json.load(f)

    for post in postlar:
        if post['id'] == post_id:
            if ism in post['yoqtirishlar']:
                post['yoqtirishlar'].remove(ism)
            else:
                post['yoqtirishlar'].append(ism)
            break

    with open(devor_file, 'w', encoding='utf-8') as f:
        json.dump(postlar, f, ensure_ascii=False, indent=2)

    return jsonify({'success': True})

# 7. TUG'ILGAN KUNLAR
@app.route('/tugilgan_kunlar')
def tugilgan_kunlar():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    # Tug'ilgan kunlarni yig'ish
    kunlar = []
    for name, info in data.items():
        if name not in TEST_ACCOUNTS and not info.get('test_account', False):
            tk = info.get('tugilgan_kun', '')
            if tk:
                kunlar.append({'ism': name, 'sana': tk})

    return render_template('tugilgan_kunlar.html', ism=ism, foydalanuvchi=data[ism], kunlar=kunlar)

@app.route('/tugilgan_kun_saqlash', methods=['POST'])
def tugilgan_kun_saqlash():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    req = request.get_json()
    sana = req.get('sana', '')
    data[ism]['tugilgan_kun'] = sana
    save_data(sinf_id, data)
    return jsonify({'success': True})

# 8. SO'ROVNOMALAR
@app.route('/sorovnomalar')
def sorovnomalar():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    sorov_file = os.path.join('maktablar', sinf_id, 'sorovnomalar.json')
    sorovlar = []
    if os.path.exists(sorov_file):
        with open(sorov_file, 'r', encoding='utf-8') as f:
            sorovlar = json.load(f)

    return render_template('sorovnomalar.html', ism=ism, foydalanuvchi=data[ism], sorovlar=sorovlar)

@app.route('/sorovnoma_yaratish', methods=['POST'])
def sorovnoma_yaratish():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    req = request.get_json()
    savol = req.get('savol', '')
    variantlar = req.get('variantlar', [])

    if not savol or len(variantlar) < 2:
        return jsonify({'success': False, 'xato': 'Savol va kamida 2 ta variant kerak'})

    sorov_file = os.path.join('maktablar', sinf_id, 'sorovnomalar.json')
    sorovlar = []
    if os.path.exists(sorov_file):
        with open(sorov_file, 'r', encoding='utf-8') as f:
            sorovlar = json.load(f)

    sorov = {
        'id': len(sorovlar) + 1,
        'muallif': ism,
        'savol': savol,
        'variantlar': {v: [] for v in variantlar},
        'vaqt': datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    sorovlar.insert(0, sorov)

    with open(sorov_file, 'w', encoding='utf-8') as f:
        json.dump(sorovlar, f, ensure_ascii=False, indent=2)

    return jsonify({'success': True})

@app.route('/sorovnoma_ovoz', methods=['POST'])
def sorovnoma_ovoz():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    req = request.get_json()
    sorov_id = req.get('sorov_id')
    variant = req.get('variant')

    sorov_file = os.path.join('maktablar', sinf_id, 'sorovnomalar.json')
    if not os.path.exists(sorov_file):
        return jsonify({'success': False})

    with open(sorov_file, 'r', encoding='utf-8') as f:
        sorovlar = json.load(f)

    for sorov in sorovlar:
        if sorov['id'] == sorov_id:
            # Oldingi ovozni o'chirish
            for v, ovozlar in sorov['variantlar'].items():
                if ism in ovozlar:
                    ovozlar.remove(ism)
            # Yangi ovoz
            if variant in sorov['variantlar']:
                sorov['variantlar'][variant].append(ism)
            break

    with open(sorov_file, 'w', encoding='utf-8') as f:
        json.dump(sorovlar, f, ensure_ascii=False, indent=2)

    return jsonify({'success': True})

# 9. SHAXSIY XABARLAR
@app.route('/xabarlar')
def xabarlar():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    # Suhbatlar ro'yxati
    xabar_file = os.path.join('maktablar', sinf_id, 'shaxsiy_xabarlar.json')
    xabarlar = {}
    if os.path.exists(xabar_file):
        with open(xabar_file, 'r', encoding='utf-8') as f:
            xabarlar = json.load(f)

    # Foydalanuvchining suhbatlari
    suhbatlar = []
    for key, msgs in xabarlar.items():
        if ism in key.split('_'):
            other = [n for n in key.split('_') if n != ism][0]
            if other not in TEST_ACCOUNTS:
                suhbatlar.append({
                    'ism': other,
                    'oxirgi': msgs[-1] if msgs else None,
                    'key': key
                })

    # Boshqa foydalanuvchilar
    boshqalar = [n for n in data.keys() if n != ism and n not in TEST_ACCOUNTS and not data[n].get('test_account', False)]

    return render_template('xabarlar.html', ism=ism, foydalanuvchi=data[ism],
                          suhbatlar=suhbatlar, boshqalar=boshqalar)

@app.route('/xabar_yuborish', methods=['POST'])
def xabar_yuborish():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    req = request.get_json()
    qabul = req.get('qabul_qiluvchi')
    matn = req.get('matn', '').strip()

    if not matn or not qabul:
        return jsonify({'success': False})

    xabar_file = os.path.join('maktablar', sinf_id, 'shaxsiy_xabarlar.json')
    xabarlar = {}
    if os.path.exists(xabar_file):
        with open(xabar_file, 'r', encoding='utf-8') as f:
            xabarlar = json.load(f)

    # Suhbat kaliti
    key = '_'.join(sorted([ism, qabul]))
    if key not in xabarlar:
        xabarlar[key] = []

    xabarlar[key].append({
        'kimdan': ism,
        'matn': matn,
        'vaqt': datetime.now().strftime('%Y-%m-%d %H:%M')
    })

    with open(xabar_file, 'w', encoding='utf-8') as f:
        json.dump(xabarlar, f, ensure_ascii=False, indent=2)

    return jsonify({'success': True})

@app.route('/xabar_olish/<qabul>')
def xabar_olish(qabul):
    if 'foydalanuvchi' not in session:
        return jsonify([])
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']

    xabar_file = os.path.join('maktablar', sinf_id, 'shaxsiy_xabarlar.json')
    if not os.path.exists(xabar_file):
        return jsonify([])

    with open(xabar_file, 'r', encoding='utf-8') as f:
        xabarlar = json.load(f)

    key = '_'.join(sorted([ism, qabul]))
    return jsonify(xabarlar.get(key, []))

# 10. FLASHCARDS
@app.route('/flashcards')
def flashcards():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    kartalar = data[ism].get('flashcards', [])
    return render_template('flashcards.html', ism=ism, foydalanuvchi=data[ism], kartalar=kartalar)

@app.route('/flashcard_qoshish', methods=['POST'])
def flashcard_qoshish():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    req = request.get_json()

    savol = req.get('savol', '').strip()
    javob = req.get('javob', '').strip()

    if not savol or not javob:
        return jsonify({'success': False})

    if 'flashcards' not in data[ism]:
        data[ism]['flashcards'] = []

    data[ism]['flashcards'].append({
        'id': len(data[ism]['flashcards']) + 1,
        'savol': savol,
        'javob': javob
    })
    save_data(sinf_id, data)
    return jsonify({'success': True})

@app.route('/flashcard_ochirish', methods=['POST'])
def flashcard_ochirish():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    req = request.get_json()
    card_id = req.get('id')

    if 'flashcards' in data[ism]:
        data[ism]['flashcards'] = [c for c in data[ism]['flashcards'] if c['id'] != card_id]
        save_data(sinf_id, data)

    return jsonify({'success': True})

# 11. POMODORO TIMER
@app.route('/pomodoro')
def pomodoro():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    stats = data[ism].get('pomodoro_stats', {'jami_sessiya': 0, 'jami_daqiqa': 0})
    return render_template('pomodoro.html', ism=ism, foydalanuvchi=data[ism], stats=stats)

@app.route('/pomodoro_saqlash', methods=['POST'])
def pomodoro_saqlash():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    req = request.get_json()
    daqiqa = req.get('daqiqa', 25)

    if 'pomodoro_stats' not in data[ism]:
        data[ism]['pomodoro_stats'] = {'jami_sessiya': 0, 'jami_daqiqa': 0}

    data[ism]['pomodoro_stats']['jami_sessiya'] += 1
    data[ism]['pomodoro_stats']['jami_daqiqa'] += daqiqa

    # Har 25 daqiqa uchun 5 ball
    ball = (daqiqa // 25) * 5
    data[ism]['ball'] = data[ism].get('ball', 0) + ball

    save_data(sinf_id, data)
    return jsonify({'success': True, 'ball': ball})

# 12. KITOB RO'YXATI
@app.route('/kitoblar')
def kitoblar():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    kitoblar = data[ism].get('kitoblar', [])
    return render_template('kitoblar.html', ism=ism, foydalanuvchi=data[ism], kitoblar=kitoblar)

@app.route('/kitob_qoshish', methods=['POST'])
def kitob_qoshish():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    req = request.get_json()

    nomi = req.get('nomi', '').strip()
    muallif = req.get('muallif', '').strip()

    if not nomi:
        return jsonify({'success': False})

    if 'kitoblar' not in data[ism]:
        data[ism]['kitoblar'] = []

    data[ism]['kitoblar'].append({
        'id': len(data[ism]['kitoblar']) + 1,
        'nomi': nomi,
        'muallif': muallif,
        'holat': 'oqilmoqda',
        'qoshilgan': datetime.now().strftime('%Y-%m-%d')
    })

    # Kitob qo'shgani uchun 5 ball
    data[ism]['ball'] = data[ism].get('ball', 0) + 5
    save_data(sinf_id, data)
    return jsonify({'success': True})

@app.route('/kitob_holat', methods=['POST'])
def kitob_holat():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    req = request.get_json()

    kitob_id = req.get('id')
    holat = req.get('holat')

    if 'kitoblar' in data[ism]:
        for kitob in data[ism]['kitoblar']:
            if kitob['id'] == kitob_id:
                old_holat = kitob['holat']
                kitob['holat'] = holat
                # Kitobni tugatgani uchun 20 ball
                if holat == 'oqilgan' and old_holat != 'oqilgan':
                    data[ism]['ball'] = data[ism].get('ball', 0) + 20
                break
        save_data(sinf_id, data)

    return jsonify({'success': True})

# 13. KUNLIK VAZIFALAR
@app.route('/vazifalar')
def vazifalar():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    vazifalar = data[ism].get('vazifalar', [])
    return render_template('vazifalar.html', ism=ism, foydalanuvchi=data[ism], vazifalar=vazifalar)

@app.route('/vazifa_qoshish', methods=['POST'])
def vazifa_qoshish():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    req = request.get_json()

    matn = req.get('matn', '').strip()
    if not matn:
        return jsonify({'success': False})

    if 'vazifalar' not in data[ism]:
        data[ism]['vazifalar'] = []

    data[ism]['vazifalar'].append({
        'id': len(data[ism]['vazifalar']) + 1,
        'matn': matn,
        'bajarildi': False,
        'sana': datetime.now().strftime('%Y-%m-%d')
    })
    save_data(sinf_id, data)
    return jsonify({'success': True})

@app.route('/vazifa_bajarish', methods=['POST'])
def vazifa_bajarish():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    req = request.get_json()

    vazifa_id = req.get('id')

    if 'vazifalar' in data[ism]:
        for vazifa in data[ism]['vazifalar']:
            if vazifa['id'] == vazifa_id and not vazifa['bajarildi']:
                vazifa['bajarildi'] = True
                # Vazifa bajargani uchun 3 ball
                data[ism]['ball'] = data[ism].get('ball', 0) + 3
                break
        save_data(sinf_id, data)

    return jsonify({'success': True})

@app.route('/vazifa_ochirish', methods=['POST'])
def vazifa_ochirish():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    req = request.get_json()

    vazifa_id = req.get('id')
    if 'vazifalar' in data[ism]:
        data[ism]['vazifalar'] = [v for v in data[ism]['vazifalar'] if v['id'] != vazifa_id]
        save_data(sinf_id, data)

    return jsonify({'success': True})

# 14. SERTIFIKATLAR
SERTIFIKATLAR = [
    {'id': 'ball_1000', 'nomi': '1000 ball yig\'uvchi', 'shart': 'ball >= 1000', 'rasm': 'bronze'},
    {'id': 'ball_5000', 'nomi': '5000 ball yig\'uvchi', 'shart': 'ball >= 5000', 'rasm': 'silver'},
    {'id': 'ball_10000', 'nomi': '10000 ball yig\'uvchi', 'shart': 'ball >= 10000', 'rasm': 'gold'},
    {'id': 'kitob_5', 'nomi': '5 kitob o\'qigan', 'shart': 'kitoblar >= 5', 'rasm': 'reader'},
    {'id': 'pomodoro_10', 'nomi': '10 soat o\'qigan', 'shart': 'pomodoro >= 600', 'rasm': 'studious'},
    {'id': 'dostlar_5', 'nomi': '5 do\'st orttirgani', 'shart': 'dostlar >= 5', 'rasm': 'social'},
]

@app.route('/sertifikatlar')
def sertifikatlar():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    user = data[ism]
    olingan = user.get('sertifikatlar', [])

    # Sertifikatlarni tekshirish
    yangi_sertifikatlar = []
    for sert in SERTIFIKATLAR:
        if sert['id'] not in olingan:
            # Shartni tekshirish
            ball = user.get('ball', 0)
            kitoblar = len([k for k in user.get('kitoblar', []) if k.get('holat') == 'oqilgan'])
            pomodoro = user.get('pomodoro_stats', {}).get('jami_daqiqa', 0)
            dostlar = len(user.get('dostlar', []))

            olindi = False
            if sert['id'] == 'ball_1000' and ball >= 1000:
                olindi = True
            elif sert['id'] == 'ball_5000' and ball >= 5000:
                olindi = True
            elif sert['id'] == 'ball_10000' and ball >= 10000:
                olindi = True
            elif sert['id'] == 'kitob_5' and kitoblar >= 5:
                olindi = True
            elif sert['id'] == 'pomodoro_10' and pomodoro >= 600:
                olindi = True
            elif sert['id'] == 'dostlar_5' and dostlar >= 5:
                olindi = True

            if olindi:
                yangi_sertifikatlar.append(sert['id'])

    if yangi_sertifikatlar:
        if 'sertifikatlar' not in data[ism]:
            data[ism]['sertifikatlar'] = []
        data[ism]['sertifikatlar'].extend(yangi_sertifikatlar)
        save_data(sinf_id, data)
        olingan = data[ism]['sertifikatlar']

    # Sertifikat ma'lumotlari
    serts = []
    for sert in SERTIFIKATLAR:
        serts.append({
            **sert,
            'olingan': sert['id'] in olingan
        })

    return render_template('sertifikatlar.html', ism=ism, foydalanuvchi=data[ism],
                          sertifikatlar=serts, yangi=yangi_sertifikatlar)

# 15. MINI BLOG
@app.route('/blog')
def blog():
    if 'foydalanuvchi' not in session:
        return redirect(url_for('sinflar'))
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)

    blog_postlar = data[ism].get('blog', [])
    return render_template('blog.html', ism=ism, foydalanuvchi=data[ism], postlar=blog_postlar)

@app.route('/blog_yozish', methods=['POST'])
def blog_yozish():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    req = request.get_json()

    sarlavha = req.get('sarlavha', '').strip()
    matn = req.get('matn', '').strip()

    if not sarlavha or not matn:
        return jsonify({'success': False})

    if 'blog' not in data[ism]:
        data[ism]['blog'] = []

    data[ism]['blog'].insert(0, {
        'id': len(data[ism]['blog']) + 1,
        'sarlavha': sarlavha,
        'matn': matn,
        'vaqt': datetime.now().strftime('%Y-%m-%d %H:%M')
    })

    # Blog yozgani uchun 10 ball
    data[ism]['ball'] = data[ism].get('ball', 0) + 10
    save_data(sinf_id, data)
    return jsonify({'success': True})

@app.route('/blog_ochirish', methods=['POST'])
def blog_ochirish():
    if 'foydalanuvchi' not in session:
        return jsonify({'success': False})
    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    data = load_data(sinf_id)
    req = request.get_json()

    post_id = req.get('id')
    if 'blog' in data[ism]:
        data[ism]['blog'] = [p for p in data[ism]['blog'] if p['id'] != post_id]
        save_data(sinf_id, data)

    return jsonify({'success': True})

# ==================== TURNIRLAR ====================
TURNIR_DAVOMIYLIKLARI = {
    'kunlik': 1,      # 1 kun
    'haftalik': 7,    # 7 kun
    'oylik': 30,      # 30 kun
    'mavsumiy': 90    # 90 kun
}

def load_turnirlar(sinf_id):
    """Sinf turnirlarini yuklash"""
    sinf_dir = os.path.join(SINFLAR_DIR, sinf_id)
    turnir_file = os.path.join(sinf_dir, 'turnirlar.json')
    if os.path.exists(turnir_file):
        with open(turnir_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'kunlik': {'rasm': None, 'ishtirokchilar': [], 'goliblar': None, 'boshlanish': None, 'tugash': None, 'tarix': []},
        'haftalik': {'rasm': None, 'ishtirokchilar': [], 'goliblar': None, 'boshlanish': None, 'tugash': None, 'tarix': []},
        'oylik': {'rasm': None, 'ishtirokchilar': [], 'goliblar': None, 'boshlanish': None, 'tugash': None, 'tarix': []},
        'mavsumiy': {'rasm': None, 'ishtirokchilar': [], 'goliblar': None, 'boshlanish': None, 'tugash': None, 'tarix': []}
    }

def save_turnirlar(sinf_id, data):
    """Sinf turnirlarini saqlash"""
    sinf_dir = os.path.join(SINFLAR_DIR, sinf_id)
    if not os.path.exists(sinf_dir):
        os.makedirs(sinf_dir)
    turnir_file = os.path.join(sinf_dir, 'turnirlar.json')
    with open(turnir_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route('/turnirlar')
def turnirlar():
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return redirect(url_for('sinflar'))

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']
    tur = request.args.get('tur', 'kunlik')

    if tur not in TURNIR_DAVOMIYLIKLARI:
        tur = 'kunlik'

    data = load_data(sinf_id)
    turnir_data = load_turnirlar(sinf_id)

    # Admin ekanligini tekshirish
    is_admin = ism in ADMINS or session.get('test_account', False) or session.get('vip_account', False)

    # Joriy turnir
    turnir = turnir_data.get(tur, {})

    # Foydalanuvchi ishtirok etganmi
    user_submitted = any(ish['ism'] == ism for ish in turnir.get('ishtirokchilar', []))

    # Tarix
    tarix = turnir.get('tarix', [])

    return render_template('turnirlar.html',
        ism=ism,
        foydalanuvchi=data.get(ism, {}),
        tur=tur,
        turnir=turnir if turnir.get('boshlanish') else None,
        is_admin=is_admin,
        user_submitted=user_submitted,
        tarix=tarix
    )

@app.route('/turnir/yuborish', methods=['POST'])
def turnir_yuborish():
    """Foydalanuvchi rasmini qabul qilish"""
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']

    req = request.get_json()
    tur = req.get('tur', 'kunlik')
    rasm = req.get('rasm', '')

    if not rasm or not rasm.startswith('data:image'):
        return jsonify({'success': False, 'xato': 'Rasm noto\'g\'ri'})

    turnir_data = load_turnirlar(sinf_id)
    turnir = turnir_data.get(tur, {})

    if not turnir.get('rasm'):
        return jsonify({'success': False, 'xato': 'Hozircha faol turnir yo\'q'})

    # Allaqachon ishtirok etgan
    if any(ish['ism'] == ism for ish in turnir.get('ishtirokchilar', [])):
        return jsonify({'success': False, 'xato': 'Siz allaqachon ishtirok etgansiz!'})

    # Ishtirokchi qo'shish
    if 'ishtirokchilar' not in turnir:
        turnir['ishtirokchilar'] = []

    turnir['ishtirokchilar'].append({
        'ism': ism,
        'rasm': rasm,
        'vaqt': datetime.now().strftime('%Y-%m-%d %H:%M')
    })

    turnir_data[tur] = turnir
    save_turnirlar(sinf_id, turnir_data)

    return jsonify({'success': True})

@app.route('/turnir/admin/rasm', methods=['POST'])
def turnir_admin_rasm():
    """Admin rasm qo'yish"""
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']

    # Admin ekanligini tekshirish
    is_admin = ism in ADMINS or session.get('test_account', False) or session.get('vip_account', False)
    if not is_admin:
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req = request.get_json()
    tur = req.get('tur', 'kunlik')
    rasm = req.get('rasm', '')

    if not rasm or not rasm.startswith('data:image'):
        return jsonify({'success': False, 'xato': 'Rasm noto\'g\'ri'})

    turnir_data = load_turnirlar(sinf_id)

    # Yangi turnir boshlash
    davomiylik = TURNIR_DAVOMIYLIKLARI.get(tur, 1)
    from datetime import timedelta
    boshlanish = datetime.now()
    tugash = boshlanish + timedelta(days=davomiylik)

    turnir_data[tur] = {
        'rasm': rasm,
        'ishtirokchilar': [],
        'goliblar': None,
        'boshlanish': boshlanish.isoformat(),
        'tugash': tugash.isoformat(),
        'tarix': turnir_data.get(tur, {}).get('tarix', [])
    }

    save_turnirlar(sinf_id, turnir_data)
    return jsonify({'success': True})

@app.route('/turnir/admin/goliblar', methods=['POST'])
def turnir_admin_goliblar():
    """G'oliblarni saqlash va coin berish"""
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']

    # Admin ekanligini tekshirish
    is_admin = ism in ADMINS or session.get('test_account', False) or session.get('vip_account', False)
    if not is_admin:
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req = request.get_json()
    tur = req.get('tur', 'kunlik')
    golib1 = req.get('golib1', '')
    golib2 = req.get('golib2', '')
    golib3 = req.get('golib3', '')
    coin1 = int(req.get('coin1', 0))
    coin2 = int(req.get('coin2', 0))
    coin3 = int(req.get('coin3', 0))

    turnir_data = load_turnirlar(sinf_id)
    turnir = turnir_data.get(tur, {})

    # G'oliblarni saqlash
    turnir['goliblar'] = {
        'golib1': golib1,
        'golib2': golib2,
        'golib3': golib3,
        'coin1': coin1,
        'coin2': coin2,
        'coin3': coin3
    }

    turnir_data[tur] = turnir
    save_turnirlar(sinf_id, turnir_data)

    # Coinlarni berish
    data = load_data(sinf_id)

    if golib1 and golib1 in data and coin1 > 0:
        data[golib1]['ball'] = data[golib1].get('ball', 0) + coin1
        # Bildirishnoma
        if 'bildirishnomalar' not in data[golib1]:
            data[golib1]['bildirishnomalar'] = []
        data[golib1]['bildirishnomalar'].append({
            'tur': 'turnir',
            'xabar': f'Tabriklaymiz! {tur.capitalize()} turnirda 1-o\'rinni egallash uchun +{coin1} coin oldingiz!',
            'vaqt': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'oqilgan': False
        })

    if golib2 and golib2 in data and coin2 > 0:
        data[golib2]['ball'] = data[golib2].get('ball', 0) + coin2
        if 'bildirishnomalar' not in data[golib2]:
            data[golib2]['bildirishnomalar'] = []
        data[golib2]['bildirishnomalar'].append({
            'tur': 'turnir',
            'xabar': f'Tabriklaymiz! {tur.capitalize()} turnirda 2-o\'rinni egallash uchun +{coin2} coin oldingiz!',
            'vaqt': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'oqilgan': False
        })

    if golib3 and golib3 in data and coin3 > 0:
        data[golib3]['ball'] = data[golib3].get('ball', 0) + coin3
        if 'bildirishnomalar' not in data[golib3]:
            data[golib3]['bildirishnomalar'] = []
        data[golib3]['bildirishnomalar'].append({
            'tur': 'turnir',
            'xabar': f'Tabriklaymiz! {tur.capitalize()} turnirda 3-o\'rinni egallash uchun +{coin3} coin oldingiz!',
            'vaqt': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'oqilgan': False
        })

    save_data(sinf_id, data)
    return jsonify({'success': True})

@app.route('/turnir/admin/yangilash', methods=['POST'])
def turnir_admin_yangilash():
    """Yangi turnir boshlash"""
    if 'foydalanuvchi' not in session or 'sinf_id' not in session:
        return jsonify({'success': False, 'xato': 'Tizimga kiring'})

    ism = session['foydalanuvchi']
    sinf_id = session['sinf_id']

    # Admin ekanligini tekshirish
    is_admin = ism in ADMINS or session.get('test_account', False) or session.get('vip_account', False)
    if not is_admin:
        return jsonify({'success': False, 'xato': 'Ruxsat yo\'q'})

    req = request.get_json()
    tur = req.get('tur', 'kunlik')

    turnir_data = load_turnirlar(sinf_id)
    eski_turnir = turnir_data.get(tur, {})

    # Eski turnirni tarixga qo'shish
    if eski_turnir.get('boshlanish'):
        tarix_entry = {
            'sana': eski_turnir.get('boshlanish', '')[:10],
            'ishtirokchilar_soni': len(eski_turnir.get('ishtirokchilar', [])),
            'goliblar': eski_turnir.get('goliblar')
        }

        if 'tarix' not in turnir_data.get(tur, {}):
            turnir_data[tur]['tarix'] = []
        turnir_data[tur]['tarix'].append(tarix_entry)

    # Yangi turnir
    turnir_data[tur] = {
        'rasm': None,
        'ishtirokchilar': [],
        'goliblar': None,
        'boshlanish': None,
        'tugash': None,
        'tarix': turnir_data.get(tur, {}).get('tarix', [])
    }

    save_turnirlar(sinf_id, turnir_data)
    return jsonify({'success': True})

# Production uchun sozlamalar
migrate_old_data()
load_sinflar()
update_sinf_count('bizning_sinf')

if __name__ == '__main__':
    # Port va debug sozlamalari
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    print("\n" + "="*50)
    print("Web-sayt ishga tushdi!")
    print(f"Brauzerda oching: http://127.0.0.1:{port}")
    print("="*50 + "\n")
    socketio.run(app, debug=debug, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
