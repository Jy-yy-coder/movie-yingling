# -*- coding: utf-8 -*-
"""赛前审查修复的回归：身份合并、无剧透推荐、标题路由、鉴权边角。"""
from __future__ import annotations
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cine import chat as chat_mod
from cine import data
from cine import recommend as rec_mod


def _offline_llm():
    import cine.llm as llm_mod
    llm_mod.chat_reply = lambda *a, **k: (None, None)


class TestTitleAndSpoiler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data.load()
        _offline_llm()

    def test_huozhe_spoken_not_hijacked(self):
        r = chat_mod.build_reply("活着好累啊想看治愈点的", spoiler=True)
        self.assertEqual(r["kind"], "recommend")

    def test_newyear_spoken_not_hijacked(self):
        r = chat_mod.build_reply("过年了推荐几部全家看的", spoiler=True)
        self.assertEqual(r["kind"], "recommend")

    def test_xiangkan_named_title_is_movie(self):
        r = chat_mod.build_reply("想看肖申克的救赎", spoiler=True)
        self.assertEqual(r["kind"], "movie")
        self.assertTrue(r.get("movie_id"))

    def test_baawang_qa_is_movie(self):
        r = chat_mod.build_reply("霸王别姬讲什么", spoiler=True)
        self.assertEqual(r["kind"], "movie")

    def test_similar_quoted_is_recommend(self):
        r = chat_mod.build_reply("推荐类似《霸王别姬》的", spoiler=True)
        self.assertEqual(r["kind"], "recommend")

    def test_quoted_title_qa_still_movie(self):
        r = chat_mod.build_reply("《活着》讲什么", spoiler=True)
        self.assertEqual(r["kind"], "movie")

    def test_spoiler_recommend_has_no_plot_blurb(self):
        r = chat_mod.build_reply("推荐一部燃的科幻片", spoiler=True)
        self.assertEqual(r["kind"], "recommend")
        self.assertNotIn("简介", r.get("text") or "")
        facts = chat_mod._movie_card(
            data.movie(r["movies"][0]["movie_id"]), safe=True)
        self.assertNotIn("简介", facts)

    def test_parents_hint_is_family(self):
        h = rec_mod.parse_hint("有没有适合带父母一起看的")
        self.assertEqual(h["genre"], "家庭")
        self.assertEqual(h["dim"], "情感")
        ms = rec_mod.recommend("有没有适合带父母一起看的", limit=4)
        self.assertTrue(ms)
        self.assertTrue(all("家庭" in (m.get("genres") or []) for m in ms))

    def test_wenyi_rainy_not_global_top(self):
        h = rec_mod.parse_hint("适合下雨天窝沙发看的文艺片")
        self.assertEqual(h["dim"], "情感")
        ids = [m["movie_id"] for m in rec_mod.recommend("适合下雨天窝沙发看的文艺片", limit=4)]
        self.assertNotIn("1293182", ids)  # 十二怒汉不应再因「无意图」霸榜

    def test_tearjerker_jp_anime_ranks_emotion(self):
        h = rec_mod.parse_hint("推荐一部催泪的日本动画")
        self.assertEqual((h["genre"], h["region"], h["dim"]), ("动画", "日本", "情感"))
        titles = [m["title"] for m in rec_mod.recommend("推荐一部催泪的日本动画", limit=4)]
        self.assertTrue(any("千与千寻" in t or "龙猫" in t for t in titles))


class TestAuthMerge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import cine.main as main
        cls._main = main
        cls.db = Path(tempfile.mkdtemp()) / "cine_test.db"
        main.DB_PATH = cls.db
        main._init_db()
        data.load()
        _offline_llm()
        from fastapi.testclient import TestClient
        cls.client = TestClient(main.app, raise_server_exceptions=True)

    def _phone(self, suffix: str) -> str:
        return ("138" + suffix.zfill(8))[:11]

    def _sms_code(self, phone: str) -> str:
        r = self.client.post("/api/auth/sms", json={"phone": phone})
        self.assertEqual(r.status_code, 200, r.text)
        m = re.search(r"(\d{6})", r.json().get("message") or "")
        self.assertTrue(m, r.text)
        return m.group(1)

    def test_spa_hosted(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)

    def test_sms_no_dev_code_field(self):
        r = self.client.post("/api/auth/sms", json={"phone": self._phone("10000001")})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertNotIn("dev_code", body)
        self.assertRegex(body.get("message") or "", r"\d{6}")

    def test_sms_replay_rejected(self):
        phone = self._phone("10000002")
        code = self._sms_code(phone)
        ok = self.client.post("/api/auth/register", json={
            "phone": phone, "code": code, "password": "123456", "device_id": "d_reg_a",
        })
        self.assertEqual(ok.status_code, 200, ok.text)
        again = self.client.post("/api/auth/register", json={
            "phone": phone, "code": code, "password": "123456", "device_id": "d_reg_a",
        })
        self.assertEqual(again.status_code, 400)

    def test_login_merges_guest_and_chat_stays_on_account(self):
        items = self.client.get("/api/movies?limit=1").json()["items"]
        self.assertTrue(items)
        mid = items[0]["movie_id"]

        phone = self._phone("10000003")
        code = self._sms_code(phone)
        acc = self.client.post("/api/auth/register", json={
            "phone": phone, "code": code, "password": "123456", "device_id": "d_acct",
        }).json()
        uid = acc["user_id"]

        guest = self.client.post("/api/auth/guest", json={"device_id": "d_guest"}).json()
        fav = self.client.post(
            f"/api/favorites?token={guest['token']}", json={"movie_id": mid})
        self.assertEqual(fav.status_code, 200, fav.text)

        login = self.client.post("/api/auth/login", json={
            "phone": phone, "password": "123456", "device_id": "d_guest",
        })
        self.assertEqual(login.status_code, 200, login.text)
        body = login.json()
        self.assertTrue(body["merged"])
        tok = body["token"]

        chat = self.client.post("/api/chat", json={
            "message": "你好", "device_id": "d_guest", "token": tok, "spoiler": True,
        })
        self.assertEqual(chat.status_code, 200, chat.text)

        con = sqlite3.connect(self.db)
        try:
            chats = con.execute(
                "SELECT COUNT(*) FROM chats WHERE user_id=?", (uid,)).fetchone()[0]
            self.assertGreater(chats, 0)
            leftover = con.execute(
                "SELECT id FROM users WHERE device_id=? AND phone IS NULL",
                ("d_guest",)).fetchall()
            self.assertEqual(leftover, [])
            favs = con.execute(
                "SELECT movie_id FROM favorites WHERE user_id=?", (uid,)).fetchall()
            self.assertIn((mid,), favs)
        finally:
            con.close()

    def test_login_merged_false_without_guest(self):
        phone = self._phone("10000004")
        code = self._sms_code(phone)
        self.client.post("/api/auth/register", json={
            "phone": phone, "code": code, "password": "123456", "device_id": "d_only",
        })
        login = self.client.post("/api/auth/login", json={
            "phone": phone, "password": "123456", "device_id": "d_never_guest",
        })
        self.assertEqual(login.status_code, 200, login.text)
        self.assertFalse(login.json()["merged"])

    def test_guest_does_not_overwrite_registered_token(self):
        phone = self._phone("10000005")
        code = self._sms_code(phone)
        acc = self.client.post("/api/auth/register", json={
            "phone": phone, "code": code, "password": "123456", "device_id": "d_same",
        }).json()
        stolen = self.client.post("/api/auth/guest", json={"device_id": "d_same"})
        self.assertEqual(stolen.status_code, 200)
        me = self.client.get(f"/api/account?token={acc['token']}")
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["id"], acc["user_id"])


if __name__ == "__main__":
    unittest.main()
