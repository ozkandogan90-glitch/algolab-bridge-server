# Railway Deployment Configuration Guide

## Bridge Server & Backend Auto-Connection Setup

Bu guide, Bridge Server'ın Railway'de Backend ile otomatik olarak bağlanması için gerekli konfigürasyonu açıklar.

## Sorun: Bridge Server localhost'a bağlanmaya çalışıyor

Eğer Railway logs'larında şöyle hata görüyorsanız:
```
⚠️ Failed to register with Backend
error: "All connection attempts failed"
backend_url: "http://localhost:8001"
```

Bu, Bridge Server'ın **production url yerine localhost'u kullanmaya çalışıyor** demektir.

## Çözüm: Railway Dashboard'da Environment Variables Ayarlayın

### Adım 1: Bridge Server Project'ine Gidin
1. https://railway.com adresine giriş yapın
2. "Trader_Eidos_Bridge_Server_TR" project'ini seçin
3. **Variables** sekmesine tıklayın

### Adım 2: Environment Variables'ı Ayarlayın

Aşağıdaki variable'ları ekleyin veya update edin:

| Variable Name | Value | Açıklama |
|---|---|---|
| `BACKEND_URL` | `https://trader-eidos-suite-backend-production.up.railway.app` | Backend sunucusunun public adresi |
| `BRIDGE_PUBLIC_URL` | `https://algolab-bridge-server-production.up.railway.app` | Bridge Server'ın public adresi |
| `ENVIRONMENT` | `production` | Ortam adı |
| `LOG_LEVEL` | `INFO` | Log seviyesi |
| `LOG_FORMAT` | `text` | Log formatı |

### Adım 3: Variables'ı Save Edin

1. Her variable'ı girdikten sonra **Add Variable** butonuna tıklayın
2. Tüm variable'lar eklendikten sonra sayfa otomatik deploy edilir

## Adım 4: Redeploy (Önemli!)

Variables ayarlandıktan sonra:

1. **Deployments** sekmesine gidin
2. Son deployment'i bul
3. **Redeploy** butonuna tıklayın
4. Deploy tamamlanana kadar bekleyin (~2-3 dakika)

## Adım 5: Logs'ları Kontrol Edin

1. **Logs** sekmesine gidin
2. Aşağıdaki mesajlar görmelisiniz:

✅ **Başarılı Bağlantı:**
```
🚀 Bridge Server Starting
✅ Redis Connected
📝 Attempting to register with Backend
  backend_url: "https://trader-eidos-suite-backend-production.up.railway.app"
🌉 Bridge Server Registered with Backend
✅ Bridge Server Started and Ready
```

❌ **Başarısız Bağlantı:**
```
⚠️ Failed to register with Backend (will continue anyway)
error: "Connection refused"
```

## Backend Tarafında Kontrol

Backend'de de Bridge Server'ın registered olduğunu doğrulayabilirsiniz:

```bash
curl https://trader-eidos-suite-backend-production.up.railway.app/api/admin/bridge/status
```

Response:
```json
{
  "connected": true,
  "bridge_url": "https://algolab-bridge-server-production.up.railway.app",
  "last_registered": "2025-12-02T11:00:00",
  "last_ping": "2025-12-02T11:01:00",
  "message": "✅ Bridge Server connected (Algolab Bridge Server)"
}
```

## Health Check

Bridge Server, her 60 saniyede bir Backend'e aşağıdaki ping gönderir:

```
POST /api/admin/bridge/ping
{
  "status": "alive",
  "timestamp": "2025-12-02T11:00:30"
}
```

Backend bunu `💓 Health check ping received` olarak kaydeder.

## Shutdown/Disconnect

Bridge Server kapatılırken Backend'e şu bildirim gönderir:

```
POST /api/admin/bridge/disconnect
```

Backend bunu `🔌 Bridge Server Disconnected` olarak kaydeder.

## Troubleshooting

### Problem: BACKEND_URL hâlâ localhost gösteriyor

**Nedeni:** Railway deploy öncesinde variable set edilmiş veya yanlış environment'a set edilmiş.

**Çözümü:**
1. Railway dashboard'da Variables sekmesinde BACKEND_URL'i kontrol edin
2. Doğru URL olduğundan emin olun: `https://trader-eidos-suite-backend-production.up.railway.app`
3. Redeploy yapın

### Problem: Connection timeout hatası alıyorum

**Nedeni:** Backend'in domain adı yanlış veya Backend aşağıda.

**Çözümü:**
1. Backend'in Railway dashboard'ında aynı URL'nin görünüp görünmediğini kontrol edin
2. Backend'in `Domains` sekmesinde public domain'in aktif olduğundan emin olun
3. `curl` ile test edin:
   ```bash
   curl https://trader-eidos-suite-backend-production.up.railway.app/api/health
   ```

### Problem: Variable set ettim ama yine eski URL'yi kullanıyor

**Nedeni:** Redeploy yapılmamış.

**Çözümü:**
1. Variables sekmesinde değişiklikleri kaydedin
2. **Deployments** sekmesine gidin
3. **Redeploy** butonuna tıklayın
4. Deploy tamamlanana kadar bekleyin

## Local Development

Local'da test ederken:

```bash
# .env dosyasında şu değerleri ayarlayın:
BACKEND_URL=http://localhost:8001
BRIDGE_PUBLIC_URL=http://localhost:8000
ENVIRONMENT=development
```

Ardından:

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Production Flow

```
Railway Bridge Server Starts
    ↓
[register_with_backend() via HTTPS]
    ↓
Backend receives registration
    ↓
Backend stores: bridge_url, last_registered, environment
    ↓
Bridge Server starts health check loop (every 60s)
    ↓
Backend updates: last_ping
    ↓
Frontend can query /api/admin/bridge/status anytime
```

## Kontrol Listesi

- [ ] Railway Bridge Server project'inin Variables sekmesinde BACKEND_URL set edildi
- [ ] BACKEND_URL = `https://trader-eidos-suite-backend-production.up.railway.app`
- [ ] BRIDGE_PUBLIC_URL set edildi (Railway'nin otomatik assign ettiği domain)
- [ ] Redeploy yapıldı
- [ ] Logs'larda "🌉 Bridge Server Registered with Backend" mesajı görüldü
- [ ] Backend'de /api/admin/bridge/status 200 dönüyor ve "connected: true"

---

**Sorularınız varsa:** Logs'lara bakın - hem Bridge Server hem Backend detaylı bilgi loguyor.
