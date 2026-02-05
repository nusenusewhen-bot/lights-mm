import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import os
from dotenv import load_dotenv

load_dotenv()

# ---------- CONFIG ----------
TICKET_CATEGORY = "Tickets"

MIDDLEMAN_ROLE_ID = 1467374476537893063
SUPPORT_ROLE_ID = 1467374470221136067

PANEL_ALLOWED_ROLES = ["Founder", "Secondary Owner", "Management"]
BAN_ALLOWED_ROLES = ["Moderator", "Management", "Secondary Owner", "Founder"]

# ---------- BOT ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="$", intents=intents)

# ---------- HELPERS ----------
def has_role(member: discord.Member, role_id: int):
    return any(role.id == role_id for role in member.roles)

def highest_role(member: discord.Member):
    return max((r.position for r in member.roles), default=0)

# ---------- MODAL ----------
class TradeTicketModal(Modal, title="Trade Ticket"):
    trader = TextInput(label="Trader Username / ID")
    giving = TextInput(label="What are YOU giving?")
    receiving = TextInput(label="What are THEY giving?")
    fee = TextInput(label="MM Fee")

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY)
        if not category:
            category = await guild.create_category(TICKET_CATEGORY)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        mm_role = guild.get_role(MIDDLEMAN_ROLE_ID)
        if mm_role:
            overwrites[mm_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"trade-{interaction.user.id}",
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(title="📌 Trade Ticket", color=discord.Color.green())
        embed.add_field(name="Trader", value=self.trader.value, inline=False)
        embed.add_field(name="Giving", value=self.giving.value, inline=False)
        embed.add_field(name="Receiving", value=self.receiving.value, inline=False)
        embed.add_field(name="Fee", value=self.fee.value, inline=False)

        await channel.send(
            content=f"{interaction.user.mention} <@&{MIDDLEMAN_ROLE_ID}>",
            embed=embed,
            view=CloseTicketView()
        )

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )

# ---------- CLOSE BUTTON ----------
class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.red,
        custom_id="close_ticket"
    )
    async def close(self, interaction: discord.Interaction, button: Button):
        if not (
            has_role(interaction.user, MIDDLEMAN_ROLE_ID)
            or has_role(interaction.user, SUPPORT_ROLE_ID)
        ):
            return await interaction.response.send_message(
                "❌ No permission.",
                ephemeral=True
            )

        await interaction.response.send_message("Closing...", ephemeral=True)
        await interaction.channel.delete()

# ---------- PANEL ----------
class TradePanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Trade Ticket",
        style=discord.ButtonStyle.green,
        custom_id="open_trade_ticket"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(TradeTicketModal())

# ---------- PREFIX COMMAND ----------
@bot.command()
async def shop(ctx):
    embed = discord.Embed(
        title="🛒 Shop",
        description="Products coming soon.",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

# ---------- SLASH COMMANDS ----------
@bot.tree.command(name="ban")
@app_commands.describe(member="Member to ban", reason="Reason")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    if not any(r.name in BAN_ALLOWED_ROLES for r in interaction.user.roles):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    if highest_role(member) >= highest_role(interaction.user):
        return await interaction.response.send_message("❌ Role hierarchy.", ephemeral=True)

    await member.ban(reason=reason)
    await interaction.response.send_message(f"✅ Banned {member} | {reason}")

@bot.tree.command(name="unban")
@app_commands.describe(user_id="User ID to unban")
async def unban(interaction: discord.Interaction, user_id: str):
    if not any(r.name in BAN_ALLOWED_ROLES for r in interaction.user.roles):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    user_id = int(user_id)
    bans = await interaction.guild.bans()

    for ban in bans:
        if ban.user.id == user_id:
            await interaction.guild.unban(ban.user)

            invite = await interaction.channel.create_invite(
                max_uses=1,
                max_age=300,
                unique=True
            )

            return await interaction.response.send_message(
                f"✅ Unbanned **{ban.user}**\n🔗 Invite: {invite.url}",
                ephemeral=True
            )

    await interaction.response.send_message("❌ User not banned.", ephemeral=True)

# ---------- EVENTS ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    bot.add_view(TradePanelView())
    bot.add_view(CloseTicketView())

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print("Sync error:", e)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

# ---------- RUN ----------
bot.run(os.getenv("TOKEN"))
