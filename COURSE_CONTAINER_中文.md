# 使用现有课程容器

Mac 项目位置：`/Users/shenziyigrace/Desktop/CS_316/mini_amazon`
容器内项目位置：`/home/zs193/shared/mini_amazon`
它与 container 目录平级，沿用现有 shared 挂载，不修改 Docker 配置。

在已连接课程容器的 VS Code 终端运行：

```bash
cd ~/shared/mini_amazon
bash setup_course_container.sh
poetry run flask run
```

打开 http://localhost:8080，使用原 skeleton 测试账号 icecream@tastes.good / test123 登录，点击 Cart。

脚本只新建 `mini_amazon_carts_dev` 数据库，安装当前项目依赖并载入小数据集/购物车草案。数据库名已存在或已有 .flaskenv 时会停止，不覆盖它们。没有 DROP DATABASE，不运行原 install.sh / db/setup.sh，不修改课程作业。失败后可能保留未完成的项目数据库；不要直接删库或重复套用 SQL，把错误发回来定位。

项目和作业共享同一 PostgreSQL 服务，但数据库不同；不要运行 docker compose down -v。8080 已由现有容器映射；若被其他应用占用，先检查占用，不强制停止课程服务。

桌面副本的代码已复制，但本次工具限制禁止复制 .git。要保留之前的 Git 分支与历史，请在 **Mac 本机终端**（不是容器终端）执行一次：

```bash
cp -R /Users/shenziyigrace/Documents/Codex/2026-10-02/zhe/outputs/mini_amazon/.git /Users/shenziyigrace/Desktop/CS_316/mini_amazon/.git
```

这条命令只适用于目标尚没有 .git 的当前状态。随后在容器项目目录运行 `git status`，应显示 carts-milestone2 分支及未提交的文件修改。没有推送 GitHub。

检查状态：初始化脚本仅通过 bash 语法检查；因工具无法连接 Docker，尚未在真实容器执行。先前 6 项测试仍为 SQLite 的只读集成测试。
