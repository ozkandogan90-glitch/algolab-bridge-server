# RAILWAY DEPLOYMENT - BASIT KURULUM

## 🚀 3 Adımda Çalıştır

### 1. Environment Variables (TAMAMEN İSTEĞE BAĞLI!)

Railway Dashboard → Variables sekmesine git.

**Hiçbir şey eklemesen de çalışır!** Varsayılan değerler kullanılır.

İstersen ekleyebilirsin:

```bash
LOG_LEVEL=INFO
ENVIRONMENT=production
```

⚠️ **ÖNEMLI:** `PORT` ekleme! Railway otomatik set eder.

---

### 2. Deploy Et

Railway otomatik deploy eder. Ya da:
- Dashboard → Deployments → "Deploy Now"

---

### 3. Test Et

```bash
curl https://algolab-bridge-server-production.up.railway.app/health
```

**Beklenen Yanıt:**
```json
{
  "status": "healthy",
  "environment": "production",
  "redis": "connected",
  "algolab_api_url": "https://www.algolab.com.tr/api"
}
```

---

## 📝 Backend'de URL'yi Ayarla

Ana backend projesinde `.env`:

```bash
ALGOLAB_BRIDGE_URL=https://algolab-bridge-server-production.up.railway.app
```

Artık backend bu URL'den bridge'e health check yapabilir:

```bash
GET /internal/algolab-bridge/status
```

---

## ⚠️ ŞU ANDA DEVRE DIŞI (İleride Eklenecek)

- ❌ JWT Authentication - Şimdilik dummy değer
- ❌ Algolab API gerçek bağlantısı - Sadece placeholder
- ❌ Redis - Opsiyonel, şimdilik local fallback

Bunlar ileride eklenecek. **Şimdilik sadece bridge server ayağa kalkıyor ve /health endpoint çalışıyor.**

---

## 🐛 Sorun Giderme

### Health endpoint 404 veriyor?
Railway Dashboard → Deployments → Logs kontrol et

### Redis connection failed?
Normal! Redis plugin eklenmemiş. Şimdilik önemli değil.

### Port already in use?
Railway otomatik PORT atar. Manuel PORT ekleme!

---

## ✅ Başarı Kriteri

Şu komut çalışıyorsa başarılı:

```bash
curl https://algolab-bridge-server-production.up.railway.app/health
```

Ve backend bu endpoint'i çağırabiliyor:

```bash
curl http://your-backend.railway.app/internal/algolab-bridge/status
```

---

## 📦 Dosya Referansları

- **Minimal .env örneği:** `.env.railway` dosyasına bakın
- **Config detayları:** `app/config.py` - Tüm fieldler optional
