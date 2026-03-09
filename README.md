# astrbot_plugin_better_markdown_to_image

## 简介
一个更好的Markdown转图片的AstrBot插件，使用chromium渲染由Markdown文本转换的html以更好地支持数学公式等较为复杂的情景

## 特性

### 平台
私聊和群聊 (仅支持aiocqhttp消息平台)

### 支持的功能
- 亮色/暗色主体切换
- 高度自适应
- 背景图设置
- 大部分Markdown语法

## 使用
- 发送诸如以下的消息格式来使用：`/md2msg [Markdown文本]` (如果你更改了指令前缀，请按照更改后的来)
- bot在LLM回复Markdown消息后自动转换成图片 (注意：字数低于阈值会跳过转换)

## 注意事项
- 在运行该插件前请检查 `chromium` 和 `chromedriver` 是否安装，且版本需相同。当然，还要检查是否能正常工作
- 推荐在Linux环境下使用
- 由于使用了chromium进行渲染，在性能较差的主机上运行可能会比较耗时
- 由于是Markdown文本转图片，故链接之类的标记无法交互
- 暂不支持Markdown的一些语法(如流程图等)
- 若发现自适应高度不起效，请更新requirements中的依赖库至最新版本
- 背景图片建议自行裁剪，不建议在暗色主题时启用

## 配置
| 配置名      | 描述 | 默认值     |
|    :---:    |    :----:   |     :---:     |
| chromedriver_path      | chromedriver路径       | /usr/bin/chromedriver   |
| output_image_width  | 输出图片长度        | 1200      |
| output_image_height| 自适应未启用时的输出图片宽度 | 800 |
| background_image  |  背景图片  | 空   |
| is_dark_theme   |  是否为暗色主题  |  false |
| md2img_len_limit|  LLM输出结果超过多少长度后转为图片|  100 |
| padding_below | 对于生成的图片，自适应时向下填充的像素数 | 50 |
| device_scale_factor | 缩放系数 | 1.0 |
| output_link | 是否输出Markdown内的链接 | false |

## 计划
- 支持更多Markdown语法???

## 更新日志

### v1.2.2
- 紧急修复来自LLM的输出无法转图片的问题
- 修复部分情况下不识别Markdown文本的问题

### v1.2.1
- 修复在部分情况下数学表达式无法识别的问题
- 增加链接提取功能

### v1.2.0
- 丢弃原有的chromium单例，处理速度大幅提升
- 增加配置项device_scale_factor，解决高DPI显示器的显示问题
- main.py的版本号问题(我打错了哈哈)

### v1.1.4
- 在LLM输出的内容转成图片后，不会再次输出原文本
- 再次尝试修复单例的bug

### v1.1.3
- 添加高度自适应，如果超出设置的高度则自动扩展至合适的大小
- 修复代码块在部分条件下未识别的问题

### v1.1.2
- 更改代码字体样式

### v1.1.1
- 修复代码块嵌套在段落内无法识别的问题
- 简化代码逻辑

### v1.1
- 新增代码高亮，根据主题变化自适应
- 修复原markdown库无法跨行识别代码块的问题

### v1.0
初始版本

## 声明
本项目使用了 `github-markdown-light.css` 和 `github-markdown-dark.css` 作为主题
具体协议见 [github-markdown-light license](https://github.com/sindresorhus/github-markdown-css/blob/main/license)

## 支持

[帮助文档](https://astrbot.app)

[模板来源](https://github.com/Soulter/helloworld)

## 资源占用多，有bug?
你可以尝试这个插件：
[无浏览器版](https://github.com/luosheng520qaq/astrbot_plugin_nobrowser_markdown_to_pic)
