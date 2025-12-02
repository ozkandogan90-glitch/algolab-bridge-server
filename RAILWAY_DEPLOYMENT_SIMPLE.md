# RAILWAY DEPLOYMENT - BASIT KURULUM

## 🚀 3 Adımda Çalıştır

### 1. Environment Variables (İsteğe Bağlı)

Railway Dashboard → Variables sekmesine git.

**Hiçbir şey eklemesen de çalışır!** Ama istersen:

```bash
LOG_LEVEL=INFO
ENVIRONMENT=production
```

⚠️ **ÖNEMLI:** `PORT` ekleme! Railway otomatik set eder.

---

### 2. Deploy Et

Railway otomatik deploy eder.

---

### 3. Test Et

```bash
curl https://algolab-bridge-server-production.up.railway.app/health
```

**Beklenen:**
```json
{
  "status": "healthy",
  "environment": "production"
}
```

---

## Backend'de URL'yi Ayarla

Ana backend'de:

```bash
ALGOLAB_BRIDGE_URL=https://algolab-bridge-server-production.up.railway.app
```

---

## ⚠️ Şu Anda Devre Dışı

- ❌ JWT Authentication
- ❌ Algolab API
- ❌ Redis

Sadece /health çalışıyor. İleride eklenecek.

---

## Sorun mu var?

Railway Dashboard → Deployments → Logs
