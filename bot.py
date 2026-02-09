import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import os, asyncio
from dotenv import load_dotenv

load_dotenv()

# ---------- CONFIG ----------
SUPPORT_ROLE_ID = 1467374470221136067
TICKET_CATEGORY = "Tickets"

MM_TIERS = {
    "0-150m": {"role": 1467374476537893063, "rank": 1},
    "0-300m": {"role": 1467374475724067019, "rank": 2},
    "0-500m": {"role": 1467374474671423620, "rank": 3},
    "0-1b":   {"role": 1467374473723252746, "rank": 4},
}

# ---------- BOT ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="$", intents=intents)

def is_support(member):
    return any(r.id == SUPPORT_ROLE_ID for r in member.roles)

def get_mm_rank(member):
    for tier in MM_TIERS.values():
        if any(r.id == tier["role"] for r in member.roles):
            return tier["rank"]
    return 0

# ---------- TRADE MODAL ----------
class TradeTicketModal(Modal, title="📝 Trade Ticket Form"):
    def __init__(self, tier):
        super().__init__()
        self.tier = tier

    trader = TextInput(label="Trader Username / ID")
    giving = TextInput(label="What are YOU giving?")
    receiving = TextInput(label="What are THEY giving?")
    fee = TextInput(label="MM fee")

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY)
        if not category:
            category = await guild.create_category(TICKET_CATEGORY)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        # allow staff to SEE but not claim
        support_role = guild.get_role(SUPPORT_ROLE_ID)
        overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        # allow all MM roles to SEE (claim logic handled later)
        for tier_data in MM_TIERS.values():
            role = guild.get_role(tier_data["role"])
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"trade-{self.tier}-{interaction.user.id}",
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(title="📌 Trade Ticket", color=discord.Color.green())
        embed.add_field(name="Tier", value=f"Middleman {self.tier}", inline=False)
        embed.add_field(name="Trader", value=self.trader.value, inline=False)
        embed.add_field(name="Giving", value=self.giving.value, inline=False)
        embed.add_field(name="Receiving", value=self.receiving.value, inline=False)
        embed.add_field(name="Fee", value=self.fee.value, inline=False)

        await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=TicketButtons(self.tier)
        )

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )

# ---------- BUTTONS ----------
class TicketButtons(View):
    def __init__(self, tier):
        super().__init__(timeout=None)
        self.tier = tier
        self.claimed_by = None

    @discord.ui.button(label="🎯 Claim", style=discord.ButtonStyle.green, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: Button):
        if is_support(interaction.user):
            return await interaction.response.send_message(
                "❌ Staff cannot claim trade tickets.",
                ephemeral=True
            )

        required_rank = MM_TIERS[self.tier]["rank"]
        user_rank = get_mm_rank(interaction.user)

        if user_rank < required_rank:
            return await interaction.response.send_message(
                "❌ Your middleman tier is too low to claim this ticket.",
                ephemeral=True
            )

        if self.claimed_by:
            return await interaction.response.send_message(
                f"Already claimed by {self.claimed_by.mention}",
                ephemeral=True
            )

        self.claimed_by = interaction.user
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.channel.edit(name=f"claimed-{interaction.user.name}")
        await interaction.response.send_message(
            f"🎯 {interaction.user.mention} claimed this ticket."
        )

    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.red, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: Button):
        if not is_support(interaction.user) and interaction.user != self.claimed_by:
            return await interaction.response.send_message(
                "❌ Only staff or the claimer can close this ticket.",
                ephemeral=True
            )
        await interaction.response.send_message("Closing...", ephemeral=True)
        await asyncio.sleep(1)
        await interaction.channel.delete()

# ---------- PANEL ----------
class TradeSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Choose middleman tier...",
            min_values=1,
            max_values=1,
            custom_id="trade_select",
            options=[
                discord.SelectOption(label="Middleman (0-150m)", value="0-150m"),
                discord.SelectOption(label="Middleman (0-300m)", value="0-300m"),
                discord.SelectOption(label="Middleman (0-500m)", value="0-500m"),
                discord.SelectOption(label="Middleman (0-1b)", value="0-1b"),
            ]
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            TradeTicketModal(self.values[0])
        )

class TradePanel(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TradeSelect())

# ---------- COMMANDS ----------
@bot.command()
async def ticketpanel(ctx):
    if not is_support(ctx.author):
        return await ctx.send("❌ Support only.")
    embed = discord.Embed(
        title="🎯 Trade Panel",
        description="Select a middleman tier to open a trade ticket.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=TradePanel())

@bot.command()
async def mminfo(ctx):
    embed = discord.Embed(
        title="📘 Middleman Tier Info",
        description=(
            "**How claiming works:**\n"
            "• You can claim your tier **and any lower tier**\n"
            "• Staff cannot claim trade tickets\n\n"
            "**Tiers:**\n"
            "0–150m → Entry MM\n"
            "0–300m → Experienced MM\n"
            "0–500m → Senior MM\n"
            "0–1b → Elite MM"
        ),
        color=discord.Color.gold()
    )

    embed.set_image(
        url="https://i.imgur.com/8Km9tLL.png"  # replace with your own image anytime
    )

    await ctx.send(embed=embed)

# ---------- ERRORS ----------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

# ---------- READY ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    bot.add_view(TradePanel())
    print("✅ Persistent views loaded")

# ---------- RUN ----------
bot.run(os.getenv("TOKEN"))
