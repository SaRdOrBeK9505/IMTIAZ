# IMTIAZ — Auth API Documentation

Frontend dasturchilarga mo'ljallangan to'liq autentifikatsiya qo'llanmasi.

---

## Umumiy qoidalar

**Base URL:** `https://api.imtiaz.uz/api`  
**Content-Type:** `application/json`  
**Autentifikatsiya:** `Authorization: Bearer <access_token>`

### Javob formati

Muvaffaqiyatli javob:
```json
{ "success": true, ... }
```

Xato javob:
```json
{ "success": false, "code": 400, "message": "...", "errors": { ... } }
```

### Token saqlash

| Client | Token saqlash joyi |
|--------|-------------------|
| Telegram Mini App | JS xotirasi (localStorage EMAS) |
| Flutter Mobile | Flutter Secure Storage |
| CRM (React/Vue) | JS xotirasi (Zustand/Redux state) |

> ⚠️ `localStorage` ishlatmang — XSS xavfi bor.

---

## 1. Ro'yxatdan o'tish (Telegram Mini App)

### Oqim sxemasi

```
[1] full_name + phone  →  OTP SMS yuboriladi
[2] phone + otp_code   →  verification_token (15 daqiqa)
[3] token + password   →  User yaratiladi + JWT (avtomatik login)
[4] keyingi kirish     →  phone + password  →  JWT
```

---

### Qadam 1 — OTP so'rash

```
POST /auth/register/request-otp/
```

**Request:**
```json
{
  "full_name": "Asilbek Karimov",
  "phone_number": "+998901234567"
}
```

**Response 200:**
```json
{
  "detail": "OTP yuborildi",
  "expires_in": 300
}
```

**Xatolar:**

| Kod | Sabab |
|-----|-------|
| 400 | Raqam allaqachon ro'yxatdan o'tgan |
| 400 | Telefon format noto'g'ri (format: +998XXXXXXXXX) |
| 400 | full_name kamida 2 so'z bo'lishi kerak |
| 429 | 60 soniyada 1 ta SMS (rate limit) |
| 503 | SMS gateway xato |

---

### Qadam 2 — OTP tasdiqlash

```
POST /auth/register/verify-otp/
```

**Request:**
```json
{
  "phone_number": "+998901234567",
  "otp_code": "123456"
}
```

**Response 200:**
```json
{
  "verification_token": "OTk4OTA6MTc1Mz...:abc123..."
}
```

> Token 15 daqiqa amal qiladi. Keyingi qadamda shu tokenni yuboring.

**Xatolar:**

| Kod | Sabab |
|-----|-------|
| 400 | Noto'g'ri kod |
| 400 | OTP muddati o'tgan (5 daqiqa) |
| 400 | 5 ta urinishdan ortiq (brute-force) |
| 400 | OTP topilmadi (qayta so'rang) |

---

### Qadam 3 — Ro'yxatdan o'tishni yakunlash

```
POST /auth/register/complete/
```

**Request:**
```json
{
  "verification_token": "OTk4OTA6MTc1Mz...:abc123...",
  "password": "Qwerty123!",
  "telegram_init_data": "query_id=...&user=...&hash=..."
}
```

> `telegram_init_data` — **ixtiyoriy**.  
> Telegram Mini App'dan: `window.Telegram.WebApp.initData`  
> Agar kelsa: HMAC tekshiriladi, `telegram_id` user ga bog'lanadi.  
> Kelmasa: faqat `phone + password` bilan user yaratiladi.

**JavaScript (Telegram Mini App):**
```javascript
const initData = window.Telegram.WebApp.initData; // string

const response = await fetch('/api/auth/register/complete/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    verification_token: token,   // qadam 2 dan kelgan
    password: password,
    telegram_init_data: initData,
  }),
});
```

**Response 201:**
```json
{
  "success": true,
  "is_new_user": true,
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "uuid",
    "phone": "+998901234567",
    "is_phone_verified": true,
    "role": "customer",
    "first_name": "Asilbek",
    "last_name": "Karimov",
    "telegram_id": 123456789,
    "balance": "0.00",
    "bonus_points": 0,
    "created_at": "2026-08-08T..."
  }
}
```

**Xatolar:**

| Kod | Sabab |
|-----|-------|
| 400 | Token muddati o'tgan (15 daqiqa) |
| 400 | Noto'g'ri token |
| 400 | Register ma'lumotlari topilmadi (qaytadan boshlang) |
| 400 | Parol juda oddiy (Django validators) |
| 400 | Bu Telegram akkaunt boshqa userga bog'langan |

---

## 2. Kirish (Login)

### 2.1 Customer login (Telegram Mini App / Flutter)

```
POST /auth/login/
```

**Request:**
```json
{
  "phone": "+998901234567",
  "password": "Qwerty123!"
}
```

**Response 200:**
```json
{
  "success": true,
  "access": "eyJ...",
  "refresh": "eyJ...",
  "user": { ... }
}
```

> Token ichidagi claims: `{ "aud": "mobile", "role": "customer", "user_id": "uuid" }`

---

### 2.2 CRM login (Owner / Branch Staff)

```
POST /crm/auth/login/
```

**Request va Response** — yuqoridagi bilan bir xil.

> Token: `{ "aud": "crm", "role": "owner" | "branch_staff" }`  
> Customer roli bu endpoint orqali kira olmaydi → **400**

---

### 2.3 Admin login

```
POST /admin/auth/login/
```

> Token: `{ "aud": "admin", "role": "admin" }`  
> Faqat `role=admin` kiradi.

---

## 3. Token boshqaruvi

### Token yangilash

```
POST /auth/token/refresh/
```

**Request:**
```json
{ "refresh": "eyJ..." }
```

**Response 200:**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

> `ROTATE_REFRESH_TOKENS=True` — har yangilanishda eski refresh blacklist ga tushadi,  
> yangi refresh qaytariladi. Yangi refresh tokenni saqlashni unutmang!

### Access token muddati tugaganda

```javascript
// Axios interceptor misoli
axios.interceptors.response.use(
  res => res,
  async error => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      const { data } = await axios.post('/api/auth/token/refresh/', {
        refresh: getStoredRefreshToken(),
      });
      setStoredTokens(data.access, data.refresh); // yangi refresh ham saqlash
      error.config.headers.Authorization = `Bearer ${data.access}`;
      return axios(error.config);
    }
    return Promise.reject(error);
  }
);
```

---

### Chiqish (Logout)

```
POST /auth/logout/
Authorization: Bearer <access_token>
```

**Request:**
```json
{ "refresh": "eyJ..." }
```

**Response 200:**
```json
{ "success": true, "detail": "Muvaffaqiyatli chiqildi." }
```

> Logout qilgandan so'ng saqlangan `access` va `refresh` tokenlarni o'chiring.

---

## 4. Profil

### Profilni olish

```
GET /users/me/
Authorization: Bearer <access_token>
```

**Response 200:**
```json
{
  "id": "uuid",
  "phone": "+998901234567",
  "is_phone_verified": true,
  "role": "customer",
  "first_name": "Asilbek",
  "last_name": "Karimov",
  "full_name": "Asilbek Karimov",
  "telegram_id": 123456789,
  "telegram_username": "asilbek",
  "avatar_url": null,
  "language_code": "uz",
  "ai_autonomy_level": "manual",
  "ai_auto_price_limit": "500000.00",
  "balance": "0.00",
  "bonus_points": 0,
  "membership_tier_name": null,
  "waitlist_status": "not_applied",
  "effective_ai_autonomy": "manual",
  "created_at": "2026-08-08T..."
}
```

### Profilni yangilash

```
PATCH /users/me/
Authorization: Bearer <access_token>
```

**Request (faqat o'zgartiriladigan maydonlar):**
```json
{
  "first_name": "Asilbek",
  "last_name": "Karimov",
  "avatar_url": "https://...",
  "language_code": "uz"
}
```

> Read-only maydonlar: `id`, `telegram_id`, `role`, `balance`, `bonus_points`, `is_phone_verified`

---

## 5. Xavfsizlik

### JWT Audience tizimi

Har bir panel uchun alohida token audience:

| Panel | Endpoint prefix | Token `aud` |
|-------|----------------|-------------|
| Telegram Mini App / Flutter | `/api/auth/...` | `mobile` |
| CRM | `/api/crm/...` | `crm` |
| Admin | `/api/admin/...` | `admin` |

**Muhim:** Customer tokeni (`aud=mobile`) CRM endpointlariga kirishga urinsa → **401 AuthenticationFailed**.

### Token muddatlari

| Token | Muddat |
|-------|--------|
| Access | 15 daqiqa |
| Refresh | 30 kun |

---

## 6. Xato kodlari

| HTTP | Ma'no |
|------|-------|
| 400 | Validatsiya xatosi yoki noto'g'ri ma'lumot |
| 401 | Token yo'q, noto'g'ri yoki muddati o'tgan |
| 403 | Ruxsat yo'q |
| 429 | So'rovlar juda ko'p (rate limit) |
| 503 | Tashqi xizmat (SMS gateway) ishlamayapti |

---

## 7. To'liq oqim (Flutter / Telegram Mini App)

```
Ilovani ochish
    ↓
Saqlangan token bormi?
    ├─ Ha → Token yangilash (refresh)
    │         ├─ Muvaffaqiyatli → Bosh sahifa
    │         └─ Xato (refresh ham o'tgan) → Login sahifasi
    │
    └─ Yo'q → Login sahifasi
                 ├─ Ro'yxatdan o'tish tugmasi
                 │    ├─ [1] full_name + phone → OTP so'rov
                 │    ├─ [2] OTP kiritish → verification_token
                 │    ├─ [3] parol + initData → User + JWT
                 │    └─ Bosh sahifa
                 │
                 └─ Kirish (mavjud user)
                      └─ phone + password → JWT → Bosh sahifa
```
