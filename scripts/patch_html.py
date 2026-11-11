from pathlib import Path
src=Path('/mnt/data/inu-tv-v3.8-semua-channel-main.html').read_text()
s=src.replace('INU TV V3.8','INU TV V3.9').replace('V3.7 + V3.8','V3.9 Server Scanner')
s=s.replace('Daftar utama hanya menampilkan channel dengan frame video terdeteksi. Auto Discovery berjalan setelah playlist dimuat.','Semua channel ditampilkan, termasuk yang belum diuji dan yang gagal. Status berasal dari server.')
s=s.replace('Hasil lokal browser','Hasil server GitHub Actions').replace('Hanya channel dengan frame video terdeteksi yang muncul di daftar utama. Status audio belum dipastikan. Hasil scan lokal dan tidak dibagikan ke pengunjung lain.','Semua channel ditampilkan. Hasil server FFprobe bukan jaminan pemutaran di browser; CORS, codec, dan jaringan dapat berbeda.')
s=s.replace('Auto Discovery berjalan terus dalam batch 100 URL: Indonesia lebih dulu, lalu negara lain. Hasil disimpan otomatis di browser setiap channel dan bisa diunduh sebagai CSV per batch atau gabungan. Pengujian satu per satu, tanpa klik Scan. Pemutaran diuji dalam keadaan muted; frame video yang maju menandakan video berhasil didekode. Audio belum bisa dipastikan otomatis di semua browser.','Server GitHub Actions menguji 200 URL setiap 6 jam. Tombol scan browser tetap tersedia untuk uji manual, tetapi tidak berjalan otomatis. Status server diperbarui saat JSON diterbitkan.')
s=s.replace('Urutan channel lolos:','Urutan channel:')
s=s.replace("if(!visible.length)root.innerHTML='<div class=\"empty\">Belum ada channel lolos tes video. Auto Discovery sedang memeriksa sumber; channel akan muncul otomatis jika lolos. Pastikan halaman tetap terbuka.</div>'","if(!visible.length)root.innerHTML='<div class=\"empty\">Tidak ada channel yang cocok dengan filter saat ini.</div>'")
s=s.replace('testerCountries();testerUpdate();scheduleAutoDiscovery();setStatus(', 'testerCountries();testerUpdate();loadServerScan();setStatus(')
# Disable auto browser scan on initial load; manual scan remains available.
needle='renderCategories();loadPlaylists();loadEPG();setInterval(updateEPG,30000);'
insert='''// V3.9: use server JSON as shared scan status; do not start browser discovery automatically.
let serverScanMeta=null;
async function loadServerScan(){
 try{
  const [catalogResponse,resultsResponse]=await Promise.all([
   fetch('./data/channels.json?ts='+Date.now(),{cache:'no-store'}),
   fetch('./data/scan-results.json?ts='+Date.now(),{cache:'no-store'})
  ]);
  if(!catalogResponse.ok||!resultsResponse.ok)throw Error('JSON server belum tersedia (jalankan GitHub Actions dulu)');
  const catalog=await catalogResponse.json(),payload=await resultsResponse.json();
  if(!Array.isArray(catalog.channels)||!payload.results)throw Error('Format JSON tidak sesuai');
  // The server catalog is authoritative for public channels; retain browser playlist metadata when possible.
  const known=new Set(channels.flatMap(c=>c.sources||[c.url]));
  const additions=[];
  for(const item of catalog.channels){
   if(!item.url||known.has(item.url))continue;
   known.add(item.url);
   additions.push({...item,categories:classify(item.group||'',item.name||''),key:item.url,sources:[item.url]});
  }
  if(additions.length)merge([...channels,...additions]);
  // Match any alternate URL to the grouped channel key.
  for(const c of channels){
   const candidates=(c.sources||[c.url]).map(u=>payload.results[u]).filter(Boolean);
   if(!candidates.length)continue;
   const preferred=candidates.find(r=>r.status==='ok')||candidates.slice().sort((a,b)=>(b.checkedAt||'').localeCompare(a.checkedAt||''))[0];
   testerResults[c.key]={status:preferred.status,detail:preferred.detail,checkedAt:preferred.checkedAt,url:preferred.url,name:c.name,country:c.country};
  }
  serverScanMeta=payload;
  testerCountries();testerUpdate();filterChannels();
  const status=$('testerMessage');if(status)status.textContent='Server scanner aktif · terakhir update '+(payload.generatedAt||'belum ada')+' · FFprobe (bukan playback browser)';
 }catch(e){
  const status=$('testerMessage');if(status)status.textContent='Data server belum siap: '+e.message+' · channel dari playlist browser tetap tersedia.';
 }
}
'''
s=s.replace(needle,insert+needle)
s=s.replace("const updated=$('monitorUpdated');if(updated)updated.textContent='Data hanya di browser ini';","const updated=$('monitorUpdated');if(updated)updated.textContent=serverScanMeta?.generatedAt?('Server: '+serverScanMeta.generatedAt):'Menunggu JSON server';")
s=s.replace('setInterval(updateEPG,30000);','setInterval(updateEPG,30000);setInterval(loadServerScan,10*60*1000);')
# Server source status should not be overwritten by local storage, browser manual scan still possible.
Path('/mnt/data/inu-tv-v3.9-package/main39.html').write_text(s)
