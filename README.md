# astrbot_plugin_better_markdown_to_image

## 简介
一个更好的Markdown转图片的AstrBot插件，使用chromium渲染由Markdown转换的html以更好地支持数学公式等较为复杂的情景


## 注意事项
- 在运行该插件前请检查 `chromium` 和 `chromedriver` 是否安装，且版本需相同。当然，还要检查是否能正常工作
- 施工中，先写个 `README.md` 计划一下 ~~(没错，就是计划)~~
- 推荐在Linux下使用
- 由于使用了chromium进行渲染，在性能较差的主机上运行可能会比较耗时

## 配置
- 你的chromedriver路径，默认为 `/usr/bin/chromedriver`
- 输出图片大小 (width * height)，默认为 `1200 x 800`
- 背景图片路径，默认为空

## 支持

[帮助文档](https://astrbot.app)
