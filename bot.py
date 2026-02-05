import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import os, json
from dotenv import load_dotenv

load_dotenv()

# ---------- CONFIG ----------
TICKET_CATEGORY = "Tickets"
SUPPORT_ROLE_ID = 1467374470221136067  # Only this role can see tickets & use certain features
PANEL_ALLOWED_ROLES = ["Founder", "Secondary Owner", "Management"]
VOUCHES_FILE = "vouches.json"
GUILD_ID = 1467374095841628207  # Your server ID

# ---------- DATA ----------
if not os.path.exists(VOUCHES_FILE):
    with open(VOUCHES_FILE, "w") as f:
        json.dump({}, f)

def get_vouches(user_id: int):
    with open(VOUCHES_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(user_id), 0)

def add_vouch(user_id: int):
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

# ---------- HELPERS ----------
def has_role(member: discord.Member, role_id: int):
    return any(role.id == role_id for role in member.roles)

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
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
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
            embed=embed,
            view=TicketControlView()
        )

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )

# ---------- TICKET CONTROLS ----------
class TicketControlView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.claimed_by = None

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green, custom_id="claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: Button):
        if not has_role(interaction.user, SUPPORT_ROLE_ID):
            return await interaction.response.send_message("❌ You cannot claim tickets.", ephemeral=True)

        if self.claimed_by:
            return await interaction.response.send_message(f"⚠️ Already claimed by {self.claimed_by.mention}", ephemeral=True)

        self.claimed_by = interaction.user
        button.disabled = True
        self.unclaim_button.disabled = False
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"🎯 {interaction.user.mention} has claimed this ticket.", ephemeral=False)

    @discord.ui.button(label="Unclaim", style=discord.ButtonStyle.gray, disabled=True, custom_id="unclaim_ticket")
    async def unclaim_button(self, interaction: discord.Interaction, button: Button):
        if not has_role(interaction.user, SUPPORT_ROLE_ID):
            return await interaction.response.send_message("❌ You cannot unclaim tickets.", ephemeral=True)

        if not self.claimed_by:
            return await interaction.response.send_message("❌ This ticket isn’t claimed yet.", ephemeral=True)

        if interaction.user != self.claimed_by:
            return await interaction.response.send_message("❌ Only the claimer can unclaim.", ephemeral=True)

        self.claimed_by = None
        button.disabled = True
        self.claim.disabled = False
        await interaction.message.edit(view=self)
        await interaction.response.send_message("🟢 Ticket has been unclaimed.", ephemeral=False)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: Button):
        if not has_role(interaction.user, SUPPORT_ROLE_ID):
            return await interaction.response.send_message("❌ No permission.", ephemeral=True)
        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        await interaction.channel.delete()

# ---------- PANELS ----------
class TradePanelView(View):
    @discord.ui.button(label="Open Trade Ticket", style=discord.ButtonStyle.green, custom_id="open_trade_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(TradeTicketModal())

class SupportPanelView(View):
    @discord.ui.button(label="Open Support Ticket", style=discord.ButtonStyle.blurple, custom_id="open_support_ticket")
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
        await channel.send(content=f"{interaction.user.mention} <@&{SUPPORT_ROLE_ID}>", embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

# ---------- PANEL COMMANDS ----------
@bot.command()
async def ticketpanel(ctx):
    if not any(r.name in PANEL_ALLOWED_ROLES for r in ctx.author.roles):
        return await ctx.send("❌ You don't have permission.")
    embed = discord.Embed(title="🎯 Trade Panel", description="Click below to open a trade ticket.", color=discord.Color.green())
    await ctx.send(embed=embed, view=TradePanelView())

@bot.command()
async def supportpanel(ctx):
    if not any(r.name in PANEL_ALLOWED_ROLES for r in ctx.author.roles):
        return await ctx.send("❌ You don't have permission.")
    embed = discord.Embed(title="🆘 Support Panel", description="Click below to open a support ticket.", color=discord.Color.blurple())
    await ctx.send(embed=embed, view=SupportPanelView())

# ---------- ADD USER ----------
@bot.command()
async def add(ctx, user: discord.User):
    if not ctx.channel.category or ctx.channel.category.name != TICKET_CATEGORY:
        return await ctx.send("❌ Use this command inside a ticket.")
    await ctx.channel.set_permissions(user, view_channel=True, send_messages=True)
    await ctx.send(f"✅ Added {user.mention} to this ticket.")

# ---------- VOUCH SYSTEM ----------
@bot.command()
async def vouch(ctx, user: discord.User):
    add_vouch(user.id)
    await ctx.send(f"✅ Added a vouch to {user.mention} (Total: {get_vouches(user.id)})")

@bot.command()
async def vouches(ctx, user: discord.User):
    await ctx.send(f"💬 {user.mention} has **{get_vouches(user.id)}** vouches.")

# ---------- BAN / UNBAN ----------
@bot.command()
async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if not has_role(ctx.author, SUPPORT_ROLE_ID):
        return await ctx.send("❌ You don’t have permission to use this command.")
    try:
        await member.ban(reason=reason)
        await ctx.send(f"✅ Banned **{member}** | Reason: {reason}")
    except Exception as e:
        await ctx.send(f"⚠️ Error banning {member}: {e}")

@bot.command()
async def unban(ctx, user_id: int):
    if not has_role(ctx.author, SUPPORT_ROLE_ID):
        return await ctx.send("❌ You don’t have permission to use this command.")
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.send(f"✅ Unbanned **{user}**")
    except Exception as e:
        await ctx.send(f"⚠️ Error unbanning: {e}")

# ---------- READY ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    bot.add_view(TradePanelView())
    bot.add_view(SupportPanelView())
    bot.add_view(TicketControlView())
    print("✅ Ticket system ready with Claim/Unclaim/Close buttons!")

# ---------- RUN ----------
bot.run(os.getenv("TOKEN"))
