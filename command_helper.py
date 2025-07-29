import webbrowser
import urllib.parse
from api_handler import APIHandler

def execute_command(command):
    """解析用户输入的命令并执行相应操作"""
    intent, url = APIHandler(command)
    intent = intent.lower()
    
    # 如果有返回的URL，直接使用它
    if url:
        webbrowser.open(url)
        return f"✅ 已打开: {url}"
    
    # 如果没有返回URL，按意图处理
    if intent == "watch_video":
        # 哔哩哔哩搜索
        search_url = f"https://search.bilibili.com/all?keyword={urllib.parse.quote(command)}"
        webbrowser.open(search_url)
        return f"🎬 已为你在哔哩哔哩搜索: {command}"
    
    elif intent == "listen_music":
        # 网易云音乐搜索
        search_url = f"https://music.163.com/#/search/m/?s={urllib.parse.quote(command)}&type=1"
        webbrowser.open(search_url)
        return f"🎵 已为你在网易云搜索: {command}"
    
    elif intent == "open_website":
        # 尝试直接打开
        if "." in command:
            url = command if command.startswith("http") else "https://" + command
            webbrowser.open(url)
            return f"🌐 已尝试打开: {url}"
    
    # 默认使用Bing搜索
    search_url = f"https://cn.bing.com/search?q={urllib.parse.quote(command)}"
    webbrowser.open(search_url)
    return f"🔍 已为你搜索: {command}"