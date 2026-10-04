import csv, json, tempfile, unittest
from pathlib import Path
from contactbook.app import ContactError, add_contact, export_csv, import_csv, load, main

class ContactbookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.path = Path(self.tmp.name) / "contacts.json"
    def tearDown(self): self.tmp.cleanup()

    def test_add_persists_normalized_contact(self):
        c = add_contact(self.path, {"name": " 张三 ", "email": "zhang@example.org", "tags": "客户; 客户;华东"})
        self.assertEqual(c["name"], "张三"); self.assertEqual(c["tags"], ["客户", "华东"])
        self.assertEqual(load(self.path)[0]["email"], "zhang@example.org")

    def test_search_and_tag_filter_via_cli(self):
        add_contact(self.path, {"name": "李明", "company": "北方公司", "tags": ["客户", "北京"]})
        add_contact(self.path, {"name": "王芳", "company": "南方公司", "tags": ["供应商"]})
        self.assertEqual(main(["--data", str(self.path), "list", "北京"]), 0)
        self.assertEqual(main(["--data", str(self.path), "list", "--tag", "供应商"]), 0)

    def test_csv_round_trip(self):
        add_contact(self.path, {"name": "赵六", "email": "zhao@example.org", "tags": ["客户"]})
        out = Path(self.tmp.name) / "out.csv"; self.assertEqual(export_csv(self.path, out), 1)
        other = Path(self.tmp.name) / "other.json"; self.assertEqual(import_csv(other, out), 1)
        self.assertEqual(load(other)[0]["name"], "赵六")

    def test_invalid_csv_is_atomic(self):
        add_contact(self.path, {"name": "已有", "email": "old@example.org"})
        bad = Path(self.tmp.name) / "bad.csv"
        bad.write_text("name,email,phone,company,tags\n好人,good@example.org,,,\n坏人,not-an-email,,,\n", encoding="utf-8")
        before = self.path.read_text(encoding="utf-8")
        with self.assertRaises(ContactError): import_csv(self.path, bad)
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)
        self.assertEqual(len(load(self.path)), 1)

    def test_duplicate_email_rejected(self):
        add_contact(self.path, {"name": "一", "email": "same@example.org"})
        with self.assertRaises(ContactError): add_contact(self.path, {"name": "二", "email": "SAME@example.org"})

    def test_unknown_secret_field_rejected(self):
        with self.assertRaises(ContactError): add_contact(self.path, {"name": "不应保存", "password": "x"})

    def test_corrupt_contact_record_is_rejected_instead_of_dropped(self):
        self.path.write_text('[{"name":"保留"}, null]', encoding="utf-8")
        with self.assertRaisesRegex(ContactError, "不是对象"):
            load(self.path)

    def test_csv_extra_fields_and_duplicate_headers_are_rejected(self):
        for content in (
            "name,email,phone,company,tags\n甲,a@example.org,,,\n乙,b@example.org,,,,EXTRA\n",
            "name,name,email,phone,company,tags\n甲,乙,a@example.org,,,\n",
        ):
            csv_path = Path(self.tmp.name) / "bad.csv"
            csv_path.write_text(content, encoding="utf-8")
            with self.assertRaises(ContactError):
                import_csv(self.path, csv_path)

    def test_export_cannot_overwrite_json_data_file(self):
        add_contact(self.path, {"name": "保留数据", "email": "keep@example.org"})
        original = self.path.read_text(encoding="utf-8")
        with self.assertRaisesRegex(ContactError, "不能与 JSON 数据文件相同"):
            export_csv(self.path, self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), original)

if __name__ == "__main__": unittest.main()
