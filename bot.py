import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import os, json, asyncio
from dotenv import load_dotenv

load_dotenv()

# ---------- CONFIG ----------
SUPPORT_ROLE_ID = 1467374470221136067
TICKET_CATEGORY = "Tickets"
VOUCHES_FILE = "vouches.json"
GUILD_ID = 1467374095841628207

# ---------- DATA ----------
if not os.path.exists(VOUCHES_FILE):
    with open(VOUCHES_FILE, "w") as f:
        json.dump({}, f)

def get_vouches(user_id):
    with open(VOUCHES_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(user_id), 0)

def add_vouch(user_id):
    with open(VOUCHES_FILE, "r") as f:
        data = json.load(f)
    data[str(user_id)] = data.get(str(user_id), 0) + 1
    with open(VOUCHES_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ---------- BOT ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="$", intents=intents)

def has_support(member):
    return any(r.id == SUPPORT_ROLE_ID for r in member.roles)

# ---------- MODAL ----------
class TradeTicketModal(Modal, title="📝 Trade Ticket Form"):
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
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        support_role = guild.get_role(SUPPORT_ROLE_ID)
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

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
            content=f"{interaction.user.mention} <@&{SUPPORT_ROLE_ID}>",
            embed=embed, view=TicketButtons()
        )
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

# ---------- BUTTON VIEW ----------
class TicketButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.claimed_by = None

    @discord.ui.button(label="🎯 Claim", style=discord.ButtonStyle.green, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: Button):
        if not has_support(interaction.user):
            return await interaction.response.send_message("❌ Support only.", ephemeral=True)
        if self.claimed_by:
            return await interaction.response.send_message(f"Already claimed by {self.claimed_by.mention}", ephemeral=True)
        self.claimed_by = interaction.user
        await interaction.channel.edit(name=f"claimed-{interaction.user.name}")
        self.claim.disabled = True
        self.unclaim.disabled = False
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"🎯 {interaction.user.mention} claimed this ticket.")

    @discord.ui.button(label="↩️ Unclaim", style=discord.ButtonStyle.gray, custom_id="ticket_unclaim", disabled=True)
    async def unclaim(self, interaction: discord.Interaction, button: Button):
        if not has_support(interaction.user):
            return await interaction.response.send_message("❌ Support only.", ephemeral=True)
        if interaction.user != self.claimed_by:
            return await interaction.response.send_message("❌ Only the claimer can unclaim.", ephemeral=True)
        self.claimed_by = None
        await interaction.channel.edit(name=f"{interaction.channel.name.replace('claimed-', '')}")
        self.claim.disabled = False
        self.unclaim.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("🟢 Ticket unclaimed.")

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.red, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: Button):
        if not has_support(interaction.user):
            return await interaction.response.send_message("❌ Support only.", ephemeral=True)
        await interaction.response.send_message("Closing...", ephemeral=True)
        await asyncio.sleep(1)
        await interaction.channel.delete()

# ---------- PANEL VIEWS ----------
class TradePanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎯 Open Trade Ticket", style=discord.ButtonStyle.green, custom_id="trade_open")
    async def open_trade(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(TradeTicketModal())

class SupportPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🆘 Open Support Ticket", style=discord.ButtonStyle.blurple, custom_id="support_open")
    async def open_support(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY)
        if not category:
            category = await guild.create_category(TICKET_CATEGORY)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        support_role = guild.get_role(SUPPORT_ROLE_ID)
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"support-{interaction.user.id}",
            category=category,
            overwrites=overwrites
        )
        embed = discord.Embed(title="🎟️ Support Ticket",
                              description="Support will be with you shortly.",
                              color=discord.Color.blurple())
        await channel.send(content=f"{interaction.user.mention} <@&{SUPPORT_ROLE_ID}>",
                           embed=embed, view=TicketButtons())
        await interaction.response.send_message(f"✅ Support ticket created: {channel.mention}", ephemeral=True)

# ---------- SUPPORT PANEL COMMAND ----------
@bot.command()
async def supportpanel(ctx):
    if not has_support(ctx.author):
        return await ctx.send("❌ Support only.")
    embed = discord.Embed(title="🆘 Support Panel",
                          description="Open a support ticket below.",
                          color=discord.Color.blurple())
    await ctx.send(embed=embed, view=SupportPanel())

# ---------- TRADE PANEL COMMAND ----------
@bot.command()
async def ticketpanel(ctx):
    if not has_support(ctx.author):
        return await ctx.send("❌ Support only.")
    embed = discord.Embed(title="🎯 Trade Panel",
                          description="Click below to open a trade ticket.",
                          color=discord.Color.green())
    await ctx.send(embed=embed, view=TradePanel())

# ---------- OTHER UTILITIES ----------
@bot.command()
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    if not has_support(ctx.author):
        return await ctx.send("❌ Support only.")
    await member.ban(reason=reason)
    await ctx.send(f"✅ Banned {member} | Reason: {reason}")

@bot.command()
async def unban(ctx, user: str):
    if not has_support(ctx.author):
        return await ctx.send("❌ Support only.")
    try:
        user_id = int(user.strip('<@!>'))
        user_obj = await bot.fetch_user(user_id)
        await ctx.guild.unban(user_obj)
        await ctx.send(f"✅ Unbanned **{user_obj}**")
    except Exception as e:
        await ctx.send(f"⚠️ Error unbanning: {e}")

@bot.command()
async def vouch(ctx, user: discord.User):
    add_vouch(user.id)
    await ctx.send(f"✅ Added 1 vouch to {user.mention} ({get_vouches(user.id)} total)")

@bot.command()
async def vouches(ctx, user: discord.User):
    await ctx.send(f"💬 {user.mention} has **{get_vouches(user.id)}** vouches.")

# ---------- READY ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    bot.add_view(TradePanel())
    bot.add_view(SupportPanel())
    bot.add_view(TicketButtons())
    print("✅ Persistent ticket buttons loaded.")

# ---------- RUN ----------
bot.run(os.getenv("TOKEN"))
