from __future__ import annotations

import asyncio
import os
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils.db_handler import DBHandler
from utils.mailer import MailerError, send_otp_email
from utils.name_utils import build_nickname
from utils.otp_store import OTPStore
from utils.verification_log import VerificationLog


def _env_int(name: str) -> Optional[int]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return int(value)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = raw.strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


class AttemptTracker:
    def __init__(self) -> None:
        self._attempts: dict[int, int] = {}

    def increment(self, user_id: int) -> int:
        self._attempts[user_id] = self._attempts.get(user_id, 0) + 1
        return self._attempts[user_id]

    def get(self, user_id: int) -> int:
        return self._attempts.get(user_id, 0)

    def clear(self, user_id: int) -> None:
        self._attempts.pop(user_id, None)


class IdentifierModal(discord.ui.Modal, title="Xác thực thành viên CLB USCC"):
    identifier = discord.ui.TextInput(
        label="MSSV hoặc Email",
        placeholder="MSSV hoặc Email đã đăng ký với USCC",
        required=True,
        max_length=128,
    )

    def __init__(
        self,
        *,
        db: DBHandler,
        otp_store: OTPStore,
        verification_log: VerificationLog,
        attempt_tracker: AttemptTracker,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_pass: str,
        smtp_from_name: str,
        otp_ttl_seconds: int,
        max_attempts: int,
    ) -> None:
        super().__init__(timeout=180)
        self._db = db
        self._otp_store = otp_store
        self._verification_log = verification_log
        self._attempt_tracker = attempt_tracker
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_pass = smtp_pass
        self._smtp_from_name = smtp_from_name
        self._otp_ttl_seconds = otp_ttl_seconds
        self._max_attempts = max_attempts

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # IMPORTANT: Must respond within ~3 seconds or Discord will show
        # "Something went wrong. Try again." even if our work succeeds.
        # Defer early and use followup for the rest.
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
        except Exception:
            # If already responded somehow, continue best-effort.
            pass

        if interaction.user is None:
            await interaction.followup.send("Không xác định được user.", ephemeral=True)
            return

        identifier_input = str(self.identifier.value).strip()

        record = self._db.find_by_identifier(identifier_input)
        if record is None:
            print(f"[GAuth] Record not found for {identifier_input}")
            await interaction.followup.send(
                "Không tìm thấy thông tin. Hãy kiểm tra MSSV/Email.",
                ephemeral=True,
            )
            return
        code = f"{random.randint(0, 999999):06d}"
        self._otp_store.set(
            interaction.user.id,
            code=code,
            email=record.email,
            full_name=record.full_name,
            mssv=record.mssv,
            ttl_seconds=self._otp_ttl_seconds,
        )

        try:
            await asyncio.to_thread(
                send_otp_email,
                smtp_host=self._smtp_host,
                smtp_port=self._smtp_port,
                smtp_user=self._smtp_user,
                smtp_pass=self._smtp_pass,
                from_name=self._smtp_from_name,
                to_email=record.email,
                otp_code=code,
                full_name=record.full_name,
            )
        except MailerError as exc:
            print(f"[GAuth] MailerError: {exc}")
            self._otp_store.clear(interaction.user.id)
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        await interaction.followup.send(
            f"Đã gửi OTP tới email: {record.email}. Bấm nút để nhập OTP.",
            view=EnterOTPView(
                otp_store=self._otp_store,
                verification_log=self._verification_log,
                attempt_tracker=self._attempt_tracker,
                max_attempts=self._max_attempts,
            ),
            ephemeral=True,
        )


class OTPModal(discord.ui.Modal, title="Nhập OTP"):
    otp = discord.ui.TextInput(
        label="Mã OTP (6 số)",
        placeholder="123456",
        required=True,
        min_length=6,
        max_length=6,
    )

    def __init__(
        self,
        *,
        otp_store: OTPStore,
        verification_log: VerificationLog,
        attempt_tracker: AttemptTracker,
        verified_role_id: int,
        max_attempts: int,
    ) -> None:
        super().__init__(timeout=180)
        self._otp_store = otp_store
        self._verification_log = verification_log
        self._attempt_tracker = attempt_tracker
        self._verified_role_id = verified_role_id
        self._max_attempts = max_attempts

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
        except Exception:
            pass

        if interaction.user is None or interaction.guild is None:
            await interaction.followup.send("Thiếu context guild/user.", ephemeral=True)
            return

        entry = self._otp_store.get(interaction.user.id)
        if entry is None:
            await interaction.followup.send(
                "OTP đã hết hạn hoặc chưa yêu cầu OTP. Hãy bấm Xác thực lại.",
                ephemeral=True,
            )
            return

        entered = str(self.otp.value).strip()
        current_attempts = self._attempt_tracker.increment(interaction.user.id)

        if entered != entry.code:
            if current_attempts >= self._max_attempts:
                self._verification_log.log_failed_attempts(
                    discord_id=interaction.user.id,
                    discord_username=str(interaction.user),
                    full_name=entry.full_name,
                    mssv=entry.mssv,
                    email=entry.email,
                    reason=f"Vượt quá {self._max_attempts} lần nhập sai OTP",
                )
                self._otp_store.clear(interaction.user.id)
                self._attempt_tracker.clear(interaction.user.id)
                await interaction.followup.send(
                    f"Bạn đã nhập sai OTP quá {self._max_attempts} lần. Tài khoản bị khóa xác thực. Mở ticket để có thể liên hệ hỗ trợ.",
                    ephemeral=True,
                )
                return

            await interaction.followup.send(
                f"Sai mã OTP. Còn {self._max_attempts - current_attempts} lần thử.",
                ephemeral=True,
            )
            return

        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(interaction.user.id)
            except Exception:
                await interaction.followup.send("Không tìm thấy member trong server.", ephemeral=True)
                return

        role = interaction.guild.get_role(self._verified_role_id)
        if role is None:
            await interaction.followup.send("Bot got mistake :(", ephemeral=True)
            return

        # Check if user already verified
        if role in member.roles:
            await interaction.followup.send("Bạn đã được xác thực rồi.", ephemeral=True)
            return

        try:
            if role not in member.roles:
                await member.add_roles(role, reason="USCC verification")
        except discord.Forbidden:
            await interaction.followup.send("Bot không đủ quyền để cấp role.", ephemeral=True)
            return
        except Exception as exc:
            await interaction.followup.send(f"Lỗi khi cấp role: {exc}", ephemeral=True)
            return

        new_nick = None
        try:
            new_nick = build_nickname(entry.full_name)
            if new_nick:
                await member.edit(nick=new_nick, reason="USCC verification")
        except discord.Forbidden:
            pass
        except Exception:
            pass

        self._otp_store.clear(interaction.user.id)
        self._attempt_tracker.clear(interaction.user.id)

        self._verification_log.log_success(
            discord_id=interaction.user.id,
            discord_username=str(interaction.user),
            full_name=entry.full_name,
            mssv=entry.mssv,
            email=entry.email,
        )

        if new_nick:
            await interaction.followup.send(
                f"Xác thực thành công. Chào mừng: {new_nick} đến với server USCC!",
                ephemeral=True,
            )
        else:
            await interaction.followup.send("Xác thực thành công.", ephemeral=True)

        # print(f"[GAuth] Verified user={interaction.user} id={interaction.user.id} mssv={entry.mssv}")


class EnterOTPView(discord.ui.View):
    def __init__(
        self,
        *,
        otp_store: OTPStore,
        verification_log: VerificationLog,
        attempt_tracker: AttemptTracker,
        max_attempts: int,
    ) -> None:
        super().__init__(timeout=300)
        self._otp_store = otp_store
        self._verification_log = verification_log
        self._attempt_tracker = attempt_tracker
        self._max_attempts = max_attempts

    @discord.ui.button(label="Nhập OTP", style=discord.ButtonStyle.primary)
    async def enter_otp(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        cog = interaction.client.get_cog("VerificationCog")
        if cog is None:
            await interaction.response.send_message("Cog chưa sẵn sàng.", ephemeral=True)
            return
        assert isinstance(cog, VerificationCog)

        # if cog.verified_role_id is None:
        #     await interaction.response.send_message("Thiếu VERIFIED_ROLE_ID trong .env.", ephemeral=True)
        #     return

        await interaction.response.send_modal(
            OTPModal(
                otp_store=self._otp_store,
                verification_log=self._verification_log,
                attempt_tracker=self._attempt_tracker,
                verified_role_id=cog.verified_role_id,
                max_attempts=self._max_attempts,
            )
        )


class VerificationView(discord.ui.View):
    def __init__(
        self,
        *,
        db: DBHandler,
        otp_store: OTPStore,
        verification_log: VerificationLog,
        attempt_tracker: AttemptTracker,
        verified_role_id: int,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_pass: str,
        smtp_from_name: str,
        otp_ttl_seconds: int,
        max_attempts: int,
    ) -> None:
        super().__init__(timeout=None)
        self._db = db
        self._otp_store = otp_store
        self._verification_log = verification_log
        self._attempt_tracker = attempt_tracker
        self._verified_role_id = verified_role_id
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_pass = smtp_pass
        self._smtp_from_name = smtp_from_name
        self._otp_ttl_seconds = otp_ttl_seconds
        self._max_attempts = max_attempts

    @discord.ui.button(
        label="💌 Xác thực ngay",
        style=discord.ButtonStyle.success,
        custom_id="uscc_verify_start",
    )
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.guild is not None and interaction.user is not None:
            member = interaction.guild.get_member(interaction.user.id)
            if member is not None and self._verified_role_id in [r.id for r in member.roles]:
                await interaction.response.send_message("Bạn đã được xác thực rồi.", ephemeral=True)
                return

        await interaction.response.send_modal(
            IdentifierModal(
                db=self._db,
                otp_store=self._otp_store,
                verification_log=self._verification_log,
                attempt_tracker=self._attempt_tracker,
                smtp_host=self._smtp_host,
                smtp_port=self._smtp_port,
                smtp_user=self._smtp_user,
                smtp_pass=self._smtp_pass,
                smtp_from_name=self._smtp_from_name,
                otp_ttl_seconds=self._otp_ttl_seconds,
                max_attempts=self._max_attempts,
            )
        )


class VerificationCog(commands.Cog, name="VerificationCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        load_dotenv()

        base_dir = os.path.dirname(os.path.dirname(__file__))
        csv_path = os.path.join(base_dir, "database", "Data.csv")
        self.db = DBHandler(csv_path)
        self.otp_store = OTPStore()
        self.verification_log = VerificationLog(log_dir=os.path.join(base_dir, "logs"))
        self.attempt_tracker = AttemptTracker()

        self.verified_role_id: Optional[int] = None
        self.verification_channel_id: Optional[int] = None

        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_pass = os.getenv("SMTP_PASS", "")
        self.smtp_from_name = os.getenv("SMTP_FROM_NAME", "USCC Auth")
        self.otp_ttl_seconds = int(os.getenv("OTP_EXPIRE_SECONDS", "300"))
        self.max_attempts = int(os.getenv("MAX_OTP_ATTEMPTS", "5"))

        # Persistent view so the button continues working after restart
        self.bot.add_view(VerificationView(
            db=self.db,
            otp_store=self.otp_store,
            verification_log=self.verification_log,
            attempt_tracker=self.attempt_tracker,
            verified_role_id=0,
            smtp_host=self.smtp_host,
            smtp_port=self.smtp_port,
            smtp_user=self.smtp_user,
            smtp_pass=self.smtp_pass,
            smtp_from_name=self.smtp_from_name,
            otp_ttl_seconds=self.otp_ttl_seconds,
            max_attempts=self.max_attempts,
        ))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if self.verification_channel_id is None:
            return

        channel = member.guild.get_channel(self.verification_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            overwrite = channel.overwrites_for(member)
            overwrite.view_channel = True
            overwrite.read_message_history = True
            overwrite.send_messages = False
            await channel.set_permissions(member, overwrite=overwrite, reason="USCC verification access")
        except discord.Forbidden:
            pass
        except Exception:
            pass

    @app_commands.command(name="verify", description="Server Verify Setup")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        verify_channel="Verification channel",
        verified_role="Role for verified members",
        attempts="Maximum number of failed attempts",
    )
    async def verify_setup(
        self,
        interaction: discord.Interaction,
        verify_channel: discord.TextChannel,
        verified_role: discord.Role,
        attempts: int = 5,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Only usable within a server.", ephemeral=True)
            return

        self.verified_role_id = verified_role.id
        self.verification_channel_id = verify_channel.id
        self.max_attempts = max(1, min(attempts, 10))

        await verify_channel.send(
            "Press the button below to start verification.",
            view=VerificationView(
                db=self.db,
                otp_store=self.otp_store,
                verification_log=self.verification_log,
                attempt_tracker=self.attempt_tracker,
                verified_role_id=self.verified_role_id,
                smtp_host=self.smtp_host,
                smtp_port=self.smtp_port,
                smtp_user=self.smtp_user,
                smtp_pass=self.smtp_pass,
                smtp_from_name=self.smtp_from_name,
                otp_ttl_seconds=self.otp_ttl_seconds,
                max_attempts=self.max_attempts,
            ),
        )

        await interaction.response.send_message(
            f"Verification setup successful:\n"
            f"- Channel: {verify_channel.mention}\n"
            f"- Role: {verified_role.mention}\n"
            f"- Max attempts: {self.max_attempts}",
            ephemeral=True,
        )

    @app_commands.command(name="log", description="View verification statistics")
    @app_commands.checks.has_permissions(administrator=True)
    async def view_logs(self, interaction: discord.Interaction) -> None:
        success = self.verification_log.count_success()
        failed = self.verification_log.count_failed()

        embed = discord.Embed(
            title="USCC Verification Statistics",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Verified", value=str(success), inline=True)
        embed.add_field(name="Failed", value=str(failed), inline=True)

        failed_entries = self.verification_log.get_failed_entries(limit=10)
        if failed_entries:
            failed_list = "\n".join(
                [
                    f"{e.get('discord_username', '?')} ({e.get('mssv', '?')}) - {e.get('reason', '?')}"
                    for e in failed_entries
                ]
            )
            embed.add_field(
                name="Recent Failed Attempts (Last 10)",
                value=f"```{failed_list}```",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VerificationCog(bot))
