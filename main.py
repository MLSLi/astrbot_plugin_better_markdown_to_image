from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from markdown import Markdown

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

import time
import os
import asyncio
import re
import pathlib

@register("bettermd2img", "MLSLi", "更好的Markdown转图片", "1.0.0")
class MyPlugin(Star):
    async def mdtext_to_image(self, text):
        html = self.md.convert(text)
        css_theme_path = self.light_theme_css_path
        if self.is_dark_theme:
            css_theme_path = self.dark_theme_css_path
        if self.background_image:
            try:
                # 标准化路径并转义特殊字符
                bg_path = os.path.abspath(self.background_image)
                
                if not os.path.isfile(bg_path):
                    raise ValueError(f"Background image not found: {bg_path}")
                
                bg_url = bg_path.replace(" ", "%20")
                # logger.info(self.background_template.format(bg_url))
                html_text = self.html_template.format(css_theme_path, self.html_style, self.background_template.format(bg_url), html)

            except Exception as e:
                logger.error(f"背景图处理失败: {e}")
                html_text = self.html_template.format(css_theme_path, self.html_style, "", html)  # 降级为无背景

        else:
            html_text = self.html_template.format(css_theme_path, self.html_style, "", html)

        logger.info(html_text)
        temp_html_path = os.path.abspath("temp.html")
        screenshot_path = os.path.abspath("screenshot.png")

        try:
            with open(temp_html_path, "w", encoding="utf-8") as f:
                f.write(html_text)
            self.driver.get(pathlib.Path(temp_html_path).as_uri())

            # 等待 JavaScript 执行完成（根据内容调整等待时间）
            time.sleep(2)  # 对于 MathJax 可能需要更长时间

            # 截图保存
            self.driver.save_screenshot(os.path.abspath(screenshot_path))
        except Exception as e:
            logger.error(f"转换失败: {str(e)}")
            raise
        finally:
            os.remove(temp_html_path)
        return screenshot_path

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        
        self.md = Markdown(
            extensions=['mdx_math', 'extra'],
            extension_configs={
            'mdx_math': {'enable_dollar_delimiter': True}
            }
        ) # Markdown配置，使其支持数学表达式

        self.html_template = """
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link rel="stylesheet" href="{}">
            <style>
            {}
            </style>
            <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
        </head>
        <body {}> 
        <article class="markdown-body">
        {}
        </article>
        </body>
        </html>
        """

        self.background_template = """
        background="{}" style="background-size:100% 100%; background-attachment: fixed;"
        """

        self.html_style = """
        .markdown-body {
            box-sizing: border-box;
            min-width: 200px;
            max-width: 980px;
            margin: 0 auto;
            padding: 45px;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background-color: #fff !important;
        }


        @media (max-width: 767px) {
            .markdown-body {
            padding: 15px;
            }
        }
        """

        self.chromedriver_path = config.get("chromedriver_path", "/usr/bin/chromedriver")
        self.output_image_width = config.get("output_image_width", 1200)
        self.output_image_height = config.get("output_image_height", 800)
        self.background_image = config.get("background_image", "")
        self.is_dark_theme = config.get("is_dark_theme", False)

        self.light_theme_css_path = os.path.dirname(os.path.realpath(__file__)) + os.sep + "github-markdown-light.css"
        self.dark_theme_css_path = os.path.dirname(os.path.realpath(__file__)) + os.sep + "github-markdown-dark.css"

        # 配置无头浏览器
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"--window-size={self.output_image_width},{self.output_image_height}")

        # 初始化浏览器
        chromedriver_path = self.chromedriver_path #指定chromedriver路径
        try:
            self.driver = webdriver.Chrome(service=Service(chromedriver_path), options=chrome_options)
        except Exception as e:
            logger.error(f"浏览器启动失败: {str(e)}")
            raise

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
    
    # Markdown转图片的命令
    @filter.command("md2img")
    async def markdown_to_image(self, event: AstrMessageEvent):
        """Markdown转图片指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 用户发的纯文本消息字符串
        message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)
        
        pattern = r'^' + re.escape('md2img')
        message_str = re.sub(pattern, '', message_str)

        try:
            image_path = await self.mdtext_to_image(message_str)
            yield event.image_result(image_path)

            await asyncio.sleep(10)
            if os.path.exists(image_path):
                os.remove(image_path)

        except Exception as e:
            logger.error(f"处理失败: {str(e)}")
            yield event.plain_result(f"转换失败: {str(e)}")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        self.driver.quit()