import discord
from discord import app_commands
from discord.ext import commands

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="post", description="Post a message to a channel as the bot")
    @app_commands.describe(
        channel="The channel to post the message to",
        content="The message to post (or use attachment)",
        attachment="An optional file to post (e.g., .md, .txt) - content will be read if text-based"
    )
    @app_commands.choices(channel=[
        app_commands.Choice(name="announcement", value="1448683191169712229"),
        app_commands.Choice(name="📣・announcement", value="1466415513969365208")
    ])
    async def post(
        self,
        interaction: discord.Interaction,
        channel: str,
        content: str = None,
        attachment: discord.Attachment = None,
    ) -> None:
        ALLOWED_ROLE_ID = 1448687309233979631
        has_role = any(role.id == ALLOWED_ROLE_ID for role in interaction.user.roles)
        
        if not has_role and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Bạn không có quyền sử dụng lệnh này (Yêu cầu Role cụ thể).", ephemeral=True)
            
        target_channel = interaction.guild.get_channel(int(channel))
        if target_channel is None:
            return await interaction.response.send_message("Channel not found in this server.", ephemeral=True)

        if content:
            content = content.replace('\\n', '\n')

        if content is None and attachment is None:
            return await interaction.response.send_message("Please provide either content or an attachment.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        try:
            kwargs = {}
            if attachment is not None:
                if attachment.filename.endswith(('.md', '.txt')):
                    file_content = await attachment.read()
                    text = file_content.decode('utf-8')
                    if content:
                        content += f"\n\n{text}"
                    else:
                        content = text
                else:
                    kwargs['file'] = await attachment.to_file()
            
            if content:
                for chunk in [content[i:i+2000] for i in range(0, len(content), 2000)]:
                    chunk_kwargs = {}
                    if chunk == content[-len(chunk):] and 'file' in kwargs:
                        chunk_kwargs['file'] = kwargs['file']
                    await target_channel.send(content=chunk, **chunk_kwargs)
            else:
                await target_channel.send(**kwargs)

            await interaction.followup.send(f"Successfully posted to {target_channel.mention}")
        except Exception as e:
            await interaction.followup.send(f"Failed to post message: {e}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
