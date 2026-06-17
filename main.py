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
        # Dictionary tracking active users: {user_id: timezone_string}
        self.active_clocks = {}

    async def setup_hook(self):
        # Force Syncing commands globally right here on boot
        try:
            synced = await self.tree.sync()
            print(f"🔄 Successfully synchronized {len(synced)} slash commands globally via setup_hook.")
        except Exception as e:
            print(f"⚠️ Failed to sync commands: {e}")

        # Start the background editing loop task
        self.update_clocks_loop.start()

    # 🔄 BACKGROUND TASK: Edits existing embeds in-place every 1 minute
    @tasks.loop(minutes=1)
    async def update_clocks_loop(self):
        for guild in self.guilds:
            try:
                channel = discord.utils.get(guild.text_channels, name=CLOCK_CHANNEL_NAME)
                if not channel or not self.active_clocks:
                    continue

                # Fetch recent bot messages from the channel to find old embeds to modify
                existing_messages = [
                    msg async for msg in channel.history(limit=100) 
                    if msg.author == self.user and msg.embeds
                ]

                # Update or build an embed for each registered developer
                for user_id, tz_name in list(self.active_clocks.items()):
                    member = guild.get_member(user_id) or await guild.fetch_member(user_id)
                    if not member:
                        continue

                    # Calculate local time
                    tz = zoneinfo.ZoneInfo(tz_name)
                    now_local = datetime.now(zoneinfo.ZoneInfo("UTC")).astimezone(tz)
                    
                    formatted_time = now_local.strftime("%I:%M %p").lstrip("0")
                    formatted_date = now_local.strftime("%A, %B %d, %Y")

                    # Dynamic color adjustment based on day/night cycles without visual clutter
                    embed_color = discord.Color.blue() if 6 <= now_local.hour < 18 else discord.Color.dark_purple()

                    # Build clean profile card layout
                    embed = discord.Embed(
                        title=f"👤 {member.display_name}'s Clock Panel",
                        color=embed_color
                    )
                    
                    embed.add_field(name="Local Time", value=f"`{formatted_time}`", inline=True)
                    embed.add_field(name="Date", value=f"`{formatted_date}`", inline=True)
                    embed.add_field(name="Region Mapping", value=f"`{tz_name}`", inline=False)
                    
                    # 🖼️ LIVE PFP SYNC: Always grabs their current profile picture link directly from Discord
                    embed.set_thumbnail(url=member.display_avatar.url)
                    
                    # Invisible ID string mapping used as our primary targeting reference key
                    embed.set_footer(text=f"Developer ID: {user_id}")

                    # Find if a message already exists for this specific developer
                    target_msg = None
                    for msg in existing_messages:
                        if msg.embeds[0].footer and msg.embeds[0].footer.text == f"Developer ID: {user_id}":
                            target_msg = msg
                            break

                    if target_msg:
                        # Only execute an edit request if data updates to save rate limits
                        if (target_msg.embeds[0].fields[0].value != f"`{formatted_time}`" or 
                            target_msg.embeds[0].thumbnail.url != member.display_avatar.url):
                            await target_msg.edit(embed=embed)
                    else:
                        # Deploy a fresh tracking card if they don't have one in the channel yet
                        await channel.send(embed=embed)

                # Optional Cleanup: Remove any loose panels whose owners are no longer tracked
                tracked_footers = [f"Developer ID: {uid}" for uid in self.active_clocks.keys()]
                for msg in existing_messages:
                    if msg.embeds[0].footer and msg.embeds[0].footer.text not in tracked_footers:
                        await msg.delete()

            except Exception as e:
                print(f"Error executing embed modification cycle loop: {e}")

    # ⏱️ WALL-CLOCK SYNCHRONIZER
    @update_clocks_loop.before_loop
    async def before_update_clocks_loop(self):
        await self.wait_until_ready()
        
        # Calculate exactly how many seconds remain until the next clean real-world minute rollover (:00)
        now = datetime.now()
        seconds_until_next_minute = 60 - now.second - (now.microsecond / 1000000.0)
        
        print(f"⏱️ Time Sync: Waiting {round(seconds_until_next_minute, 2)}s to align perfectly with the top of the minute...")
        await asyncio.sleep(seconds_until_next_minute)
        print("⏱️ Time Sync: Successfully locked onto atomic wall-clock intervals!")

bot = TimeBot()

# --- CONFIGURATION (Ensure these match your exact server setup case-sensitively!) ---
UNVERIFIED_ROLE_NAME = "Unverified Developer"
VERIFIED_ROLE_NAME = "Developer"
ADMIN_ROLE_NAME = "Master Administrator"
VERIFY_CHANNEL_NAME = "verify-here"
CLOCK_CHANNEL_NAME = "developer-clocks"  # Shared text dashboard location

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
    
    # 💾 BOOT CHECK: Re-read tracking definitions hidden cleanly inside the channel topic metadata
    try:
        for guild in bot.guilds:
            channel = discord.utils.get(guild.text_channels, name=CLOCK_CHANNEL_NAME)
            if channel and channel.topic and "DATA:" in channel.topic:
                raw_data = channel.topic.split("DATA:")[1].strip()
                if raw_data:
                    for item in raw_data.split(","):
                        if ":" in item:
                            uid_str, tz = item.split(":", 1)
                            bot.active_clocks[int(uid_str)] = tz
        print(f"💾 Restored tracking definitions for {len(bot.active_clocks)} active developers.")
    except Exception as e:
        print(f"Error handling boot scan string parsing: {e}")


def is_master_admin():
    def predicate(interaction: discord.Interaction) -> bool:
        admin_role = discord.utils.get(interaction.user.roles, name=ADMIN_ROLE_NAME)
        if admin_role is not None:
            return True
        raise app_commands.errors.MissingRole([ADMIN_ROLE_NAME])
    return app_commands.checks.check(predicate)


# 🛠️ COMMAND 1: Master Administrator Server Build Command
@bot.tree.command(name="setup-verification", description="[MASTER ADMIN ONLY] Builds onboarding and the single clock channel.")
@is_master_admin()
async def setup_verification(interaction: discord.Interaction):
    guild = interaction.guild
    await interaction.response.defer(ephemeral=True)

    unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME)
    verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
    if not unverified_role or not verified_role:
        await interaction.followup.send(f"❌ Error: Could not find roles named `{UNVERIFIED_ROLE_NAME}` or `{VERIFIED_ROLE_NAME}`.", ephemeral=True)
        return

    # Create Gateway Verification Channel
    verify_channel = discord.utils.get(guild.text_channels, name=VERIFY_CHANNEL_NAME)
    if not verify_channel:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            unverified_role: discord.PermissionOverwrite(view_channel=True, send_messages=False)
        }
        verify_channel = await guild.create_text_channel(name=VERIFY_CHANNEL_NAME, overwrites=overwrites)
    else:
        try:
            await verify_channel.purge(limit=10, check=lambda m: m.author == bot.user)
        except Exception:
            pass

    # Create Singular Clock Channel
    clock_channel = discord.utils.get(guild.text_channels, name=CLOCK_CHANNEL_NAME)
    if not clock_channel:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            verified_role: discord.PermissionOverwrite(view_channel=True, send_messages=False)
        }
        await guild.create_text_channel(name=CLOCK_CHANNEL_NAME, overwrites=overwrites, topic="Live Developer Dashboard | DATA:")

    embed = discord.Embed(
        title="Hello this is an developer verification channel",
        description=(
            "Put your country or time region in this embed so everyone can track your availability "
            "and what time is it for you you can also see everyones time region.\n\n"
            "By also completing this you get developer roles so you can get access to developer channels."
        ),
        color=discord.Color.blue()
    )
    embed.add_field(name="How to verify:", value="Type `/verify` in your chat box, click the command, select your global location from the menu, and press Enter!", inline=False)
    
    await verify_channel.send(embed=embed)
    await interaction.followup.send(f"✅ Onboarding framework deployed! Verification gate: {verify_channel.mention}", ephemeral=True)


# 🔍 AUTOCOMPLETE AUTO-SUGGEST LOGIC
async def timezone_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    choices = []
    for label in TIMEZONE_MAP.keys():
        if current.lower() in label.lower():
            choices.append(app_commands.Choice(name=label, value=label))
    return choices[:25]


# 📄 COMMAND 2: Public Interactive Verification Command
@bot.tree.command(name="verify", description="Onboard by choosing your country location and matching UTC offset.")
@app_commands.describe(timezone="Type your country name or offset value (e.g. UTC+8)")
@app_commands.autocomplete(timezone=timezone_autocomplete)
async def verify(interaction: discord.Interaction, timezone: str):
    guild = interaction.guild
    member = interaction.user if isinstance(interaction.user, discord.Member) else await guild.fetch_member(interaction.user.id)

    unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME)
    verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)

    if not unverified_role or not verified_role:
        await interaction.response.send_message("❌ Server configuration error with role names.", ephemeral=True)
        return

    if unverified_role not in member.roles:
        await interaction.response.send_message("❌ This command is reserved for unverified developers.", ephemeral=True)
        return

    if timezone not in TIMEZONE_MAP:
        await interaction.response.send_message("❌ Please select an option directly from the auto-suggested list!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    clock_channel = discord.utils.get(guild.text_channels, name=CLOCK_CHANNEL_NAME)
    if not clock_channel:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            verified_role: discord.PermissionOverwrite(view_channel=True, send_messages=False)
        }
        clock_channel = await guild.create_text_channel(name=CLOCK_CHANNEL_NAME, overwrites=overwrites, topic="Live Developer Dashboard | DATA:")

    iana_tz = TIMEZONE_MAP[timezone]
    
    # Update local memory map tracking configuration
    bot.active_clocks[member.id] = iana_tz

    # Save tracking data map string back to channel topic metadata for reboots
    data_segments = [f"{uid}:{tz}" for uid, tz in bot.active_clocks.items()]
    await clock_channel.edit(topic=f"Live Developer Dashboard | DATA: {','.join(data_segments)}")

    # Role processing assignments 
    try:
        if unverified_role in member.roles:
            await member.remove_roles(unverified_role)
        await member.add_roles(verified_role)
    except discord.Forbidden:
        await interaction.followup.send("⚠️ Saved preferences, but I couldn't change your roles due to Discord server role hierarchy positions.", ephemeral=True)
        return

    await interaction.followup.send(f"✅ Verification successful! Your local clock profile is now processing on the panel here: {clock_channel.mention}", ephemeral=True)


# 🗑️ COMMAND 3: Restricted Channel Clear Command
@bot.tree.command(name="clear", description="Clears every message in the current text channel.")
async def clear_channel(interaction: discord.Interaction):
    user = interaction.user
    
    # Check if user matches the strict username or global name constraints
    if user.name == "._happymadman_." or user.global_name == "crxvedblood":
        await interaction.response.send_message("🧹 Clearing all messages in this channel...", ephemeral=True)
        try:
            # channel.purge deletes messages bulk-style up to 14 days old
            deleted = await interaction.channel.purge(limit=None)
            
            # Since purge cannot bulk-delete messages older than 14 days, fall back to individual deletion if needed
            print(f"Purged {len(deleted)} recent messages via bulk purge.")
        except discord.Forbidden:
            print("Bot lacks permission to manage messages or read channel history.")
        except Exception as e:
            print(f"Error during channel purge: {e}")
    else:
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)


# --- BOT EXECUTION ---
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("Fatal Error: No token found. Please set the DISCORD_TOKEN environment variable.")
