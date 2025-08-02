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
- 你的chromedriver路径，默认为 `/usr/bin/chromedriver`
- 输出图片大小 (width * height)，默认为 `1200 x 800`
- 背景图片路径，默认为空，不推荐与暗色主体配合
- 主体是否为暗色主体，默认为 `false`

## 计划
- 替换LLM的Markdown输出，直接转成图片防止bot刷屏 ~~(主要是为了美观)~~

## 更新日志
### v1.0
初始版本

## 声明
本项目使用了 `github-markdown-light.css` 和 `github-markdown-dark.css` 作为主题
具体协议见 [github-markdown-light license](https://github.com/sindresorhus/github-markdown-css/blob/main/license)

## 支持

[帮助文档](https://astrbot.app)

[模板来源](https://github.com/Soulter/helloworld)
