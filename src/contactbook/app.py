"""Contactbook: local contact management with validated atomic storage."""
from __future__ import annotations
import argparse, csv, json, os, re, sys, tempfile
from pathlib import Path
from typing import Any

FIELDS = ("name", "email", "phone", "company", "tags")
_HEADER = "name,email,phone,company,tags"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class ContactError(ValueError):
    pass

def data_path(value: str | None) -> Path:
    return Path(value or os.environ.get("CONTACTBOOK_DATA", "~/.contactbook/contacts.json")).expanduser()

def clean_tags(value: Any) -> list[str]:
    if isinstance(value, str): parts = value.split(";")
    elif isinstance(value, list): parts = value
    elif value is None: parts = []
    else: raise ContactError("标签必须是分号分隔文本或数组")
    tags = []
    for part in parts:
        tag = str(part).strip()
        if tag and tag not in tags: tags.append(tag)
    return tags

def validate_contact(raw: dict[str, Any], *, allow_missing_name: bool = False) -> dict[str, Any]:
    unknown = set(raw) - set(FIELDS)
    if unknown: raise ContactError("不支持的字段: " + ", ".join(sorted(unknown)))
    name = str(raw.get("name") or "").strip()
    if not name and not allow_missing_name: raise ContactError("姓名不能为空")
    email = str(raw.get("email") or "").strip()
    if email and not _EMAIL.fullmatch(email): raise ContactError(f"邮箱格式无效: {email}")
    phone = str(raw.get("phone") or "").strip()
    company = str(raw.get("company") or "").strip()
    if len(name) > 200 or len(email) > 320 or len(phone) > 80 or len(company) > 200: raise ContactError("字段长度超过限制")
    return {"name": name, "email": email, "phone": phone, "company": company, "tags": clean_tags(raw.get("tags"))}

def load(path: Path) -> list[dict[str, Any]]:
    if not path.exists(): return []
    try: obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e: raise ContactError(f"无法读取数据文件: {e}")
    if not isinstance(obj, list): raise ContactError("数据文件必须是联系人数组")
    contacts = []
    for index, item in enumerate(obj, 1):
        if not isinstance(item, dict): raise ContactError(f"第 {index} 条联系人记录不是对象")
        contacts.append(validate_contact(item))
    return contacts

def save(path: Path, contacts: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(contacts, ensure_ascii=False, indent=2) + "\n"
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    except Exception:
        try: os.unlink(temp)
        except OSError: pass
        raise

def add_contact(path: Path, raw: dict[str, Any]) -> dict[str, Any]:
    c = validate_contact(raw)
    contacts = load(path)
    if c["email"] and any(x["email"].casefold() == c["email"].casefold() for x in contacts):
        raise ContactError("该邮箱已存在，拒绝重复联系人")
    contacts.append(c); save(path, contacts); return c

def import_csv(path: Path, csv_path: Path) -> int:
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            if len(headers) != len(set(headers)) or set(headers) != set(FIELDS):
                raise ContactError("CSV 表头必须恰好包含且只包含: " + _HEADER)
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as e: raise ContactError(f"无法读取 CSV: {e}")
    if not rows: raise ContactError("CSV 没有联系人数据")
    if any(None in row for row in rows): raise ContactError("CSV 行包含多于表头的字段")
    incoming = [validate_contact(dict(r)) for r in rows]
    emails = [x["email"].casefold() for x in incoming if x["email"]]
    if len(emails) != len(set(emails)): raise ContactError("CSV 内有重复邮箱，未导入")
    old = load(path); old_emails = {x["email"].casefold() for x in old if x["email"]}
    if old_emails & set(emails): raise ContactError("CSV 与现有联系人有重复邮箱，未导入")
    save(path, old + incoming); return len(incoming)

def export_csv(path: Path, out: Path) -> int:
    contacts = load(path)
    if out.expanduser().resolve() == path.expanduser().resolve():
        raise ContactError("导出目标不能与 JSON 数据文件相同")
    out = out.expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{out.name}.", dir=str(out.parent), text=True)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
            for c in contacts: w.writerow({**c, "tags": ";".join(c["tags"])})
            f.flush(); os.fsync(f.fileno())
        os.replace(temporary, out)
    except OSError as e: raise ContactError(f"无法写出 CSV: {e}")
    finally:
        try: os.unlink(temporary)
        except FileNotFoundError: pass
    return len(contacts)

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="contactbook", description="本地隐私优先的联系人管理工具")
    p.add_argument("--data", "--db", metavar="PATH", help="JSON 数据文件（也可用 CONTACTBOOK_DATA）")
    sp = p.add_subparsers(dest="command", required=True)
    a = sp.add_parser("add", help="新增联系人")
    for n in FIELDS[:-1]: a.add_argument(f"--{n}", required=(n == "name"))
    a.add_argument("--tag", action="append", default=[], help="标签，可重复指定")
    l = sp.add_parser("list", aliases=["search"], help="列出或搜索联系人")
    l.add_argument("query", nargs="?", help="在姓名、邮箱、电话、公司、标签中搜索")
    l.add_argument("--tag", help="只显示包含该标签的联系人")
    i = sp.add_parser("import", help="校验全部 CSV 后一次性导入")
    i.add_argument("csv_file", type=Path)
    e = sp.add_parser("export", help="导出全部联系人为 CSV")
    e.add_argument("csv_file", type=Path)
    return p

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv); path = data_path(args.data)
    try:
        if args.command == "add":
            c = add_contact(path, {n: getattr(args, n, "") for n in FIELDS[:-1]} | {"tags": args.tag})
            print(f"已添加: {c['name']}")
        elif args.command in ("list", "search"):
            cs = load(path); q = (args.query or "").casefold()
            for c in cs:
                text = " ".join([c["name"], c["email"], c["phone"], c["company"], *c["tags"]]).casefold()
                if (not q or q in text) and (not args.tag or args.tag in c["tags"]): print(f"{c['name']} | {c['email']} | {c['phone']} | {c['company']} | {', '.join(c['tags'])}")
            print(f"共 {sum(1 for c in cs if (not q or q in ' '.join([c['name'],c['email'],c['phone'],c['company'],*c['tags']]).casefold()) and (not args.tag or args.tag in c['tags']))} 条")
        elif args.command == "import": print(f"已导入 {import_csv(path, args.csv_file)} 条联系人")
        elif args.command == "export": print(f"已导出 {export_csv(path, args.csv_file)} 条联系人")
        return 0
    except (ContactError, OSError) as e:
        print(f"错误: {e}", file=sys.stderr); return 2

if __name__ == "__main__": raise SystemExit(main())
