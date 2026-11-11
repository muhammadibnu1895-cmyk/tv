# INU TV V3.9 — GitHub Actions Server Auto Scanner

**Produksi `index.html` tidak disentuh.** Upload isi folder paket ini ke root repo `tv`, termasuk folder tersembunyi `.github/workflows`.

## Instalasi

1. Upload `main39.html`, `scripts/scan.py`, `.github/workflows/scan.yml`, `data/channels.json`, dan `data/scan-results.json` ke **root repository** (pertahankan struktur folder).
2. Di GitHub repo: **Settings → Actions → General → Workflow permissions → Read and write permissions**, lalu Save. Jika pengaturan dibatasi organisasi, perlu penyesuaian izin.
3. Buka tab **Actions → INU TV server scan → Run workflow** untuk scan pertama. Jadwal berikutnya `17 */6 * * *` (UTC): pukul **01:17, 07:17, 13:17, 19:17 WIB**. Jadwal GitHub Actions bisa terlambat atau terlewat; bukan jaminan real-time.
4. Setelah workflow sukses dan JSON ter-commit, buka `https://muhammadibnu1895-cmyk.github.io/tv/main39.html`. Jika GitHub Pages menggunakan deployment branch lain, pastikan folder `data/` ikut terpublikasi.
5. Biarkan `index.html` tetap seperti sekarang selama pengujian.

## Cara kerja

- Mengambil 11 playlist negara dari iptv-org; menghapus URL duplikat persis.
- Menyimpan seluruh katalog di `data/channels.json`.
- Memilih **200 URL per eksekusi**: belum diuji → gagal paling lama → berhasil paling lama.
- Memeriksa maksimal 4 URL paralel dengan FFprobe (timeout sekitar 15 detik per URL). Status `ok` hanya berarti **stream video terdeteksi**. Tidak memverifikasi suara, kualitas gambar, hak akses, atau kompatibilitas browser.
- Menyimpan hasil dan riwayat ringkas (`checks`, `lastOkAt`) di `data/scan-results.json`, lalu GitHub Actions melakukan commit otomatis.
- Halaman `main39.html` menampilkan semua channel dan status dari JSON server. Pemindaian browser otomatis **dinonaktifkan**; tombol scan manual tetap tersedia.
- Channel gagal akan diuji ulang setelah URL yang belum diuji habis. Pada 3.022 URL, 200 per 6 jam berarti setidaknya **16 eksekusi (~4 hari)** untuk putaran pertama, jika workflow selalu berjalan dan sumber tetap stabil.

## Batasan dan keamanan

- Repository publik membuat JSON dan URL stream **publik**. Jangan menaruh kredensial, token, atau playlist privat di dalamnya.
- FFprobe bisa gagal pada stream dengan pembatasan geo/IP, sementara browser berhasil, atau sebaliknya (CORS/codec).
- GitHub Actions memiliki batas kuota, penjadwalan, dan masa hidup job. Pada repository publik, jadwal dapat dinonaktifkan setelah lama tidak aktif. Pantau Actions dan commit hasil.
- Jika `git push` gagal karena branch protection, gunakan pull request atau sesuaikan izin; jangan mematikan proteksi tanpa pertimbangan.
- Jika sumber M3U tidak tersedia, scanner mempertahankan katalog lama. Tidak ada jaminan jumlah channel tetap 3.022.
- Data scanner server dan hasil manual browser dapat berbeda. Reload halaman untuk mengambil JSON terbaru.

## Tes lokal

```bash
python3 -m http.server 8000
# lalu buka http://localhost:8000/main39.html
```

Untuk uji scanner lokal diperlukan `ffprobe` terpasang. Jalankan `python3 scripts/scan.py --batch 5 --workers 2 --timeout 8` (memerlukan internet). Jangan menguji stream yang tidak Anda berhak akses.
