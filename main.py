from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from markdown import Markdown
from markdown.extensions import Extension
from markdown.blockprocessors import BlockProcessor


from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import guess_lexer

from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.provider import LLMResponse

import xml.etree.ElementTree as etree

import os
import asyncio
import re
import pathlib
import threading
import tempfile
import html

class BrowserManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._browser = None
                cls._instance._ref_count = 0
                cls._instance._browser_lock = asyncio.Lock()
                cls._instance._async_lock = asyncio.Lock()
            return cls._instance
    
    async def get_browser(self, config):
        async with self._async_lock:
            if self._browser is None:
                # 配置无头浏览器
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument(f"--window-size={config['output_image_width']},{config['output_image_height']}")

                try:
                    loop = asyncio.get_running_loop()
                    self._browser = await loop.run_in_executor(
                        None,
                        lambda: Chrome(
                            service = Service(config['chromedriver_path']),
                            options = chrome_options
                        )
                    )
                    logger.info("浏览器实例已创建")

                except Exception as e:
                    logger.error(f"浏览器启动失败: {str(e)}")
                    raise
            
            self._ref_count += 1  # 增加引用计数
            return self._browser
    
    async def release_browser(self):
        async with self._async_lock:
            self._ref_count = max(0, self._ref_count - 1)
            if self._ref_count == 0 and self._browser is not None:
                try:
                    await asyncio.get_running_loop().run_in_executor(
                        None, 
                        self._browser.quit()
                    )
                    logger.info("浏览器实例已关闭")

                except Exception as e:
                    logger.error(f"浏览器关闭失败: {str(e)}")

                finally:
                    self._browser = None
    
    async def execute_with_browser(self, config, func):
        # 获取浏览器实例锁，确保同一时间只有一个任务使用浏览器
        browser = await self.get_browser(config)
        try:
            async with self._browser_lock:
                return await func(browser)
        finally:
            await self.release_browser() # 确保释放资源
                
    async def shutdown_browser(self):
        async with self._async_lock:
            if self._browser is not None:
                try:
                    await asyncio.get_running_loop().run_in_executor(
                        None, 
                        self._browser.quit()
                    )
                    logger.info("浏览器实例已关闭")
                    
                except Exception as e:
                    logger.error(f"浏览器关闭失败: {str(e)}")
                    
                finally:
                    self._browser = None
                    self._ref_count = 0

class EscapedCodeBlockProcessor(BlockProcessor):
    """正确处理多行代码块，包括完整识别代码块结束标记"""
    RE_FENCE_START = r'^ {0,3}(`{3,}|~{3,})[ ]*([\w-]*)?[ ]*\n'
    
    def test(self, parent, block):
        return re.match(self.RE_FENCE_START, block)
    
    def run(self, parent, blocks):
        original_block = blocks[0]
        start_match = re.match(self.RE_FENCE_START, original_block)
        
        if not start_match:
            return False
            
        # 提取起始标记和语言类型
        start_fence = start_match.group(1)
        lang_type = start_match.group(2) or ''
        # 结束标记必须与起始标记使用相同的字符
        end_pattern = r'^ {0,3}' + re.escape(start_fence) + r'[ ]*$'
        
        # 移除起始行，保留内容
        content_lines = original_block[start_match.end():].split('\n')
        found_end = False
        code_lines = []
        
        # 首先处理原始块中的内容
        for i, line in enumerate(content_lines):
            line_stripped = line.strip()
            if line_stripped.startswith(start_fence) and re.match(end_pattern, line_stripped):
                # 处理同一块内的结束标记
                found_end = True
                break
            code_lines.append(line)
        
        # 如果原始块中没找到结束标记，检查后续块
        block_index = 1
        while not found_end and block_index < len(blocks):
            block_lines = blocks[block_index].split('\n')
            for j, line in enumerate(block_lines):
                line_stripped = line.strip()
                if line_stripped.startswith(start_fence) and re.match(end_pattern, line_stripped):
                    found_end = True
                    # 保存结束标记之后的内容
                    remaining_lines = '\n'.join(block_lines[j+1:])
                    if remaining_lines:
                        # 将剩余内容放回块中
                        blocks[block_index] = remaining_lines
                    else:
                        # 删除空块
                        del blocks[block_index]
                    break
                code_lines.append(line)
            
            if found_end:
                break
                
            block_index += 1
        
        # 处理结束标记未找到的情况
        if not found_end:
            # 恢复原始块，视为普通文本
            blocks[0] = original_block
            return False
        
        # 删除已处理的块
        del blocks[0]  # 移除原始块
        for i in range(1, block_index):
            del blocks[0]  # 移除已处理的后续块
        
        # 合并代码内容
        full_code = '\n'.join(code_lines).rstrip('\n')
        escaped_code = html.escape(full_code)
        
        # 创建容器并添加转义后的代码
        container = etree.SubElement(parent, 'div')
        container.set('class', 'custom-code-container')
        pre = etree.SubElement(container, 'pre')
        if lang_type:
            pre.set('class', f'language-{lang_type}')
        code_elem = etree.SubElement(pre, 'code')
        code_elem.text = escaped_code + '\n'
        
        return True

class EscapedCodeExtension(Extension):
    """Markdown 扩展：正确处理带结束标记的代码块"""
    def extendMarkdown(self, md):
        # 注册处理器，优先级高于标准代码块处理器
        md.parser.blockprocessors.register(
            EscapedCodeBlockProcessor(md.parser), 
            'escaped_code', 
            115
        )

@register("bettermd2img", "MLSLi", "更好的Markdown转图片", "1.1")
class MyPlugin(Star):

    _browser_manager = BrowserManager()

    def _replace_by_func(self, input_str, prefix, suffix, process_func):
        pattern = re.escape(prefix) + r'(.*?)' + re.escape(suffix)
        compiled_pattern = re.compile(pattern, re.DOTALL)

        def replace_match(match):
            b_str = match.group(1)
            processed_b = process_func(b_str)
            return processed_b
        
        result_str = compiled_pattern.sub(replace_match, input_str)
        return result_str

    def _code_highlighting(self, code):
        code = html.unescape(code)
        lexer = guess_lexer(code)
        highlighted_html = highlight(code, lexer, self.formatter)
 
        return highlighted_html
    
    def _in_block_str(self, text):
        return '<div class="block-math">\\[' + text + '\\]</div>'
    
    def _in_line_str(self, text):
        return '<div class="inline-math">$' + text + '$</div>'

    async def _generate_and_send_image(self, text: str, event: AstrMessageEvent, is_llm_response: bool):
        try:
            image_path = await self._browser_manager.execute_with_browser(
            self.browser_config,
            lambda browser: self.mdtext_to_image(text, browser)
            )
            # 判断是否是LLM回复
            if is_llm_response: 
                await event.send(MessageChain().file_image(path=image_path))
            else:
                yield event.image_result(image_path)

            await asyncio.sleep(10)
            if os.path.exists(image_path):
                os.remove(image_path)

        except Exception as e:
            logger.error(f"处理失败: {str(e)}")
            error_msg = f"转换失败: {str(e)}"

            if is_llm_response:
                await event.send(MessageChain().message(message = error_msg))
            else:
                yield event.plain_result(error_msg)

    async def mdtext_to_image(self, text, browser):
        html = self.md.convert(text)
        html = self._replace_by_func(html, '<code>', '</code>', self._code_highlighting)
        html = self._replace_by_func(html, '<script type="math/tex; mode=display">', '</script>', self._in_block_str)
        html = self._replace_by_func(html, '<script type="math/tex">', '</script>', self._in_line_str)
        logger.info(html)
        
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
                # logger.info(self.background_template.format(bg_url))
                html_text = self.html_template.format(css_theme_path, self.html_style, self.code_css_styles, self.script, self.background_template.format(bg_url), html)

            except Exception as e:
                logger.error(f"背景图处理失败: {e}")
                html_text = self.html_template.format(css_theme_path, self.html_style, self.code_css_styles, self.script, "", html)  # 降级为无背景

        else:
            html_text = self.html_template.format(css_theme_path, self.html_style, self.code_css_styles, self.script, "", html)

        logger.info(html_text)

        with tempfile.NamedTemporaryFile(mode = "w", encoding = "utf-8", suffix = ".html", delete = False) as f:
                temp_html_path = f.name
                f.write(html_text)
            
        screenshot_path = temp_html_path.replace(".html", ".png")

        try:
            browser.get(pathlib.Path(temp_html_path).as_uri())

            # 等待 JavaScript 执行完成（根据内容调整等待时间）
            await asyncio.sleep(2)  # 对于 MathJax 可能需要更长时间

            # 截图保存
            browser.save_screenshot(screenshot_path)

        except Exception as e:
            logger.error(f"转换失败: {str(e)}")
            raise

        finally:
            if os.path.exists(temp_html_path):
                os.remove(temp_html_path)

        return screenshot_path

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        
        self.md = Markdown(
            extensions = ['mdx_math', 'extra', 'tables', 'codehilite', EscapedCodeExtension()],
            extension_configs = {
            'mdx_math': {'enable_dollar_delimiter': True},
            'codehilite': {
                'guess_lang': False,  # 禁用自动语言检测
                'pygments_style': 'monokai'  # 设置代码高亮样式
                }
            }
        ) # Markdown配置，使其支持数学表达式

        self.html_template = """
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link rel="stylesheet" type="text/css" href="{}">
            <style> {} </style>
            <style type="text/css"> {} </style>
            <script> {} </script>
            <script async src="https://cdn.jsdmirror.com/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
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
            ['$', '$']         // 支持 $...$
            ],
            tags: 'ams'  // 启用\tag{}
            }
        };
        """

        self.no_boaders = """
        pre, .highlight, td.linenos, td.linenos .normal, 
        td.linenos .special, span.linenos, span.linenos.special,
        .highlight .hll, .highlight table, .highlight td {
            border: none !important;
            background: none !important;
            box-shadow: none !important;
            border-radius: 0 !important;
        }
        .highlight .err {
        border: none !important;
        background: none !important;
        color: inherit !important;
        }
        """
        # 一堆html样式和模板，没错，是魔法强力胶！

        self.chromedriver_path = config.get("chromedriver_path", "/usr/bin/chromedriver")
        self.output_image_width = config.get("output_image_width", 1200)
        self.output_image_height = config.get("output_image_height", 800)
        self.background_image = config.get("background_image", "")
        self.is_dark_theme = config.get("is_dark_theme", False)
        self.md2img_len_limit = config.get("md2img_len_limit", 100)
        # 一堆配置
        self.local_path = os.path.dirname(os.path.realpath(__file__)) + os.sep
        self.light_theme_css_path = self.local_path + "github-markdown-light.css"
        self.dark_theme_css_path = self.local_path + "github-markdown-dark.css"
        # 获取文件绝对路径
        self.browser_config = {
            "chromedriver_path": self.chromedriver_path,
            "output_image_width": self.output_image_width,
            "output_image_height": self.output_image_height
        }
        # 浏览器配置
        self.formatter = HtmlFormatter(linenos=False, cssclass = "highlight", style = "github-dark" if self.is_dark_theme else "default")
        self.code_css_styles = HtmlFormatter().get_style_defs('.highlight') + self.no_boaders
        # 代码高亮

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        await self._browser_manager.get_browser(self.browser_config)

    # Markdown转图片的命令
    @filter.command("md2img")
    async def markdown_to_image(self, event: AstrMessageEvent):
        """Markdown转图片指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 用户发的纯文本消息字符串
        message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        # logger.info(message_chain)
        
        pattern = r'^' + re.escape('md2img')
        message_str = re.sub(pattern, '', message_str)
        # 去掉指令开头内容
        if not message_str:
            yield event.plain_result("请输入要转换的Markdown内容")
            return

        async for result in self._generate_and_send_image(message_str, event, False):
            yield result

    async def terminate(self):
        await self._browser_manager.shutdown_browser()
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""

    @filter.on_llm_response()
    async def on_llm_resp(self, event: AstrMessageEvent, resp: LLMResponse):
        """LLM响应后修改成图片形式的消息发送"""
        rawtext = resp.result_chain.chain[0].text
        # logger.info(rawtext)
        
        if len(rawtext) > self.md2img_len_limit and self.md2img_len_limit > 0:
            try:
                async for _ in self._generate_and_send_image(rawtext, event, True):
                    pass  # 不需要处理生成器产生的值

            except Exception as e:
                logger.error(f"处理失败: {str(e)}")
                msg_chain = MessageChain().message(message = f"处理失败: {str(e)}")

                await event.send(msg_chain)
        else:
            pass
