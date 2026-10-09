# 课程容器运行说明

项目在 Mac 的 Desktop/CS_316/mini_amazon，对应容器内 /home/zs193/shared/mini_amazon。

在现有课程 Ubuntu 容器终端中：

```bash
cd ~/shared/mini_amazon
poetry install --no-root
poetry run python -m unittest discover -s tests -v
DB_NAME=mini_amazon_m2_verify_aligned_20261008 poetry run flask run --host 0.0.0.0 --port 8080
```

上面的数据库在本次本机验证时创建，队友的新环境需要自行创建空库和载入数据；详见 docs/milestone2/交给队友_中文.md。示例登录为 icecream@tastes.good / test123。

setup_course_container.sh 只适合尚无 .flaskenv 和 mini_amazon_carts_dev 的新环境；已有库会停止，不能当作更新脚本反复执行。原 install.sh / db/setup.sh 包含重建数据库操作，已有数据时不要直接执行。

旧 Carts 表升级使用 db/migrate_carts_m2_contract.sql，先备份、审查后运行一次。端口 8080 已占用时先确认旧服务器，勿停止其他同学或作业的服务。
