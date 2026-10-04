# Contactbook

Contactbook 是一个**本地、隐私优先的联系人管理 CLI**，专门处理姓名、电子邮箱、电话、公司和标签等常规联系人信息。它不提供也不接受密码、令牌、密钥、身份证号等秘密或高敏感字段。

## 功能边界

- 新增联系人，并对姓名、邮箱、字段长度和重复邮箱校验。
- 在姓名、邮箱、电话、公司及标签中搜索；按标签筛选。
- CSV 导入/导出。导入会先读取并校验**全部**行，确认表头、字段数、格式和邮箱不重复后才一次性原子写入；失败不会改变原文件。
- JSON 数据文件和 CSV 导出都使用临时文件及原子替换；CSV 导出拒绝覆盖 JSON 数据文件本身。
- 单机本地工具，不同步、不联网、不提供多用户权限、加密或冲突合并。

## 要求与安装

需要 Python **3.10 或更高版本**，运行时仅使用 Python 标准库，无第三方运行依赖。

```bash
python -m pip install .
contactbook --help
# 开发时可用 python -m pip install -e .
```

默认数据文件是 `~/.contactbook/contacts.json`。建议在脚本、测试或不同项目中显式指定 `--data PATH`（`--db` 是同义参数），也可设置 `CONTACTBOOK_DATA` 环境变量；命令行参数优先于环境变量。

## 完整 CLI 示例

```bash
contactbook --data ./contacts.json add \
  --name "李明" --email li.ming@example.org --phone "+86-138-0000-0000" \
  --company "示例科技" --tag 客户 --tag 华东

contactbook --data ./contacts.json list
contactbook --data ./contacts.json search "示例"
contactbook --data ./contacts.json list --tag 客户
contactbook --data ./contacts.json export ./contacts-backup.csv
contactbook --data ./contacts.json import ./examples/contacts.csv
```

错误会写到标准错误并以状态码 2 退出，例如缺少姓名、邮箱格式不正确、CSV 表头/字段数错误、重复邮箱或文件不可读时均会明确报错。

## 全部命令参数

全局参数必须放在子命令前：

- `--data PATH` / `--db PATH`：指定 JSON 数据文件；缺省读取 `CONTACTBOOK_DATA`，再缺省为 `~/.contactbook/contacts.json`。

子命令：

- `add`：`--name NAME`（必填）、`--email EMAIL`、`--phone PHONE`、`--company COMPANY`、`--tag TAG`（可重复）。
- `list`：可选位置参数 `QUERY`，以及 `--tag TAG`。`search QUERY` 是 `list QUERY` 的别名形式。
- `import CSV_FILE`：导入 CSV，必须一次性通过全部验证。
- `export CSV_FILE`：原子写出所有联系人 CSV；会替换现有 CSV，但拒绝把 JSON 数据文件本身作为目标。

可用 `contactbook COMMAND --help` 查看 argparse 帮助。

## 数据格式

JSON 是联系人数组，每项固定包含以下字段：

```json
[{"name":"示例联系人","email":"example@example.org","phone":"+86-10-12345678","company":"示例公司","tags":["客户","北京"]}]
```

CSV 必须包含且仅包含表头 `name,email,phone,company,tags`；`tags` 使用分号分隔，例如 `客户;北京`。姓名必填，邮箱非空时要求基本 `name@domain.tld` 形式；标签会去空格并去重。额外列、重复表头或多出的行字段会被拒绝。

## 隐私与安全限制

数据只写入用户指定的本地路径，不调用外部服务；示例文件不含个人数据。请自行设置数据文件权限并谨慎备份。软件不存储密码、令牌、API key、凭据或其他秘密字段，也不声称提供静态加密。原子替换不能防止磁盘损坏、恶意进程或同时写入者造成的问题。

## 开发与测试

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

测试使用 `tempfile.TemporaryDirectory`，覆盖新增/持久化、搜索和标签筛选、CSV 导入导出、全量校验失败不落盘、重复邮箱、损坏 JSON、额外列及防止导出覆盖 JSON。

## 许可证

MIT，见 [LICENSE](LICENSE)。
