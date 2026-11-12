"""Lihat struktur berkas dataset (CSV / XLSX) tanpa mengubah apa pun.

Pakai:  python inspect_dataset.py "folder_atau_berkas"
Contoh: python inspect_dataset.py req_dataset
Salin SELURUH hasilnya ke chat agar skrip impor bisa dibuat sesuai kolom aslinya.
"""
import csv
import sys
from collections import Counter
from pathlib import Path


def read_rows(path):
    if path.suffix.lower() == ".xlsx":
        import openpyxl  # pip install openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = [["" if c is None else str(c) for c in r] for r in ws.iter_rows(values_only=True)]
            if rows:
                yield f"{path.name} [sheet: {ws.title}]", rows[0], rows[1:]
        return
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(raw[:4000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(raw.splitlines(), dialect))
    if rows:
        yield path.name, rows[0], rows[1:]


def show(name, header, body):
    print("=" * 78); print(name); print(f"{len(body)} baris, {len(header)} kolom"); print("kolom:", header)
    cols = list(zip(*[r + [""] * (len(header) - len(r)) for r in body])) if body else []
    for h, col in zip(header, cols):
        uniq = Counter(col)
        avg = sum(len(v) for v in col) / max(len(col), 1)
        print(f"\n- kolom '{h}': {len(uniq)} nilai unik, rata-rata panjang {avg:.0f} karakter")
        if len(uniq) <= 40:
            print("  sebaran:", dict(uniq.most_common(40)))
        else:
            print("  contoh:", [v[:70] for v in list(uniq)[:3]])
    print("\n5 baris pertama:")
    for r in body[:5]:
        print("  ", [c[:60] for c in r])


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    target = Path(sys.argv[1])
    files = [target] if target.is_file() else sorted(p for p in target.rglob("*") if p.suffix.lower() in (".csv", ".xlsx", ".tsv", ".txt"))
    if not files:
        sys.exit("Tidak ada berkas .csv/.xlsx ditemukan.")
    for f in files:
        try:
            for name, header, body in read_rows(f):
                show(name, header, body)
        except Exception as exc:
            print(f"{f.name}: gagal dibaca ({type(exc).__name__}: {exc})")


if __name__ == "__main__":
    main()
