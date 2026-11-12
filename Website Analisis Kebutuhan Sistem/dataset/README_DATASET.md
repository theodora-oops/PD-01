# Dataset acuan SIKARA (`sikara_gold.jsonl`)

## STATUS PENTING
Seluruh 12 kasus di sini adalah **DRAF** (`"status": "draft_ai"`). Belum divalidasi
pakar manapun. Jangan menyebutnya "dataset tervalidasi" di laporan/skripsi sebelum Anda menjalankan
protokol validasi di bawah. Fungsinya: kerangka awal + contoh format yang bisa Anda perluas.

## Isi
- `split: "example"` (4 kasus): dipakai sebagai contoh few-shot yang disisipkan ke prompt Gemini.
- `split: "eval"` (8 kasus): HANYA untuk pengujian; tidak pernah dipakai sebagai contoh (mencegah kebocoran).

Field per kasus: `id`, `split`, `domain`, `status`, `input` (deskripsi mentah seperti ketikan pengguna),
`actors` (`name`, `role`, `description`, `aliases` = sinonim untuk pencocokan), `requirements`
(`actor`, `text`, `priority`), dan khusus `example`: `summary`, `user_stories`.

## Dataset publik (Inggris) dan cara memakainya
Urut dari yang paling cocok dengan tugas SIKARA (deskripsi kebutuhan -> aktor, kebutuhan, user story):
| Dataset | Isi | Kecocokan |
|---|---|---|
| **User stories Dalpiaz** https://data.mendeley.com/datasets/7zbk8zsd8y/2 (CC BY 4.0) | 22 aplikasi, 1.679 user story (satu per baris, berkas .txt) | **Paling cocok.** Berisi aktor + tujuan + manfaat tulisan manusia. Sudah ada skrip impor (di bawah). |
| Dalpiaz 2020 (Zenodo) | user story dan use case terperinci untuk 3 aplikasi: sistem manajemen rumah sakit (HOS), simulator lalu lintas kota (SIM), portal asosiasi sepak bola (IFA) | Lebih rinci, tetapi hanya 3 aplikasi. Lisensi belum saya verifikasi. |
| PURE | 79 dokumen kebutuhan (SRS) publik | Bahan uji untuk mode UNGGAH DOKUMEN. Tidak ada kunci jawaban. |
| FR-NFR (Mendeley) https://data.mendeley.com/datasets/4ysx9fyzv4 dan PROMISE NFR | kalimat kebutuhan berlabel FR/NFR | Hanya untuk pengklasifikasi fungsional vs non-fungsional, bukan untuk menghasilkan kebutuhan. |

### Alur: Dalpiaz -> terjemahan AI -> kasus uji Indonesia
1. Di halaman Mendeley, klik **Download All**, ekstrak ke folder `dalpiaz_raw\`.
2. `python import_dalpiaz.py --src dalpiaz_raw --limit 3` (coba 3 produk), lalu tanpa `--limit` untuk semua.
3. Hasil: `dataset/dalpiaz_id.jsonl`, 1 kasus per produk (8 story acak, seed tetap). Setiap kasus menyimpan
   story Inggris asli di `source_stories_en` agar terjemahan bisa dicek.
4. `python evaluate.py --modes rule,zero,few --only dp-` menguji semuanya. `--only ev-` hanya kasus buatan sendiri.

Yang perlu dipahami tentang kasus hasil impor:
- Kunci jawaban (aktor dan kebutuhan) berasal dari story tulisan manusia. Namun teks MASUKAN (deskripsi awam)
  ditulis oleh AI dari story tersebut, dan terjemahannya juga oleh AI. Ungkapkan ini di laporan.
- Prioritas kosong (`null`) karena dataset asal tidak memilikinya.
- Hanya 8 story per produk yang dipakai; Gemini yang baik bisa menghasilkan kebutuhan valid lain, yang akan
  terhitung "ekstra" (bukan salah). Periksa `evaluasi/detail.md`.
- Status `translated_ai`: perlu pemeriksaan manual terhadap sampel (mis. 20% kasus) oleh Anda atau dosen.
- Wajib mencantumkan atribusi: lihat `ATTRIBUTION.md`.

## Protokol validasi (agar layak disebut "tervalidasi")
1. Kumpulkan deskripsi kebutuhan nyata (proposal, skripsi, dokumen unit PM) atau minta calon pengguna
   menulis deskripsi singkat. Anonimkan data pribadi. Target awal yang masuk akal: 30 kasus atau lebih.
2. Dua penilai (misalnya Anda dan dosen/praktisi) menyusun daftar aktor dan kebutuhan secara
   INDEPENDEN untuk tiap kasus, tanpa melihat hasil AI.
3. Gabungkan; selisihnya didiskusikan sampai sepakat. Catat tingkat kesepakatan awal
   (mis. persentase kebutuhan yang sama, atau Cohen's kappa).
4. Ubah `status` kasus menjadi `validated`, catat penilai dan tanggal.
5. Pisahkan kasus `eval` dari `example` seperti sekarang. Jangan ubah kasus `eval` setelah melihat
   hasil AI.

## Menjalankan evaluasi
```bat
python evaluate.py --modes rule                      :: tanpa LLM, bisa offline
python evaluate.py --modes rule,zero,few --sleep 8   :: perbandingan 3 metode
```
Hasil: `evaluasi\ringkasan.csv` (per kasus) dan `evaluasi\detail.md` (kebutuhan yang tidak ditemukan
dan yang ekstra; periksa manual).
- `rule` = analisis berbasis aturan lama, `zero` = Gemini tanpa contoh, `few` = Gemini + contoh dari dataset.
- Kecocokan kebutuhan diukur dengan kemiripan kata (Dice), bukan makna. Parafrase yang benar bisa
  terhitung salah dan sebaliknya, jadi angka ini perkiraan kasar. Selalu baca `detail.md`.
- "Precision" cenderung terlalu rendah karena kebutuhan ekstra yang valid dianggap salah.
- Pemanggilan Gemini gratis memakai kuota; `--sleep` menjaga jeda antar panggilan.

## Menambah kasus
Tambahkan satu baris JSON baru di `sikara_gold.jsonl` mengikuti field di atas (satu kasus per baris).
Aktor di `requirements` harus sama persis dengan salah satu `actors[].name`.
