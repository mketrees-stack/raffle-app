
Raffle App (Referral + Weighted Tickets) - Local Flask Demo
Files created in this folder.

How it works:
- Users visit / (optionally with ?ref=CODE)
- Sign up with phone and instagram handle (name optional)
- Each signup creates a referral_code for that user
- If a new signup uses ?ref=CODE (or form field), the referring user's tickets increment by +1
- Each entrant starts with 1 ticket, plus bonus tickets from referrals
- Admin POST /admin/draw?key=YOUR_KEY will run a weighted draw (3 winners) and save winners to meta
- Admin GET /admin/winners?key=YOUR_KEY returns winners

Run locally:
1. Install Python 3.8+ and pip
2. cd raffle_app
3. pip install -r requirements.txt
4. export RAFFLE_ADMIN_KEY=some_secret_key   (or set in Windows)
5. python app.py
6. Visit http://127.0.0.1:5000/    (change end time via /admin/set_end POST with JSON {"end_time":"2025-11-10T20:00:00"})

Notes:
- This is a demo. For production:
  - Use HTTPS and a proper host
  - Rate-limit signups and add CAPTCHA to prevent abuse
  - Validate and sanitize phone/instagram input
  - Implement duplicate prevention and verify phone ownership (SMS)
  - Store environment secrets safely
  - Add logging and backups for the database
