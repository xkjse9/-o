import os
import discord
from discord.ext import commands
from discord import app_commands, ui, Interaction
import json
import threading
import requests
import time
from flask import Flask
import traceback


# ---------- Discord Bot 設定 ----------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ---------- JSON 儲存檔 (關鍵字系統) ----------
DATA_FILE = "keywords.json"


def load_keywords():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"❗ 讀取 {DATA_FILE} 時發生錯誤，已備份並以空字典取代：{e}")
            try:
                os.rename(DATA_FILE, DATA_FILE + ".bak")
                print(f"備份檔案為 {DATA_FILE}.bak")
            except Exception as e2:
                print(f"備份失敗：{e2}")
            return {}
    else:
        return {}


keywords = load_keywords()

if not isinstance(keywords, dict):
    keywords = {}


def save_keywords():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(keywords, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"⚠️ 儲存 {DATA_FILE} 時出錯：{e}")


# ---------- 關鍵字 Modal ----------
class KeywordModal(ui.Modal, title="新增或修改關鍵字"):
    def __init__(self, key_to_edit=None):
        super().__init__()
        self.key_to_edit = key_to_edit

        self.keyword_input = ui.TextInput(
            label="要偵測的關鍵字或關鍵詞",
            placeholder="輸入關鍵字...",
            max_length=1000,
            default=key_to_edit if key_to_edit else "",
        )
        self.add_item(self.keyword_input)

        self.reply_input = ui.TextInput(
            label="回覆內容",
            placeholder="輸入回覆訊息...",
            style=discord.TextStyle.paragraph,
            max_length=2000,
        )
        self.add_item(self.reply_input)

    async def on_submit(self, interaction: Interaction):
        guild_id = str(interaction.guild_id)
        if guild_id not in keywords:
            keywords[guild_id] = {}

        key = self.keyword_input.value.strip()
        reply = self.reply_input.value.strip()

        if not key or not reply:
            await interaction.response.send_message("關鍵字或回覆不能為空", ephemeral=True)
            return

        if self.key_to_edit and self.key_to_edit != key:
            keywords[guild_id].pop(self.key_to_edit, None)

        keywords[guild_id][key] = reply
        save_keywords()

        await interaction.response.send_message(
            f"✅ 已儲存關鍵字 `{key}` 對應回覆 `{reply}`", ephemeral=True
        )


# ---------- 關鍵字按鈕面板 ----------
class KeywordView(ui.View):
    def __init__(self, guild_id: str):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        guild_keywords = keywords.get(guild_id, {})
        for key in guild_keywords:
            self.add_item(DeleteOrEditButton(guild_id, key))

    @ui.button(label="新增關鍵字", style=discord.ButtonStyle.primary)
    async def add_keyword(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(KeywordModal())


class DeleteOrEditButton(ui.Button):
    def __init__(self, guild_id, key):
        label = key if isinstance(key, str) and len(key) <= 80 else (str(key)[:77] + "...")
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id
        self.key = key
        self.custom_id = f"keyword_button_{guild_id}_{key}"

    async def callback(self, interaction: Interaction):
        options_view = ui.View(timeout=None)
        options_view.add_item(
            ui.Button(
                label="修改",
                style=discord.ButtonStyle.success,
                custom_id=f"edit_{self.guild_id}_{self.key}",
            )
        )
        options_view.add_item(
            ui.Button(
                label="刪除",
                style=discord.ButtonStyle.danger,
                custom_id=f"delete_{self.guild_id}_{self.key}",
            )
        )
        await interaction.response.send_message(
            f"管理關鍵字 `{self.key}`", view=options_view, ephemeral=True
        )


@bot.event
async def on_interaction(interaction: Interaction):
    try:
        if interaction.type != discord.InteractionType.component:
            return

        data = getattr(interaction, "data", None)
        if not data:
            return

        custom_id = data.get("custom_id", "")
        if not custom_id:
            return

        if custom_id.startswith("edit_"):
            _, guild_id, key = custom_id.split("_", 2)
            await interaction.response.send_modal(KeywordModal(key_to_edit=key))

        elif custom_id.startswith("delete_"):
            _, guild_id, key = custom_id.split("_", 2)
            if guild_id in keywords:
                keywords[guild_id].pop(key, None)
                save_keywords()
            await interaction.response.send_message(
                f"🗑️ 已刪除關鍵字 `{key}`", ephemeral=True
            )

    except Exception:
        print("on_interaction 發生例外：")
        traceback.print_exc()


# ---------- 關鍵字斜線指令 ----------
@bot.tree.command(name="keywords", description="開啟關鍵字管理面板")
async def keywords_command(interaction: Interaction):
    guild_id = str(interaction.guild_id)
    view = KeywordView(guild_id)
    await interaction.response.send_message(
        f"🔧 關鍵字管理面板（伺服器：{interaction.guild.name}）",
        view=view,
        ephemeral=True,
    )


# ---------- 偵測訊息 ----------
@bot.event
async def on_message(message):
    try:
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        guild_keywords = keywords.get(guild_id, {})

        for key, reply in guild_keywords.items():
            if key in message.content:
                await message.channel.send(reply)
                break

    except Exception:
        print("on_message 發生例外：")
        traceback.print_exc()
    finally:
        await bot.process_commands(message)


# ---------- 訂單 Modal ----------
class OrderModal(discord.ui.Modal, title="🛒 填寫表單"):
    product = discord.ui.TextInput(label="所需商品", placeholder="例如：1000R")
    account = discord.ui.TextInput(label="帳號", placeholder="輸入帳號")
    password = discord.ui.TextInput(label="密碼", style=discord.TextStyle.short, placeholder="輸入密碼")
    backup_codes = discord.ui.TextInput(
        label="五組備用碼 請以逗號分開",
        style=discord.TextStyle.paragraph,
        placeholder="例如：1234,5678,9012,3456,7890"
    )

    def __init__(self, user: discord.User, channel: discord.TextChannel):
        super().__init__()
        self.target_user = user
        self.target_channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        codes = [c.strip() for c in self.backup_codes.value.split(",") if c.strip()]
        formatted_codes = "\n".join([f"🔹 {c}" for c in codes])

        embed = discord.Embed(
            title="新訂單提交",
            color=discord.Color.blue()
        )
        embed.add_field(name="所需商品", value=self.product.value, inline=False)
        embed.add_field(name="帳號", value=self.account.value, inline=False)
        embed.add_field(name="密碼", value=self.password.value, inline=False)
        embed.add_field(name="備用碼", value=formatted_codes or "無", inline=False)

        await self.target_channel.send(embed=embed)
        await interaction.response.send_message("✅ 表單已提交！", ephemeral=True)

        # ===== 刪除整個訂單面板訊息 =====
        try:
            if interaction.message:
                await interaction.message.delete()
        except Exception as e:
            print(f"刪除訂單面板訊息失敗: {e}")


# ---------- 訂單按鈕 ----------
class OrderButton(discord.ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=None)
        self.user = user

    @discord.ui.button(label="📝 填寫訂單", style=discord.ButtonStyle.primary)
    async def fill_order(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 這不是給你的表單喔！", ephemeral=True)
            return
        try:
            modal = OrderModal(user=self.user, channel=interaction.channel)
            await interaction.response.send_modal(modal)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 無法開啟表單，請稍後再試。\n```{e}```", ephemeral=True)


# ---------- 訂單斜線指令 ----------
@bot.tree.command(name="開啟訂單", description="建立一個填寫訂單的表單介面")
@app_commands.describe(user="選擇可以填寫此訂單的用戶")
async def open_order(interaction: discord.Interaction, user: discord.User):
    embed = discord.Embed(
        title="🛒 訂單填寫表單",
        description=f"{user.mention} 麻煩點選下面的按鈕填寫所需商品、帳號、密碼、備用碼。送出後請提供最近遊玩的20款遊戲，感謝配合！",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, view=OrderButton(user))


# ---------- 上線事件 ----------
@bot.event
async def on_ready():
    try:
        print(f"✅ {bot.user} 已上線")
        await bot.change_presence(activity=discord.Game(name="關鍵字監聽中"))
        try:
            synced = await bot.tree.sync()
            print(f"✅ 已同步 {len(synced)} 個斜線指令")
        except Exception as e:
            print(f"❌ 同步斜線指令時出錯：{e}")
    except Exception:
        print("on_ready 發生例外：")
        traceback.print_exc()


# ---------- Flask Web 伺服器 ----------
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is running!"


def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)


# ---------- 自動 Ping 自己 ----------
def ping_self():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        print("⚠️ RENDER_EXTERNAL_URL 未設，ping_self 不啟動")
        return

    print(f"🔁 ping_self 啟動，目標：{url}")
    while True:
        try:
            r = requests.get(url, timeout=10)
            print(f"🟢 Ping {url} -> {r.status_code}")
        except Exception as e:
            print(f"🔴 Ping 失敗: {e}")
        time.sleep(300)


# ---------- 啟動多執行緒 ----------
threading.Thread(target=run_flask, daemon=True).start()
threading.Thread(target=ping_self, daemon=True).start()


# ---------- 啟動 Bot ----------
TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()
if not TOKEN:
    print("❌ 未設定 DISCORD_TOKEN 環境變數")
    raise SystemExit(1)

try:
    bot.run(TOKEN)
except Exception:
    print("❌ bot.run 發生錯誤：")
    traceback.print_exc()
    raise
