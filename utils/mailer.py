from __future__ import annotations

import smtplib
from email.mime.text import MIMEText


class MailerError(RuntimeError):
    pass


def send_otp_email(
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    from_name: str,
    to_email: str,
    otp_code: str,
    full_name: str,
) -> None:
    if not to_email or "@" not in to_email:
        raise MailerError("Email không hợp lệ hoặc không tồn tại trong hệ thống.")

    subject = "USCC - Mã xác thực OTP"
    body = (
        f"Xin chào {full_name},\n\n"
        f"Mã OTP xác thực server Discord USCC của bạn là: {otp_code}\n\n"
        "Mã có hiệu lực trong vài phút. Nếu bạn không yêu cầu mã này, hãy bỏ qua email.\n"
    )

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{smtp_user}>" if from_name else smtp_user
    msg["To"] = to_email

    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        try:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to_email], msg.as_string())
        finally:
            try:
                server.quit()
            except Exception:
                pass
    except Exception as exc:
        print(f"[GAuth] SMTP Error: {type(exc).__name__}: {exc}")
        raise MailerError(f"Gửi OTP thất bại: {exc}")
