import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
import os, asyncio
from dotenv import load_dotenv

load_dotenv()

# ---------- CONFIG ----------
SUPPORT_ROLE_ID = 1467374470221136067
GUILD_ID = 1467374095841628207
TICKET_CATEGORY = "Tickets"

MM_TIERS = {
    "0-150m": {"role": 1467374476537893063, "rank": 1},
    "0-300m": {"role": 1467374475724067019, "rank": 2},
    "0-500m": {"role": 1467374474671423620, "rank": 3},
    "0-1b":   {"role": 1467374473723252746, "rank": 4},
    "1b+":    {"role": 1470545241525194948, "rank": 5},
}

# ---------- BOT ----------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents)

# ---------- HELPERS ----------
def get_mm_rank(member: discord.Member):
    rank = 0
    for tier in MM_TIERS.values():
        if any(r.id == tier["role"] for r in member.roles):
            rank = max(rank, tier["rank"])
    return rank

def is_staff(member):
    return any(r.id == SUPPORT_ROLE_ID for r in member.roles)

# ---------- MODALS ----------
class TradeModal(Modal, title="📝 Trade Ticket"):
    trader = TextInput(label="Other Trader (User / ID)")
    giving = TextInput(label="You Are Giving")
    receiving = TextInput(label="You Are Receiving")
    fee = TextInput(label="Middleman Fee")

    def __init__(self, tier_key):
        super().__init__()
        self.tier_key = tier_key

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY)
        if not category:
            category = await guild.create_category(TICKET_CATEGORY)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        # Allow all MM roles to view
        for tier in MM_TIERS.values():
            role = guild.get_role(tier["role"])
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True)

        # Staff can view/help
        staff = guild.get_role(SUPPORT_ROLE_ID)
        if staff:
            overwrites[staff] = discord.PermissionOverwrite(view_channel=True)

        channel = await guild.create_text_channel(
            name=f"trade-{interaction.user.id}",
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(title="📌 Trade Ticket", color=discord.Color.green())
        embed.add_field(name="Trader", value=self.trader.value, inline=False)
        embed.add_field(name="Giving", value=self.giving.value, inline=False)
        embed.add_field(name="Receiving", value=self.receiving.value, inline=False)
        embed.add_field(name="MM Fee", value=self.fee.value, inline=False)
        embed.add_field(name="Tier", value=self.tier_key, inline=False)

        await channel.send(
            content=f"{interaction.user.mention}",
            embed=embed,
            view=TicketButtons(self.tier_key)
        )

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )

class SupportModal(Modal, title="📝 Support Ticket"):
    reason = TextInput(label="Reason / Issue")

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY)
        if not category:
            category = await guild.create_category(TICKET_CATEGORY)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        # Only staff can view support tickets
        staff = guild.get_role(SUPPORT_ROLE_ID)
        if staff:
            overwrites[staff] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"support-{interaction.user.id}",
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(
            title="🎟️ Support Ticket",
            description=self.reason.value,
            color=discord.Color.blurple()
        )

        await channel.send(
            content=f"{interaction.user.mention} <@&{SUPPORT_ROLE_ID}>",
            embed=embed,
            view=TicketButtons("support")
        )

        await interaction.response.send_message(
            f"✅ Support ticket created: {channel.mention}",
            ephemeral=True
        )

# ---------- TICKET BUTTONS ----------
class TicketButtons(View):
    def __init__(self, tier_key):
        super().__init__(timeout=None)
        self.tier = tier_key
        self.claimed_by = None

    @discord.ui.button(label="🎯 Claim", style=discord.ButtonStyle.green, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: Button):
        if self.tier == "support":
            if not is_staff(interaction.user):
                return await interaction.response.send_message("❌ Only staff can claim support tickets.", ephemeral=True)
        else:
            user_rank = get_mm_rank(interaction.user)
            required_rank = MM_TIERS[self.tier]["rank"]
            if user_rank == 0:
                return await interaction.response.send_message("❌ Only verified middlemen can claim this ticket.", ephemeral=True)
            if user_rank < required_rank:
                return await interaction.response.send_message("❌ Your middleman tier is too low.", ephemeral=True)

        if self.claimed_by:
            return await interaction.response.send_message(f"Already claimed by {self.claimed_by.mention}", ephemeral=True)

        self.claimed_by = interaction.user
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.channel.edit(name=f"claimed-{interaction.user.name}")
        await interaction.response.send_message(f"🎯 {interaction.user.mention} claimed this ticket.")

    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.red, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: Button):
        if not (is_staff(interaction.user) or self.claimed_by == interaction.user):
            return await interaction.response.send_message("❌ No permission.", ephemeral=True)
        await interaction.channel.delete()

# ---------- PANELS ----------
class TradePanel(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TierSelect())

class TierSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=f"Middleman {k}", value=k)
            for k in MM_TIERS.keys()
        ]
        super().__init__(
            placeholder="Select trade size / MM tier",
            options=options,
            custom_id="mm_tier_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TradeModal(self.values[0]))

class SupportPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🆘 Open Support Ticket", style=discord.ButtonStyle.blurple, custom_id="support_open")
    async def open_support(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SupportModal())

# ---------- COMMANDS ----------
@bot.command()
async def ticketpanel(ctx):
    embed = discord.Embed(
        title="🎯 Trade Ticket Panel",
        description="Choose the trade size to open a ticket.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=TradePanel())

@bot.command()
async def supportpanel(ctx):
    if not is_staff(ctx.author):
        return await ctx.send("❌ Staff only.")
    embed = discord.Embed(
        title="🆘 Support Panel",
        description="Click below to open a support ticket.",
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed, view=SupportPanel())

@bot.command()
async def mminfo(ctx):
    embed = discord.Embed(
        title="🔐 What Is a Middleman?",
        description=(
            "A **middleman (MM)** is a trusted third party to keep trades safe.\n\n"
            "**How it works:**\n"
            "• Both traders give items to the MM\n"
            "• MM verifies trade\n"
            "• Items are exchanged safely\n\n"
            "**Rules:**\n"
            "• Only selected tier + higher tiers can claim\n"
            "• Staff can help but cannot claim unless MM"
        ),
        color=discord.Color.gold()
    )
    embed.set_image(
        url="https://cdn.discordapp.com/attachments/1467374503796408454/1470544269528797259/image-34.png"
    )
    await ctx.send(embed=embed)

# ---------- READY ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    bot.add_view(TradePanel())
    bot.add_view(SupportPanel())

# ---------- RUN ----------
bot.run(os.getenv("TOKEN"))
