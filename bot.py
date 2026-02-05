import discord
from discord.ext import commands
import os, json, asyncio, random, re
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ---------- CONFIG ----------
TICKET_CATEGORY = "Tickets"
SUPPORT_ROLE_ID = 1467374470221136067
VOUCHES_FILE = "vouches.json"
GUILD_ID = 1467374095841628207

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

def has_support_role(member: discord.Member):
    return any(r.id == SUPPORT_ROLE_ID for r in member.roles)

# ---------- ADD ----------
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

# ---------- GIVEAWAY ----------
@bot.command()
async def giveaway(ctx, name: str, duration: str, winners: int):
    if not has_support_role(ctx.author):
        return await ctx.send("❌ Only Support role can start giveaways.")

    match = re.match(r"^(\d+)(s|m|h|d)$", duration.lower())
    if not match:
        return await ctx.send("❌ Invalid duration — use 10s, 5m, 2h, or 1d.")

    amount, unit = int(match[1]), match[2]
    seconds = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[unit] * amount
    end_time = datetime.utcnow() + timedelta(seconds=seconds)

    embed = discord.Embed(
        title="🎉 GIVEAWAY 🎉",
        description=f"**Prize:** {name}\n\nReact with 🎉 to join!\nEnds <t:{int(end_time.timestamp())}:R>",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"{winners} winner(s) | Ends at {end_time.strftime('%H:%M:%S UTC')}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")

    await asyncio.sleep(seconds)
    new_msg = await ctx.channel.fetch_message(msg.id)
    users = await new_msg.reactions[0].users().flatten()
    users = [u for u in users if not u.bot]
    if not users:
        return await ctx.send("😢 No participants entered.")
    winners_list = random.sample(users, min(winners, len(users)))
    mentions = ", ".join(w.mention for w in winners_list)
    await ctx.send(f"🎊 Congratulations {mentions}! You won **{name}**!")

# ---------- RESTRICTED COMMANDS ----------
@bot.command()
async def claim(ctx):
    if not has_support_role(ctx.author):
        return await ctx.send("❌ Only the Support role can use this command.")
    if not ctx.channel.category or ctx.channel.category.name != TICKET_CATEGORY:
        return await ctx.send("❌ Use this in a ticket.")
    await ctx.send(f"🎯 {ctx.author.mention} claimed this ticket.")

@bot.command()
async def close(ctx):
    if not has_support_role(ctx.author):
        return await ctx.send("❌ Only the Support role can use this command.")
    if not ctx.channel.category or ctx.channel.category.name != TICKET_CATEGORY:
        return await ctx.send("❌ Use this in a ticket.")
    await ctx.send("Closing ticket...")
    await asyncio.sleep(1)
    await ctx.channel.delete()

@bot.command()
async def ticketpanel(ctx):
    if not has_support_role(ctx.author):
        return await ctx.send("❌ Only the Support role can use this command.")
    embed = discord.Embed(title="🎯 Trade Ticket", description="Click below to open a trade ticket.", color=discord.Color.green())
    view = discord.ui.View(timeout=None)
    button = discord.ui.Button(label="Open Trade Ticket", style=discord.ButtonStyle.green,
                               custom_id="open_trade_ticket")
    async def button_callback(interaction: discord.Interaction):
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
        em = discord.Embed(title="📌 Trade Ticket", description=f"Opened by {interaction.user.mention}",
                           color=discord.Color.green())
        await channel.send(content=f"{interaction.user.mention} <@&{SUPPORT_ROLE_ID}>", embed=em)
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)
    button.callback = button_callback
    view.add_item(button)
    await ctx.send(embed=embed, view=view)

@bot.command()
async def supportpanel(ctx):
    if not has_support_role(ctx.author):
        return await ctx.send("❌ Only the Support role can use this command.")
    embed = discord.Embed(title="🆘 Support Ticket", description="Click below to open a support ticket.", color=discord.Color.blurple())
    view = discord.ui.View(timeout=None)
    button = discord.ui.Button(label="Open Support Ticket", style=discord.ButtonStyle.blurple, custom_id="open_support_ticket")
    async def button_callback(interaction: discord.Interaction):
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
        em = discord.Embed(title="🎟️ Support Ticket", description=f"Opened by {interaction.user.mention}",
                           color=discord.Color.blurple())
        await channel.send(content=f"{interaction.user.mention} <@&{SUPPORT_ROLE_ID}>", embed=em)
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)
    button.callback = button_callback
    view.add_item(button)
    await ctx.send(embed=embed, view=view)

@bot.command()
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    if not has_support_role(ctx.author):
        return await ctx.send("❌ Only the Support role can use this command.")
    try:
        await member.ban(reason=reason)
        await ctx.send(f"✅ Banned **{member}** | Reason: {reason}")
    except Exception as e:
        await ctx.send(f"⚠️ Error banning {member}: {e}")

@bot.command()
async def unban(ctx, user: str):
    if not has_support_role(ctx.author):
        return await ctx.send("❌ Only the Support role can use this command.")
    try:
        user_id = int(user.strip('<@!>'))
        user_obj = await bot.fetch_user(user_id)
        await ctx.guild.unban(user_obj)
        await ctx.send(f"✅ Unbanned **{user_obj}**")
    except discord.NotFound:
        await ctx.send("⚠️ That user isn’t banned or doesn’t exist.")
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")

# ---------- READY ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        await bot.tree.sync()
        await bot.tree.clear_commands(guild=None)
        print("🧹 Cleared leftover slash commands.")
    except Exception as e:
        print("⚠️ Slash cleanup failed:", e)
    print("✅ Bot fully ready.")

# ---------- RUN ----------
bot.run(os.getenv("TOKEN"))
