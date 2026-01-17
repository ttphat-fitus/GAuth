# GAuth

A Discord bot for verifying club members via email-based One-Time Password (OTP) authentication.

## Features

- **Email Verification**: Members verify their identity by entering their student ID or email
- **OTP Authentication**: Secure verification using one-time passwords sent to registered email addresses
- **Database Integration**: Maintains a CSV database of verified members
- **Role Assignment**: Automatically assigns verified roles to authenticated members
- **Attempt Tracking**: Limits verification attempts to prevent abuse
- **Verification Logging**: Tracks successful verifications with timestamps

## Requirements

- Python 3.8+
- Discord.py 2.3.2+
- python-dotenv 1.0.1+
- pandas 2.2.0+

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with the following variables:
   ```
   DISCORD_TOKEN=your_bot_token
   VERIFIED_ROLE_ID=role_id_for_verified_members
   MAIL_SMTP_HOST=smtp.gmail.com
   MAIL_SMTP_PORT=587
   MAIL_SMTP_USER=your_email@gmail.com
   MAIL_SMTP_PASS=your_app_password
   MAIL_FROM_NAME=Your Club Name
   OTP_TTL_SECONDS=600
   MAX_VERIFICATION_ATTEMPTS=3
   ENABLE_MEMBERS_INTENT=true
   ```

## Usage

Run the bot:
```bash
python main.py
```

### Verification Process

1. User clicks the verification button in Discord
2. Enters their student ID or registered email
3. Receives a 6-digit OTP via email
4. Enters the OTP to complete verification
5. Receives the verified role and can access restricted channels

## Configuration

- **OTP_TTL_SECONDS**: How long an OTP code remains valid (default: 600 seconds)
- **MAX_VERIFICATION_ATTEMPTS**: Maximum OTP entry attempts per verification request (default: 3)
- **ENABLE_MEMBERS_INTENT**: Enable Discord members intent for role assignment

## Project Structure

```
GAuth/
├── main.py                 # Bot entry point
├── requirements.txt        # Python dependencies
├── .env                    # Configuration (not in repo)
├── cogs/
│   ├── verification.py    # Verification logic and commands
│   └── __init__.py
├── utils/
│   ├── db_handler.py      # CSV database operations
│   ├── mailer.py          # Email sending
│   ├── otp_store.py       # OTP storage and expiry
│   ├── verification_log.py # Verification logging
│   └── name_utils.py      # Member name utilities
├── database/
│   └── Data.csv           # Member database
└── logs/
    └── verification_success.jsonl # Verification history
```