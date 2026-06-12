import os
import asyncio
from datetime import datetime
import zoneinfo
import discord
from discord import app_commands
from discord.ext import commands, tasks

class TimeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        # Dictionary to track messages that need updating: {channel_id: timezone_string}
        self.active_clocks = {}

    async def setup_hook(self):
        # Start the background editing loop task
        self.update_clocks_loop.start()

    # 🔄 BACKGROUND TASK: Edits the text messages automatically when time changes
    @tasks.loop(seconds=10)
    async def update_clocks_loop(self):
        for channel_id, tz_name in list(self.active_clocks.items()):
            try:
                channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
                if not channel:
                    continue
                
                # Calculate the exact current local time for their country choice
                tz = zoneinfo.ZoneInfo(tz_name)
                now_local = datetime.now(zoneinfo.ZoneInfo("UTC")).astimezone(tz)
                
                # Format time precisely as: 3:17 AM (stripping zero padding like 03:17)
                formatted_time = now_local.strftime("%I:%M %p").lstrip("0")
                formatted_date = now_local.strftime("%A, %B %d, %Y")
                
                # The plain text string that will overwrite the old message text
                new_content = (
                    f"⏰ **Developer Clock:** `{formatted_time}`\n"
                    f"📅 **Date:** {formatted_date}\n"
                    f"🌍 **Timezone Region:** `{tz_name}`"
                )

                # Find the pinned profile message inside that specific channel to edit it
                pins = await channel.pins()
                if pins:
                    profile_msg = pins[0]
                    # Only edit if the text actually changed to save data limits
                    if profile_msg.content != new_content:
                        await profile_msg.edit(content=new_content)
            except Exception as e:
                print(f"Error editing clock channel {channel_id}: {e}")

    @update_clocks_loop.before_loop
    async def before_update_clocks_loop(self):
        await self.wait_until_ready()

bot = TimeBot()

# --- CONFIGURATION (Ensure these match your exact server setup) ---
UNVERIFIED_ROLE_NAME = "unverifiedeveloper"
VERIFIED_ROLE_NAME = "developer"
ADMIN_ROLE_NAME = "Master Administrator"
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
    print(f"Live Message Editing System Online as {bot.user}")
    print("---")
    
    # 💾 BOOT CHECK: Automatically scan existing channels so the loop resumes monitoring them if the bot restarts!
    try:
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} slash commands globally!")
        
        for guild in bot.guilds:
            category = discord.utils.get(guild.categories, name=DASHBOARD_CATEGORY_NAME)
            if category:
                for channel in category.text_channels:
                    if channel.name.startswith("🕒-") and channel.name.endswith("-time"):
                        pins = await channel.pins()
                        if pins:
                            # Read what timezone was assigned from the footer text line
                            for label, iana in TIMEZONE_MAP.items():
                                if iana in channel.topic or label in channel.topic:
                                    bot.active_clocks[channel.id] = iana
                                    break
                            if channel.id not in bot.active_clocks:
                                bot.active_clocks[channel.id] = "Asia/Singapore" # Fallback default
    except Exception as e:
        print(f"Error handling boot scan: {e}")


def is_master_admin():
    def predicate(interaction: discord.Interaction) -> bool:
        admin_role = discord.utils.get(interaction.user.roles, name=ADMIN_ROLE_NAME)
        if admin_role is not None:
            return True
        raise app_commands.errors.MissingRole(ADMIN_ROLE_NAME)
    return app_commands.checks.check(predicate)


# 🛠️ COMMAND 1: Master Administrator Server Build Command
@bot.tree.command(name="setup-verification", description="[MASTER ADMIN ONLY] Builds the onboarding channels and verification panels automatically.")
@is_master_admin()
async def setup_verification(interaction: discord.Interaction):
    guild = interaction.guild
    await interaction.response.defer(ephemeral=True)

    unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME)
    if not unverified_role:
        await interaction.followup.send(f"❌ Error: Could not find a role named `{UNVERIFIED_ROLE_NAME}` in your server. Please create it first!", ephemeral=True)
        return

    category = discord.utils.get(guild.categories, name=DASHBOARD_CATEGORY_NAME)
    if not category:
        category = await guild.create_category(DASHBOARD_CATEGORY_NAME)

    verify_channel = discord.utils.get(guild.text_channels, name=VERIFY_CHANNEL_NAME)
    if not verify_channel:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            unverified_role: discord.PermissionOverwrite(view_channel=True, send_messages=False)
        }
        verify_channel = await guild.create_text_channel(
            name=VERIFY_CHANNEL_NAME,
            category=category,
            overwrites=overwrites
        )

    embed = discord.Embed(
        title="Hello this is an developer verification channel",
        description=(
            "Put your country or time region in this embed so everyone can track your availability "
            "and what time is it for you you can also see everyones time region.\n\n"
            "By also completing this you get developer roles so you can get access to developer channels."
        ),
        color=discord.Color.blue()
    )
    embed.add_field(name="How to verify:", value="Type `/verify` in your chat box, click the command, select your global location from the dropdown menu, and press Enter!", inline=False)
    embed.set_footer(text="Automated Developer Gatekeeper System")

    await verify_channel.send(embed=embed)
    await interaction.followup.send(f"✅ Onboarding framework deployed successfully! The gate channel is live at: {verify_channel.mention}", ephemeral=True)


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
        await interaction.response.send_message("❌ Configuration error. Please select an option directly from the drop-down choice list!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    category = discord.utils.get(guild.categories, name=DASHBOARD_CATEGORY_NAME)
    if not category:
        category = await guild.create_category(DASHBOARD_CATEGORY_NAME)

    clean_name = user.name.lower().replace(" ", "-")
    channel_name = f"🕒-{clean_name}-time"
    
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        unverified_role: discord.PermissionOverwrite(read_messages=False)
    }

    iana_tz = TIMEZONE_MAP[timezone]

    # Create the text channel and store the timezone configuration directly in the channel metadata topic
    timezone_channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
