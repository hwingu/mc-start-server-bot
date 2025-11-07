import discord
import os
from mcstatus import JavaServer
import subprocess
from discord.ext import tasks, commands
import asyncio
from mcrcon import MCRcon
from subprocess import CREATE_NEW_CONSOLE
import json

try:
    with open("config.json") as f:
        config = json.load(f)
except FileNotFoundError:
    print("FATAL ERROR: config.json not found.")
    print("Please create a config.json file.")
    exit()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

# Configuration
SERVER_START_SCRIPT = config.get("server_start_script")
RCON_PASSWORD = config.get("rcon_password")
RCON_HOST = config.get("rcon_host")
RCON_PORT = config.get("rcon_port")
INACTIVITY_LIMIT_MINUTES = config.get("inactivity_limit_minutes")
SERVER_ADDRESS = config.get("server_address")

empty_since = None
server_started = False
is_starting = False

# Bot Events
@bot.event
async def on_ready():
    global server_started
    global is_starting

    status = await check_server_status()
    if status: 
        server_started = True

    is_starting = False
    print(f'We have logged in as {bot.user}')
    check_inactivity.start()


def get_server_status_sync():
    try:
        server = JavaServer.lookup(SERVER_ADDRESS)
        status = server.status()

        return status

    except Exception as e:
        print(f"Server is OFFLINE or unreachable. Error: {e}")
        return None
    
async def check_server_status():
    status = await asyncio.to_thread(get_server_status_sync)
    return status

def run_rcon_command(command_to_run):
    """A helper function to run a single, blocking RCON command."""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, RCON_PORT) as mcr:
            response = mcr.command(command_to_run)
            return response
    except Exception as rcon_error:
        print(f"RCON error executing '{command_to_run}': {rcon_error}")
        raise 

# Bot Commands
@bot.command()
async def status(ctx):
    if server_started:
        status = await check_server_status()

        if status:
            if status.players.sample:
                response = (f"✅ **Server is ONLINE!**\n"
                            f"**Players:** {status.players.online}/{status.players.max}: {', '.join(player.name for player in status.players.sample)}\n"
                            )
            else:
                response = (f"✅ **Server is ONLINE!**\n"
                            f"**Players:** {status.players.online}/{status.players.max}: No players connected\n"
                            )
        else:
            response = "❌ **Server is OFFLINE**"
    else:
        response = "❌ **Server is OFFLINE**"
    await ctx.send(response)

@bot.command()
async def start(ctx):
    global server_started
    global is_starting
    user_mention = ctx.author.mention

    if server_started:
        await ctx.send("✅ **The server is already ONLINE!**")
        return
    
    if is_starting:
        await ctx.send("⚠️ **The server is already starting. Please wait...**")
        return
    
    try:
        is_starting = True 
        await ctx.send("Server is offline. Attempting to start...")

        subprocess.Popen([SERVER_START_SCRIPT], creationflags=CREATE_NEW_CONSOLE)
        await ctx.send(f"**Server is starting!**\nServer is set to shutdown automatically after **{INACTIVITY_LIMIT_MINUTES} minutes** of inactivity.\n")
        
        for i in range(20):
            print(f"Checking server status... Attempt {i+1}/20")
            await asyncio.sleep(10) 
            status = await check_server_status()

            if status:
                await ctx.send(f"✅ **The server is ONLINE!** {user_mention}")
                server_started = True
                is_starting = False
                print("server started", server_started)
                return
            
        else:
            await ctx.send(f"❌ **Error:** Server failed to start after 3+ minutes. {user_mention}, please check the server console.")
            is_starting = False

    except Exception as start_error:
        print(f"Failed to start server: {start_error}")
        is_starting = False
        await ctx.send("❌ **Error:** Could not run the start script.")

@bot.command()
async def stop(ctx):
    global server_started
    global is_starting

    if not server_started:
        await ctx.send("❌ **The server is OFFLINE!**")
        return

    status = await check_server_status()

    if status:
        if status.players.online > 0:
            await ctx.send("⚠️ **There are players online! Please ask them to log off before stopping the server.**")
            return
        
        try:
            await asyncio.to_thread(run_rcon_command, "stop")
            await ctx.send("🛑 **Server is stopping!**")
            server_started = False
            is_starting = False

        except Exception as rcon_error:
            print(f"Failed to stop server: {rcon_error}")
            await ctx.send("❌ **Error:** Could not connect via RCON to stop the server.")
    else:
        await ctx.send("❌ **The server is running but cannot be connected to. Is the `playit.gg` tunnel running?**")
        return

# Bot Tasks
@tasks.loop(minutes=5)
async def check_inactivity():
    global empty_since
    global server_started
    global is_starting

    if server_started:

        status = await check_server_status()

        if status:
            print("[Inactivity Check] Running check...")
            if status.players.online <= 0 and empty_since is None:
                empty_since = asyncio.get_event_loop().time()
                print(f"[Inactivity Check] Server is empty. Starting {INACTIVITY_LIMIT_MINUTES} min timer.")

            elif status.players.online > 0:
                empty_since = None
                print("[Inactivity Check] Players detected. Resetting timer.")
            else:
                elapsed = (asyncio.get_event_loop().time() - empty_since) / 60
                print(f"[Inactivity Check] Server empty for {elapsed:.2f} minutes.")
                
                if elapsed >= INACTIVITY_LIMIT_MINUTES:
                    print(f"[Inactivity Check] Server empty for {INACTIVITY_LIMIT_MINUTES} mins. Stopping.")
                    
                    try:
                        await asyncio.to_thread(run_rcon_command, "stop")
                        server_started = False
                        is_starting = False
                        empty_since = None
                    except Exception as rcon_error:
                        print(f"Failed to auto-stop server: {rcon_error}")
        else:
            print("[Inactivity Check] Server is offline. Resetting timer.")
            server_started = False
            is_starting = False
            empty_since = None

bot.run(config.get("bot_token"))