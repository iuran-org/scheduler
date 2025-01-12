# Scheduler

## fitur
 - API Create, Read, Update, Delete Job
 - Timezone Support, Otomatis Konversi waktu ke timezone yang diinginkan
 - Presist Job (Postgre)
 - Async Job Eksekusi
 - Async Circuit Breaker
 - Health Check
 - Circuit Breaker
 - Testing Endpoint  (Dev Purposes)

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
uvicorn main:app --reload --port 8008 --host 0.0.0.0 --workers 4
```

## Docker
```bash
docker compose up --build -d 
```

## API Docs
```
http://localhost:8008/docs
```

## Sample Request

```
http://localhost:8008/jobs/interval
```

### 1. Harian (Setiap hari jam 8 pagi):

```

{
  "days": 1,
  "start_date": "2024-01-20T08:00:00",
  "callback_url": "http://example.com/daily",
  "payload": {
    "type": "daily_job",
    "time": "08:00"
  },
  "timezone": "GMT+7"
}
```

#### 2.Mingguan (Setiap Senin jam 9 pagi):

```
{
  "weeks": 1,
  "start_date": "2024-01-22T09:00:00",  // Pastikan ini hari Senin
  "callback_url": "http://example.com/weekly",
  "payload": {
    "type": "weekly_job",
    "day": "Monday"
  },
  "timezone": "GMT+7"
}
```

#### 3. Tahunan (Setiap 1 Januari jam 00:00):
```
{
  "days": 365,  // atau 366 untuk tahun kabisat
  "start_date": "2024-01-01T00:00:00",
  "callback_url": "http://example.com/yearly",
  "payload": {
    "type": "yearly_job",
    "event": "new_year"
  },
  "timezone": "GMT+7"
}
```

#### Variasi lain:

Setiap 2 jam:
```
{
  "hours": 2,
  "callback_url": "http://example.com/every-2-hours",
  "payload": {
    "type": "hourly_job"
  },
  "timezone": "GMT+7"
}
```

Setiap 30 menit:
```
{
  "minutes": 30,
  "callback_url": "http://example.com/every-30-min",
  "payload": {
    "type": "frequent_job"
  },
  "timezone": "GMT+7"
}
```

Setiap 2 minggu pada hari Jumat jam 3 sore:
```
{
  "minutes": 30,
  "callback_url": "http://example.com/every-30-min",
  "payload": {
    "type": "frequent_job"
  },
  "timezone": "GMT+7"
}
```


## Catatan

## Circuit Breaker dengan PyBreaker

PyBreaker mengimplementasikan pola Circuit Breaker untuk menangani kegagalan sistem:

### Cara Kerja:
- **Closed (Normal)**: Sistem berjalan normal, request diteruskan
- **Open**: Setelah beberapa kegagalan, circuit terbuka dan request langsung ditolak
- **Half-Open**: Setelah waktu timeout, circuit membuka sebagian untuk test koneksi

### Konfigurasi Dasar:
```python
breaker = CircuitBreaker(
    fail_max=5,           # Jumlah kegagalan sebelum circuit open
    reset_timeout=60,     # Waktu tunggu sebelum half-open (detik)
    exclude=[ValueError]  # Error yang tidak dihitung sebagai kegagalan
)
```

### Penggunaan:
```python
@breaker
def call_external_service():
    # Kode untuk memanggil service eksternal
    pass
```


### ENV

```

DB_USER=
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432
DB_NAME=scheduler
MISFIRE_GRACE_TIME=900 // 15 minutes

PORT_EXPOSE=8009

```