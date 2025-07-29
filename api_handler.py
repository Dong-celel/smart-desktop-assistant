from openai import OpenAI
from dotenv import load_dotenv
import os
import re
import json

load_dotenv()  # 加载.env

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


def APIHandler(command: str):
    system_prompt = """
你是一个中文智能助手，能根据用户的自然语言需求，自主判断最合适的网址链接并返回。请结合常识、平台特性及用户可能的潜在期望（如官方平台、常用平台优先），灵活匹配需求：

- 若用户有明确内容需求（如“看豫剧视频”“听周杰伦的歌”），请选择最适合该内容的平台（如视频类选常用视频平台，音乐类选主流音乐平台），返回对应平台的搜索页或内容页链接。
- 若用户需求模糊（如“了解深圳”“探究宇宙起源”），请返回能高效获取信息的搜索平台或权威网站链接。
- 若用户明确提及特定网站（如“打开知乎”），直接返回该网站链接。

返回格式为严格JSON，包含“intent”（体现你判断的用户核心意图，如“watch_video”“listen_music”“search_web”“open_website”等）和“url”（完整可用的网址），不添加任何额外说明。

示例1：用户输入“我想看个有名的豫剧视频”，可能返回：
{
  "intent": "watch_video",
  "url": "https://search.bilibili.com/all?keyword=%E9%99%88%E4%B8%96%E7%BE%8E%E5%96%8A%E5%86%A4"
}

示例2：用户输入“想听周杰伦的歌”，可能返回：
{
  "intent": "listen_music",
  "url": "https://music.163.com/#/search/m/?s=%E5%91%A8%E6%9D%B0%E4%BC%A6&type=1"
}

示例3：用户输入“了解深圳”，可能返回：
{
  "intent": "search_web",
  "url": "https://cn.bing.com/search?q=%E6%B7%B1%E5%9C%B3"
}

示例4：用户输入“打开知乎”，返回：
{
  "intent": "open_website",
  "url": "https://www.zhihu.com/"
}

示例5：用户输入“怎么构建网站GitHub”或“GitHub怎么构建网站”，返回：
{
  "intent": "open_website",
  "url": "https://github.com/search?q=%E6%9E%84%E5%BB%BA%E7%BD%91%E7%AB%99&type=repositories"
}

注意：当用户输入中包含特定网站名称时，请优先返回在该网站搜索后的链接。请确保返回的URL是完整的可用链接，且意图明确，参考示例5。
"""

    user_prompt = f"用户输入：{command}"

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2,
        stream=False
    )

    content = response.choices[0].message.content.strip()
    
    # 调试：打印API响应内容
    print(f"[API 响应] {content}")

    try:
        # 提取JSON内容
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            
            # 确保URL格式正确
            url = result.get("url", "")
            if url and not url.startswith("http"):
                url = "https://" + url
            
            return result.get("intent", "unknown"), url
        else:
            print(f"[⚠️] 未找到JSON内容: {content}")
            return "unknown", ""
    except json.JSONDecodeError as e:
        print(f"[⚠️] JSON解析失败: {str(e)}")
        print(f"[原始内容] {content}")
        return "unknown", ""