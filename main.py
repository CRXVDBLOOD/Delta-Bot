import os
import time
from datetime import datetime
import zoneinfo
import discord
from discord import app_commands
from discord.ext import commands

class TimeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        pass

bot = TimeBot()

# --- CONFIGURATION (Ensure these match your exact server setup) ---
UNVERIFIED_ROLE_NAME = "unverifiedeveloper"
VERIFIED_ROLE_NAME = "developer"
DASHBOARD_CATEGORY_NAME = "Developer Timezones"
VERIFY_CHANNEL_NAME = "verify-here"

# --- EXTENDED GLOBAL TIMEZONE DATABASE ---
TIMEZONE_MAP = {
    "[UK] London / GMT (UTC+0)": "Europe/London",
    "[Western Europe] Paris / Berlin (UTC+1)": "Europe/Paris",
    "[Eastern Europe] Kyiv / Cairo (UTC+2)": "Europe/Kyiv",
    "[Saudi Arabia / Moscow] (UTC+3)": "Asia/Riyadh",
    "[UAE] Dubai (UTC+4)": "Asia/Dubai",
    "[Pakistan] Karachi (UTC+5)": "Asia/Karachi",
    "[India] Kolkata / IST (UTC+5:30)": "Asia/Kolkata",
    "[Bangladesh] Dhaka (UTC+6)": "Asia/Dhaka",
    "[Vietnam / Thailand] Bangkok (UTC+7)": "Asia/Bangkok",
    "[China / Singapore / Philippines] (UTC+8)": "Asia/Singapore",
    "[Japan / South Korea] Tokyo (UTC+9)": "Asia/Tokyo",
    "[Australia] Brisbane / AEST (UTC+10)": "Australia/Brisbane",
    "[Australia] Sydney / AEDT (UTC+11)": "Australia/Sydney",
    "[New Zealand] Auckland (UTC+12)": "Pacific/Auckland",
    
    "[USA] Eastern Time / New York (UTC-5)": "America/New_York",
    "[USA] Central Time / Chicago (UTC-6)": "America/Chicago",
    "[USA] Mountain Time / Denver (UTC-7)": "America/Denver",
    "[USA] Pacific Time / Los_Angeles (UTC-8)": "America/Los_Angeles",
    "[USA] Alaska Time (UTC-9)": "America/Anchorage",
    "[USA] Hawaii Time (UTC-10)": "Pacific/Honolulu",
    
    "[Canada] Atlantic Time / Halifax (UTC-4)": "America/Halifax",
    "[Brazil] Sao Paulo / Brasilia (UTC-3)": "America/Sao_Paulo",
    "[Argentina] Buenos Aires (UTC-3)": "America/Argentina/Buenos_Aires",
    "[Mexico] Mexico City (UTC-6)": "America/Mexico_City"
}

@bot.event
async def on_ready():
    print("---")
    print(f"Owner Setup & Onboarding Bot Online as {bot.user}")
    print("---")
    try:
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} slash commands!")
    except Exception as e:
        print(f"Error syncing commands: {e}")


# 🛠️ COMMAND 1: Owner-Only Server Build Command
@bot.tree.command(name="setup-verification", description="[OWNER ONLY] Builds the onboarding channels and verification embed panels automatically.")
async def setup_verification(interaction: discord.Interaction):
    guild = interaction.guild
    
    # Strictly enforce that ONLY the absolute server creator/owner can execute this
    if interaction.user.id != guild.owner_id:
        await interaction.response.send_message("❌ Access Denied. Only the **Server Owner** can execute this master setup command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME)
    if not unverified_role:
        await interaction.followup.send(f"❌ Error: Could not find a role named `{UNVERIFIED_ROLE_NAME}` inside your server settings. Please make sure you spell it exactly right first!")
        return

    # 1. Automatically generate the Dashboard Folder Category if missing
    category = discord.utils.get(guild.categories, name=DASHBOARD_CATEGORY_NAME)
    if not category:
        category = await guild.create_category(DASHBOARD_CATEGORY_NAME)

    # 2. Automatically generate the entry Verification Channel with lock-down rules
    verify_channel = discord.utils.get(guild.text_channels, name=VERIFY_CHANNEL_NAME)
    if not verify_channel:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            unverified_role: discord.PermissionOverwrite(view_channel=True, send_messages=False) # Block manual typing, they must use the slash interaction dropdown
        }
        verify_channel = await guild.create_text_channel(
            name=VERIFY_CHANNEL_NAME,
            overwrites=overwrites
        )

    # 3. Deploy the customized welcome embed instructions you specified
    embed = discord.Embed(
        title="# Hello this is an developer verification channel",
        description=(
            "Put your country or time region in this embed so everyone can track your availability "
            "and what time is it for you you can also see everyones time region.\n\n"
            "By also completing this you get developer roles so you can get access to developer channels."
        ),
        color=discord.Color.blue()
    )
    embed.add_field(name="How to verify:", value="Type `/verify` in your chat box, click the command, select your global location from the autocompletion dropdown menu, and press Enter!", inline=False)
    embed.set_footer(text="Automated Developer Gatekeeper System")

    await verify_channel.send(embed=embed)
    await interaction.followup.send(f"✅ Onboarding framework deployed successfully! The gate channel is now live at: {verify_channel.mention}")


# 📄 COMMAND 2: Public Interactive Verification Command
@bot.tree.command(name="verify", description="Onboard by choosing your country location and matching UTC offset.")
@app_commands.describe(timezone="Type your country name or offset value (e.g. UTC+8)")
async def verify(interaction: discord.Interaction, timezone: str):
    user = interaction.user
    guild = interaction.guild

    unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME)
    verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)

    if not unverified_role or unverified_role not in user.roles:
        await interaction.response.send_message("❌ This command is reserved for unverified developers.", ephemeral=True)
        return

    if timezone not in TIMEZONE_MAP:
        await interaction.response.send_message("❌ Configuration error. Please select an option directly from the auto-populating drop-down choice list!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    iana_timezone_str = TIMEZONE_MAP[timezone]
    tz_target = zoneinfo.ZoneInfo(iana_timezone_str)

    now_utc = datetime.now(zoneinfo.ZoneInfo("UTC"))
    now_target = now_utc.astimezone(tz_target)
    offset_seconds = now_target.utcoffset().total_seconds()

    category = discord.utils.get(guild.categories, name=DASHBOARD_CATEGORY_NAME)
    if not category:
        category = await guild.create_category(DASHBOARD_CATEGORY_NAME)

    clean_name = user.name.lower().replace(" ", "-")
    channel_name = f"🕒-{clean_name}-time"
    
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        unverified_role: discord.PermissionOverwrite(read_messages=False)
    }

    timezone_channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites
    )

    live_unix = int(time.time()) + int(offset_seconds)
    
    embed = discord.Embed(
        title="Developer System Profile",
        description=f"Active real-time status and operational time matrix tracking for **{user.display_name}**.",
        color=discord.Color.dark_teal()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="Developer Name", value=user.mention, inline=True)
    embed.add_field(name="Assigned Location", value=f"🌍 `{timezone}`", inline=True)
    embed.add_field(name="Local Current Clock", value=f"📡 <t:{live_unix}:T>", inline=True)
    embed.add_field(name="Calendar Date", value=f"📅 <t:{live_unix}:d>", inline=True)
    embed.set_footer(text="Clocks match international standard syncing models automatically.")

    pinned_msg = await timezone_channel.send(embed=embed)
    await pinned_msg.pin()

    if verified_role:
        await user.add_roles(verified_role)
    await user.remove_roles(unverified_role)

    await interaction.followup.send(f"🎉 Onboarding complete! Profile entry listed under: {timezone_channel.mention}")

@verify.autocomplete("timezone")
async def verify_autocomplete(interaction: discord.Interaction, current: str):
    choices = []
    for display_label in TIMEZONE_MAP.keys():
        if current.lower() in display_label.lower():
            choices.append(app_commands.Choice(name=display_label, value=display_label))
    return choices[:25]

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
