"""Tes koneksi Gemini + daftar model yang bisa dipakai.
Jalankan:  python cek_gemini.py
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()
key = os.environ.get("GEMINI_API_KEY", "").strip()
if not key:
    sys.exit("GEMINI_API_KEY di .env masih kosong. Buat key di https://aistudio.google.com/apikey")

from google import genai

client = genai.Client(api_key=key)

print("Model Gemini yang bisa dipakai untuk generateContent:")
for m in client.models.list():
    actions = getattr(m, "supported_actions", None) or []
    if "generateContent" in actions and "gemini" in m.name:
        print("  -", m.name.replace("models/", ""))

model = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
print(f"\nMengetes model '{model}' ...")
r = client.models.generate_content(model=model, contents="Jawab satu kalimat: apa itu analisis kebutuhan sistem?")
print(r.text)
print("\nBERHASIL. Gemini siap dipakai.")
