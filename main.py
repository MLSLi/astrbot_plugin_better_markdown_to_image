from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from markdown import Markdown

from pygments.formatters import HtmlFormatter

from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.provider import LLMResponse

import astrbot.api.message_components as Comp
import os
import asyncio
import re
import pathlib
import tempfile

class BrowserManager:
    def __init__(self):
        self._browser = None
        self._ref_count = 0
        self._browser_lock = asyncio.Lock()
        self._async_lock = asyncio.Lock()

    async def get_browser(self, config):
        async with self._async_lock:
            if self._browser is None:
                # 配置无头浏览器
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--allow-file-access-from-files")
                chrome_options.add_argument("--disable-web-security")
                chrome_options.add_argument("--allow-running-insecure-content")
                chrome_options.add_argument(f"--window-size={config['output_image_width']},{config['output_image_height']}")
                chrome_options.add_argument(f"--force-device-scale-factor={config['device_scale_factor']}")

                try:
                    loop = asyncio.get_running_loop()
                    self._browser = await loop.run_in_executor(
                        None,
                        lambda: Chrome(
                            service=Service(config['chromedriver_path']),
                            options=chrome_options
                        )
                    )
                    logger.info("浏览器实例已创建")

                except Exception as e:
                    logger.error(f"浏览器启动失败: {str(e)}")
                    raise
            
            self._ref_count += 1
            return self._browser
    
    async def release_browser(self):
        async with self._async_lock:
            self._ref_count = max(0, self._ref_count - 1)
            if self._ref_count == 0 and self._browser is not None:
                try:
                    quit_func = self._browser.quit
                    await asyncio.get_running_loop().run_in_executor(None, quit_func)
                    logger.info("浏览器实例已关闭")

                except Exception as e:
                    logger.error(f"浏览器关闭失败: {str(e)}")

                finally:
                    self._browser = None
    
    async def execute_with_browser(self, config, func):
        """获取浏览器并执行操作"""
        browser = await self.get_browser(config)
        try:
            async with self._browser_lock:
                return await func(browser)
        finally:
            await self.release_browser()
                
    async def shutdown_browser(self):
        """强制关闭浏览器（用于插件终止时）"""
        async with self._async_lock:
            if self._browser is not None:
                try:
                    quit_func = self._browser.quit
                    await asyncio.get_running_loop().run_in_executor(None, quit_func)
                    logger.info("浏览器实例已强制关闭")
                    
                except Exception as e:
                    logger.error(f"浏览器强制关闭失败: {str(e)}")
                    
                finally:
                    self._browser = None
                    self._ref_count = 0

@register("bettermd2img", "MLSLi", "更好的Markdown转图片", "1.2.1")
class MyPlugin(Star):

    def _replace_by_func(self, input_str, prefix, suffix, process_func):
        pattern = re.escape(prefix) + r'(.*?)' + re.escape(suffix)
        compiled_pattern = re.compile(pattern, re.DOTALL)

        def replace_match(match):
            b_str = match.group(1)
            processed_b = process_func(b_str)
            return processed_b
        
        result_str = compiled_pattern.sub(replace_match, input_str)
        return result_str
    
    def _in_block_str(self, text):
        return '<div class="block-math">\\[' + text + '\\]</div>'
    
    def _in_line_str(self, text):
        return '<div class="inline-math">$' + text + '$</div>'
    
    def _extract_md_links(self, text, include_images=True):
        links = []
    
        if include_images:
            pattern = r'\[(?:[^\[\]]|\[[^\[\]]*\])*\]\(([^)\s]+)(?:\s*["\'][^"\']*["\'])?\)'
        else:
            pattern = r'(?<!!)\[(?:[^\[\]]|\[[^\[\]]*\])*\]\(([^)\s]+)(?:\s*["\'][^"\']*["\'])?\)'
    
        links.extend(re.findall(pattern, text))

        ref_pattern = r'^\s*\[[^\]]+\]:\s*(\S+)(?:\s+["\'][^"\']*["\'])?\s*$'
        links.extend(re.findall(ref_pattern, text, re.MULTILINE))
    
        auto_pattern = r'<(https?://[^>]+)>'
        links.extend(re.findall(auto_pattern, text))
    
        if not links:
            return ""

        return self.protect_multiline("所有链接:\n" + '\n'.join(links))
    
    def protect_multiline(self, text):
        lines = text.split('\n')
        protected = [f"\u200b{line}\u200b" for line in lines]
        return '\n'.join(protected)

    def _clean_code_blocks(self, text):
        pattern = r"(\s*)```(\w*)\s*\n([\s\S]*?)\s*```(\s*)"
    
        def replace_match(match):
            lang = match.group(2)
            content = match.group(3).strip()
            logger.info(f"language = {lang}")
            if lang == "latex" or lang == "katex" or lang == "math":
                return f'\n\\[{content}\\]\n'
            elif lang:
                return f"\n```{lang}\n{content}\n```\n"
            else:
                return f"\n```\n{content}\n```\n"
    
        return re.sub(pattern, replace_match, text, flags=re.DOTALL)

    async def _generate_and_send_image(self, text: str, event: AstrMessageEvent, is_llm_response: bool):
        try:
            image_path = await self._browser_manager.execute_with_browser(
                self.browser_config,
                lambda browser: self.mdtext_to_image(text, browser)
            )

            links = self._extract_md_links(text)
            chain = [
                Comp.Image.fromFileSystem(image_path),
            ]

            if self.output_link and links:
                chain.append(Comp.Plain(links))

            # 判断是否是LLM回复
            if is_llm_response: 
                await event.chain_result(chain)
            else:
                yield event.chain_result(chain)

            await asyncio.sleep(10)
            if os.path.exists(image_path):
                os.remove(image_path)

        except Exception as e:
            logger.error(f"处理失败: {str(e)}")
            error_msg = f"转换失败: {str(e)}"

            if is_llm_response:
                await event.send(MessageChain().message(message=error_msg))
            else:
                yield event.plain_result(error_msg)

    async def mdtext_to_image(self, text, browser):
        text = self._clean_code_blocks(text)
        
        html = self.md.convert(text)

        html = self._replace_by_func(html, '<script type="math/tex; mode=display">', '</script>', self._in_block_str)
        html = self._replace_by_func(html, '<script type="math/tex">', '</script>', self._in_line_str)
        
        css_theme_path = self.light_theme_css_path
        if self.is_dark_theme:
            css_theme_path = self.dark_theme_css_path
            
        if self.background_image:
            try:
                # 标准化路径并转义特殊字符
                bg_path = os.path.abspath(self.background_image)
                
                if not os.path.isfile(bg_path):
                    raise ValueError(f"背景图片未找到: {bg_path}")
                
                bg_url = bg_path.replace(" ", "%20")
                html_text = self.html_template.format(css_theme_path, self.html_style, self.code_css_styles, self.script, self.background_template.format(bg_url), html)

            except Exception as e:
                logger.error(f"背景图处理失败: {e}")
                html_text = self.html_template.format(css_theme_path, self.html_style, self.code_css_styles, self.script, "", html)

        else:
            html_text = self.html_template.format(css_theme_path, self.html_style, self.code_css_styles, self.script, "", html)

        logger.info(html_text)

        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".html", delete=False) as f:
            temp_html_path = f.name
            f.write(html_text)
            
        screenshot_path = temp_html_path.replace(".html", ".png")

        try:
            loop = asyncio.get_running_loop()
            
            await loop.run_in_executor(None, browser.get, pathlib.Path(temp_html_path).as_uri())
            
            def wait_for_mathjax(driver):
                try:
                    # 等待 MathJax 完成渲染
                    return driver.execute_script("return typeof MathJax !== 'undefined' && MathJax.typesetPromise && MathJax.typesetPromise.isPending !== true;")
                except:
                    return True
            
            await loop.run_in_executor(None, lambda: WebDriverWait(browser, 10).until(lambda d: wait_for_mathjax(d) or True))
            await asyncio.sleep(0.5)
            
            # 获取文档实际高度
            document_height = await loop.run_in_executor(
                None,
                lambda: browser.execute_script(
                    "return Math.max("
                    "document.body.scrollHeight, "
                    "document.body.offsetHeight, "
                    "document.documentElement.clientHeight, "
                    "document.documentElement.scrollHeight, "
                    "document.documentElement.offsetHeight"
                    ");"
                )
            )
            document_height += self.padding_below

            await loop.run_in_executor(
                None,
                browser.set_window_size,
                self.browser_config['output_image_width'],
                max(document_height, self.output_image_height)
            )

            await asyncio.sleep(0.3)

            await loop.run_in_executor(None, browser.save_screenshot, screenshot_path)

        except Exception as e:
            logger.error(f"转换失败: {str(e)}")
            raise

        finally:
            if os.path.exists(temp_html_path):
                os.remove(temp_html_path)

        return screenshot_path

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        
        self._browser_manager = BrowserManager()

        self.chromedriver_path = config.get("chromedriver_path", "/usr/bin/chromedriver")
        self.output_image_width = config.get("output_image_width", 1200)
        self.output_image_height = config.get("output_image_height", 800)
        self.background_image = config.get("background_image", "")
        self.is_dark_theme = config.get("is_dark_theme", False)
        self.md2img_len_limit = config.get("md2img_len_limit", 100)
        self.padding_below = config.get("padding_below", 50)
        self.device_scale_factor = config.get("device_scale_factor", 1.0)
        self.output_link = config.get("output_link", False)

        self.local_path = os.path.dirname(os.path.realpath(__file__)) + os.sep
        self.light_theme_css_path = self.local_path + "github-markdown-light.css"
        self.dark_theme_css_path = self.local_path + "github-markdown-dark.css"

        self.browser_config = {
            "chromedriver_path": self.chromedriver_path,
            "output_image_width": self.output_image_width,
            "output_image_height": self.output_image_height,
            "device_scale_factor": self.device_scale_factor
        }

        self.pygments_style = 'monokai' if self.is_dark_theme else 'default'

        self.base_styles = HtmlFormatter(style=self.pygments_style).get_style_defs('.codehilite')

        self.md = Markdown(
            extensions=['mdx_math', 'extra', 'tables', 'codehilite'],
            extension_configs={
                'mdx_math': {'enable_dollar_delimiter': True},
                'codehilite': {
                    'guess_lang': False,
                    'pygments_style': self.pygments_style,  # 使用与CSS一致的样式
                    'css_class': 'codehilite'
                }
            }
        )

        self.html_template = """
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link rel="stylesheet" type="text/css" href="{}">
            <style> {} </style>
            <style type="text/css"> {} </style>
            <script> {} </script>
            <script async src="https://cdn.jsdmirror.com/npm/mathjax@3/es5/tex-mml-chtml.js "></script>
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
        
        body { font-family: sans-serif; padding: 20px; }

        @media (max-width: 767px) {
            .markdown-body {
                padding: 15px;
            }
        }

        .inline-math {
            display: inline !important;
            white-space: nowrap;
            vertical-align: middle;
        }

        .block-math {
            display: block;
            margin: 0.5em 0;
            text-align: center;
        }
        """

        self.script = """
        MathJax = {
            tex: {
                inlineMath: [
                    ['$', '$']
                ],
                tags: 'ams'
            }
        };
        """

        self.no_borders = """
        pre, .codehilite, td.linenos, td.linenos .normal, 
        td.linenos .special, span.linenos, span.linenos.special,
        .codehilite .hll, .codehilite table, .codehilite td {
            border-radius: 0 !important;
        }
        .codehilite .err {
            border: none !important;
            background: none !important;
            color: inherit !important;
        }
        """

        self.code_font_style = """
        .codehilite {
            font-family: Consolas, Monaco, 'Andale Mono', 'Ubuntu Mono', monospace !important;
            background: BG;
            border-radius: 0px;
        }
        """
    
        self.override_styles = """
        .codehilite pre, .codehilite code {
            background-color: transparent !important;
        }
        """

        self.code_css_styles = self.base_styles + self.no_borders + self.code_font_style.replace("BG", "#2d2d2d" if self.is_dark_theme else "#f6f8fa") + self.override_styles

    async def initialize(self):
        """插件初始化时预创建浏览器实例"""
        logger.info("正在配置浏览器...")
        await self._browser_manager.get_browser(self.browser_config)

    @filter.command("md2img")
    async def markdown_to_image(self, event: AstrMessageEvent):
        """Markdown转图片指令"""
        user_name = event.get_sender_name()
        message_str = event.message_str
        message_chain = event.get_messages()
        
        pattern = r'^' + re.escape('md2img')
        message_str = re.sub(pattern, '', message_str)
        
        if not message_str:
            yield event.plain_result("请输入要转换的Markdown内容")
            return

        async for result in self._generate_and_send_image(message_str, event, False):
            yield result

    async def terminate(self):
        """插件终止时确保浏览器被关闭"""
        logger.info("正在销毁浏览器...")
        try:
            await self._browser_manager.shutdown_browser()
        except Exception as e:
            logger.error(f"终止时关闭浏览器失败: {e}")

    @filter.on_llm_response()
    async def on_llm_resp(self, event: AstrMessageEvent, resp: LLMResponse):
        """LLM响应后修改成图片形式的消息发送"""
        rawtext = resp.result_chain.chain[0].text
        
        if len(rawtext) > self.md2img_len_limit and self.md2img_len_limit > 0:
            try:
                async for _ in self._generate_and_send_image(rawtext, event, True):
                    return
                event.stop_event()

            except Exception as e:
                logger.error(f"处理失败: {str(e)}")
                msg_chain = MessageChain().message(message=f"处理失败: {str(e)}")
                await event.send(msg_chain)