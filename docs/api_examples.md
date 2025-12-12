# API Examples — ISD-v1.0

Base URL (development): `http://127.0.0.1:5000`

## Signup (form)

```bash
curl -X POST http://127.0.0.1:5000/signup \
  -F "username=alice" \
  -F "password=secret123" \
  -F "owner_name=Alice Smith" \
  -F "email=alice@example.com"
```

## Login (form)

```bash
curl -X POST http://127.0.0.1:5000/login \
  -F "username=alice" \
  -F "password=secret123" \
  -c cookiejar.txt
```

The `-c cookiejar.txt` option saves session cookies for subsequent authenticated requests.

## Book appointment (authenticated)

```bash
curl -X POST http://127.0.0.1:5000/book \
  -b cookiejar.txt \
  -F "car_plate=ABC-123" \
  -F "car_model=Toyota Corolla" \
  -F "car_year=2016" \
  -F "service_id=1" \
  -F "date=2025-12-20" \
  -F "time=09:30"
```

## Get mechanic recent activity (mechanic auth required)

```bash
curl "http://127.0.0.1:5000/mechanic/api/recent-activity?limit=8&offset=0" \
  -H "Authorization: Bearer <MECHANIC_TOKEN>"
```

## Complete service (JSON)

```bash
curl -X POST http://127.0.0.1:5000/mechanic/api/complete-service \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <MECHANIC_TOKEN>" \
  -d '{"appointment_id": 42, "notes": "Replaced brake pads", "status": "completed"}'
```

## Generate PDF (example)

If the project exposes a PDF generation endpoint that accepts CV/appointment data (adjust endpoint & payload accordingly):

```bash
curl -X POST http://127.0.0.1:5000/api/generate_pdf \
  -H "Content-Type: application/json" \
  -d '{"template": "default", "data": {"owner_name": "Alice Smith", "appointments": []}}' --output cv.pdf
```

Notes:
- Replace `Authorization` header values with valid tokens when using token-based auth.
- If the app uses session cookies, use `-c` and `-b` curl options to save/send cookies.
- Check `routes/` for exact parameter names the endpoints expect.
