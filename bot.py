import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import os, json, asyncio
from dotenv import load_dotenv

load_dotenv()

# ---------- CONFIG ----------
SUPPORT_ROLE_ID = 1467374470221136067
TICKET_CATEGORY = "Tickets"
VOUCHES_FILE = "vouches.json"

MM_ROLES = {
    "0-150m": 1467374476537893063,
    "0-300m": 1467374475724067019,
    "0-500m": 1467374474671423620,
    "0-1b":   1467374473723252746,
}

# ---------- DATA ----------
if not os.path.exists(VOUCHES_FILE):
    with open(VOUCHES_FILE, "w") as f:
        json.dump({}, f)

# ---------- BOT ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="$", intents=intents)

def has_support(member):
    return any(r.id == SUPPORT_ROLE_ID for r in member.roles)

# ---------- TRADE MODAL ----------
class TradeTicketModal(Modal, title="📝 Trade Ticket Form"):
    def __init__(self, tier: str):
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

        mm_role_id = MM_ROLES[self.tier]
        mm_role = guild.get_role(mm_role_id)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            mm_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

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
            content=f"{interaction.user.mention} <@&{mm_role_id}>",
            embed=embed,
            view=TicketButtons(self.tier)
        )

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )

# ---------- TICKET BUTTONS ----------
class TicketButtons(View):
    def __init__(self, tier: str):
        super().__init__(timeout=None)
        self.tier = tier
        self.claimed_by = None

    @discord.ui.button(
        label="🎯 Claim",
        style=discord.ButtonStyle.green,
        custom_id="ticket_claim"
    )
    async def claim(self, interaction: discord.Interaction, button: Button):
        required_role = MM_ROLES[self.tier]

        if not any(r.id == required_role for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ You are not allowed to claim this ticket.",
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

    @discord.ui.button(
        label="🔒 Close Ticket",
        style=discord.ButtonStyle.red,
        custom_id="ticket_close"
    )
    async def close(self, interaction: discord.Interaction, button: Button):
        if not has_support(interaction.user) and interaction.user != self.claimed_by:
            return await interaction.response.send_message(
                "❌ Only support or the claimer can close.",
                ephemeral=True
            )

        await interaction.response.send_message("Closing...", ephemeral=True)
        await asyncio.sleep(1)
        await interaction.channel.delete()

# ---------- TRADE PANEL ----------
class TradeTypeSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Choose middleman tier...",
            min_values=1,
            max_values=1,
            custom_id="trade_mm_select",
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
        self.add_item(TradeTypeSelect())

# ---------- COMMANDS ----------
@bot.command()
async def ticketpanel(ctx):
    if not has_support(ctx.author):
        return await ctx.send("❌ Support only.")

    embed = discord.Embed(
        title="🎯 Trade Panel",
        description="Select a middleman tier to open a trade ticket.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=TradePanel())

# ---------- ADD USER TO TICKET ----------
@bot.command()
async def add(ctx, user: discord.Member):
    if not has_support(ctx.author):
        return await ctx.send("❌ Support only.")

    if not ctx.channel.category or ctx.channel.category.name != TICKET_CATEGORY:
        return await ctx.send("❌ This command can only be used in ticket channels.")

    await ctx.channel.set_permissions(
        user,
        view_channel=True,
        send_messages=True,
        read_message_history=True
    )

    await ctx.send(f"✅ Added {user.mention} to this ticket.")

# ---------- SILENCE UNKNOWN COMMANDS ----------
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
    print("✅ Persistent TradePanel loaded.")

# ---------- RUN ----------
bot.run(os.getenv("TOKEN"))
