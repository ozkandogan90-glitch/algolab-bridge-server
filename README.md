# Algolab Bridge Server

**Version:** 1.0.0
**Purpose:** Proxy server to bypass Algolab API Turkey IP restriction

---

## 📖 Overview

The Algolab Bridge Server is a lightweight FastAPI application designed to proxy requests between Railway (international) and Algolab API (Turkey-only). It handles:

- ✅ AES-CBC encryption for credentials
- ✅ SHA256 request signing (Checker header)
- ✅ 2FA SMS authentication flow
- ✅ Session management with Redis
- ✅ Rate limiting (5-second minimum interval)
- ✅ JWT authentication from Railway backend

---

## 🏗️ Architecture

```
Railway Backend (Int'l) → Bridge Server (TR VPS) → Algolab API (TR)
```

**Location:** Turkish VPS (Ubuntu 20.04)
**Tech Stack:** Python 3.10+, FastAPI, Redis, httpx

---

## 📦 Installation

### Prerequisites

- Python 3.10 or higher
- Redis server
- Ubuntu 20.04 (or similar Linux)

### Setup

```bash
# Clone repository
cd /opt
git clone <repository>
cd bridge_server

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Edit with your configuration
```

### Environment Configuration

```bash
# .env
ALGOLAB_API_URL=https://www.algolab.com.tr/api
BRIDGE_JWT_SECRET=<generate-strong-secret>
REDIS_URL=redis://localhost:6379/0
ENVIRONMENT=production
```

Generate JWT secret:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 🚀 Running the Server

### Development

```bash
source venv/bin/activate
python -m app.main
```

Server will start at `http://0.0.0.0:8000`

### Production (systemd)

Create `/etc/systemd/system/algolab-bridge.service`:

```ini
[Unit]
Description=Algolab Bridge Server
After=network.target redis.service

[Service]
Type=simple
User=bridge
WorkingDirectory=/opt/bridge_server
Environment="PATH=/opt/bridge_server/venv/bin"
ExecStart=/opt/bridge_server/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable algolab-bridge
sudo systemctl start algolab-bridge
sudo systemctl status algolab-bridge
```

### Nginx Reverse Proxy

`/etc/nginx/sites-available/bridge`:

```nginx
server {
    listen 80;
    server_name your-bridge-domain.com;

    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name your-bridge-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-bridge-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-bridge-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90;
    }
}
```

Enable:
```bash
sudo ln -s /etc/nginx/sites-available/bridge /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 📡 API Endpoints

### Health Check

```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "environment": "production",
  "redis": "connected",
  "algolab_api_url": "https://www.algolab.com.tr/api"
}
```

### Authentication

#### 1. Login (Request SMS)

```bash
POST /bridge/login
Authorization: Bearer {railway_jwt_token}
Content-Type: application/json

{
  "api_key": "APIKEY-xyz==",
  "username": "12345678901",
  "password": "user_password"
}
```

Response:
```json
{
  "success": true,
  "temp_token": "Ys/WhU/D37vO71VIBumDRh...",
  "message": "SMS kodu telefon numaranıza gönderildi"
}
```

#### 2. Verify SMS

```bash
POST /bridge/verify-sms
Authorization: Bearer {railway_jwt_token}
Content-Type: application/json

{
  "api_key": "APIKEY-xyz==",
  "temp_token": "Ys/WhU/D37vO71VIBumDRh...",
  "sms_code": "123456"
}
```

Response:
```json
{
  "success": true,
  "session_id": "a1b2c3d4-...",
  "hash": "eyJhbGciOiJodHRwOi8vd3d3...",
  "expires_at": "2025-12-01T18:00:00Z",
  "message": "Algolab oturumu başarıyla oluşturuldu"
}
```

#### 3. Refresh Session

```bash
POST /bridge/refresh-session
Authorization: Bearer {railway_jwt_token}
Content-Type: application/json

{
  "session_id": "a1b2c3d4-..."
}
```

### Trading

#### Send Order

```bash
POST /bridge/send-order
Authorization: Bearer {railway_jwt_token}
Content-Type: application/json

{
  "session_id": "a1b2c3d4-...",
  "symbol": "ASELS",
  "direction": "BUY",
  "pricetype": "limit",
  "price": "45.50",
  "lot": "100",
  "sms": false,
  "email": false,
  "subaccount": ""
}
```

#### Delete Order

```bash
POST /bridge/delete-order
Authorization: Bearer {railway_jwt_token}
Content-Type: application/json

{
  "session_id": "a1b2c3d4-...",
  "order_id": "001VEV",
  "subaccount": ""
}
```

#### Modify Order

```bash
POST /bridge/modify-order
Authorization: Bearer {railway_jwt_token}
Content-Type: application/json

{
  "session_id": "a1b2c3d4-...",
  "order_id": "001VEV",
  "price": "45.75",
  "lot": "200",
  "viop": false,
  "subaccount": ""
}
```

### Portfolio

#### Get Portfolio

```bash
POST /bridge/portfolio
Authorization: Bearer {railway_jwt_token}
Content-Type: application/json

{
  "session_id": "a1b2c3d4-...",
  "subaccount": ""
}
```

#### Get Cash Flow

```bash
POST /bridge/cash-flow
Authorization: Bearer {railway_jwt_token}
Content-Type: application/json

{
  "session_id": "a1b2c3d4-...",
  "subaccount": ""
}
```

#### Get Equity Info

```bash
POST /bridge/equity-info
Authorization: Bearer {railway_jwt_token}
Content-Type: application/json

{
  "session_id": "a1b2c3d4-...",
  "symbol": "ASELS"
}
```

---

## 🔐 Security

### Railway Authentication

The bridge uses JWT tokens for Railway authentication:

**Railway Backend (Python):**
```python
import jwt
from datetime import datetime, timedelta

def create_bridge_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
        "iss": "railway_backend"
    }
    return jwt.encode(payload, BRIDGE_JWT_SECRET, algorithm="HS256")

# Use in requests
token = create_bridge_token("user_123")
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(f"{BRIDGE_URL}/bridge/login", json=payload, headers=headers)
```

### Best Practices

1. **Keep JWT secret safe** - Store in environment variables, never commit
2. **Use HTTPS** - Always use SSL/TLS in production
3. **Rotate secrets** - Change JWT secret periodically
4. **Monitor logs** - Watch for authentication failures
5. **IP Whitelisting** - Optional: restrict to Railway IPs

---

## 🧪 Testing

### Run Tests

```bash
pytest tests/ -v
```

### Manual Testing

```bash
# Health check
curl http://localhost:8000/health

# Test crypto module
python -m app.crypto_utils

# Test session manager (requires Redis)
python -m app.session_manager
```

---

## 📊 Monitoring

### Logs

Structured JSON logs to stdout:
```bash
# View logs
sudo journalctl -u algolab-bridge -f

# Filter errors
sudo journalctl -u algolab-bridge -p err
```

### Metrics

Key metrics to monitor:
- Request latency
- Rate limit violations (429 errors)
- Session expiration rate
- Redis connection status

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Redis Connection Failed

```bash
# Check Redis status
sudo systemctl status redis

# Test connection
redis-cli ping  # Should return "PONG"
```

#### 2. Rate Limit Errors (429)

- Check `MIN_REQUEST_INTERVAL_SECONDS` in .env (default 5.0)
- Verify no concurrent requests from same user
- Check logs for rate limiter violations

#### 3. Session Expired

- Sessions expire after 1 hour by default
- Call `/bridge/refresh-session` periodically (every 10 minutes recommended)
- Check Redis TTL: `redis-cli TTL algolab_session:{session_id}`

#### 4. Authentication Failures

- Verify JWT secret matches between Railway and Bridge
- Check token expiration time
- Validate token issuer is "railway_backend"

---

## 📝 Development

### Project Structure

```
bridge_server/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings
│   ├── crypto_utils.py      # AES + SHA256
│   ├── algolab_client.py    # Algolab API client
│   ├── session_manager.py   # Redis sessions
│   ├── auth.py              # Railway JWT auth
│   └── routes.py            # API endpoints
├── tests/
│   ├── __init__.py
│   ├── test_crypto.py
│   └── test_routes.py
├── requirements.txt
├── .env.example
├── README.md
└── Dockerfile
```

### Adding New Endpoints

1. Add endpoint to `algolab_client.py`
2. Add route to `routes.py`
3. Add request/response models
4. Test endpoint

---

## 📄 License

Internal use only - Trader Eidos Suite

---

## 🤝 Support

For issues or questions:
- Check logs: `sudo journalctl -u algolab-bridge -f`
- Review roadmap: `backend/ROADMAP_ALGOLAB_BRIDGE_V1.md`
- Contact: [Your Contact Info]

---

**Last Updated:** 2025-12-01
**Status:** ✅ Phase 1 MVP Complete
