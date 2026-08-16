# OpenAmer Agent

**Agen AI yang terus meningkatkan diri — belajar dari pengalaman, menciptakan keterampilan, mengingat preferensi Anda, dan bekerja untuk Anda di mana saja.**

**Perangkat Lunak Penerjemah Profesional**
Terjemahan ke dalam Bahasa Indonesia (asli: Bahasa Indonesia). Simpan format Markdown (**, teks tampilan link) asli, biarkan perintah/URL utuh. Kembalikan hanya terjemahan, tidak ada komentar/pemisah.

## Fitur

- **Antarmuka terminal yang sebenarnya — TUI penuh dengan autocomplete, sejarah, dan keluaran alat streaming**
- **Hidup di mana Anda tinggal — Telegram, Discord, Slack, WhatsApp dan lebih dari satu pintu masuk**
- **Belajar secara berkelanjutan — memori, kemampuan yang memperbaiki diri sendiri, pengingat antar-sesi**
- **Delegasikan & paralelkan — spawn subagen untuk pekerjaan paralel**
- **Automatisasi yang dijadwalkan — cron bawaan untuk laporan harian, cadangan, audit**
- **Dapat dijalankan di mana saja — lokal, Docker, SSH, cloud, serverless**

## Pemasangannya Cepat

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## Mengawali Pengerjaan

```bash
openamer              # Apa yang ingin dibicarakan?
openamer setup        # **Mengatur Kunci API & Provider**

Untuk mengatur kunci API dan provider, Anda perlu mengikuti langkah-langkah berikut:

1. **Daftar ke layanan API**: Daftar ke layanan API yang Anda inginkan, seperti Google Cloud Platform, AWS, atau lainnya.
2. **Membuat kunci API**: Setelah Anda terdaftar, buat kunci API baru. Kunci API ini akan digunakan untuk mengakses layanan API.
3. **Simpan kunci API**: Simpan kunci API Anda dengan aman, seperti di dalam file teks atau menggunakan layanan manajemen kunci API.
4. **Konfigurasi provider**: Konfigurasi provider API Anda di dalam aplikasi atau proyek Anda. Ini biasanya melibatkan mengisi informasi kunci API dan URL API.

**Contoh penggunaan**

* **Menggunakan kunci API di Python**: Untuk menggunakan kunci API di Python, Anda dapat menggunakan library seperti `requests` dan `json`.
```python
import requests

api_key = "YOUR_API_KEY"
api_url = "https://api.example.com/endpoint"

response = requests.get(api_url, headers={"Authorization": f"Bearer {api_key}"))
```
* **Menggunakan kunci API di Node.js**: Untuk menggunakan kunci API di Node.js, Anda dapat menggunakan library seperti `axios` dan `jsonwebtoken`.
```javascript
const axios = require('axios');

const apiKey = 'YOUR_API_KEY';
const apiUrl = 'https://api.example.com/endpoint';

axios.get(apiUrl, {
  headers: {
    Authorization: `Bearer ${apiKey}`,
  },
})
  .then((response) => {
    console.log(response.data);
  })
  .catch((error) => {
    console.error(error);
  });
```
Perlu diingat bahwa Anda harus mengganti `YOUR
openamer model        # Pilih model Anda
openamer update       # Perbarui ke versi terbaru.
```

## Mengupdate

OpenAmer memeriksa pembaruan secara otomatis dan menampilkan peringatan di banner selamat datang. Jalankan perintah openamer update untuk mendapatkan versi terbaru — ia akan membackup data Anda terlebih dahulu.

## Mengkontribusikan

Kontribusi selalu diterima — buka isu terbuka, kirim pull request, atau bergabunglah dengan komunitas.

## Hak Cipta

Lisensi Apache 2.0. Lihat {LICENSE}.
