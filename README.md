# astrbot_plugin_better_markdown_to_image

## 简介
一个更好的Markdown转图片的AstrBot插件，使用chromium渲染由Markdown转换的html以更好地支持数学公式等较为复杂的情景，支持私聊和群聊 (暂时仅支持aiocqhttp消息平台)，支持亮色/暗色主体切换

## 使用
发送诸如以下的消息格式来使用：`/md2msg [Markdown文本]`
或者可以让bot发送Markdown消息时自动转换

## 注意事项
- 在运行该插件前请检查 `chromium` 和 `chromedriver` 是否安装，且版本需相同。当然，还要检查是否能正常工作
- 推荐在Linux下使用
- 由于使用了chromium进行渲染，在性能较差的主机上运行可能会比较耗时

## 配置
| 配置名      | 描述 | 默认值     |
|    :---:    |    :----:   |     :---:     |
| chromedriver_path      | chromedriver路径       | /usr/bin/chromedriver   |
| output_image_width  | 输出图片长度        | 1200      |
| output_image_height| 输出图片宽度 | 800|
| background_image  |  背景图片  |空   |
| is_dark_theme   |  是否为暗色主题  |  false|
| md2img_len_limit|  LLM输出结果超过字数超过多少后转为图片|  100|
## 计划
- 支持代码高亮 ~~不过得等一段时间~~

## 更新日志
### v1.0
初始版本

## 声明
本项目使用了 `github-markdown-light.css` 和 `github-markdown-dark.css` 作为主题
具体协议见 [github-markdown-light license](https://github.com/sindresorhus/github-markdown-css/blob/main/license)

## 支持

[帮助文档](https://astrbot.app)

[模板来源](https://github.com/Soulter/helloworld)
