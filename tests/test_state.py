"""
state.py のユニットテスト
ファイルI/Oと diff ロジックをテストする
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

import state


class TestLoad:
    """load 関数のテストクラス"""

    def test_存在するJSONファイルを正しく読み込む(self, tmp_path):
        """正常なJSONファイルを読み込めること"""
        data = {"JR山手線": {"state": "遅延", "detail": "詳細"}}
        p = tmp_path / "state.json"
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        result = state.load(p)
        assert result == data

    def test_ファイルが存在しない場合は空辞書を返す(self, tmp_path):
        """存在しないパスを渡したとき空辞書が返ること"""
        result = state.load(tmp_path / "nonexistent.json")
        assert result == {}

    def test_不正なJSONの場合は空辞書を返す(self, tmp_path):
        """破損したJSONファイルのとき空辞書が返ること"""
        p = tmp_path / "state.json"
        p.write_text("{invalid json", encoding="utf-8")

        result = state.load(p)
        assert result == {}


class TestSave:
    """save 関数のテストクラス"""

    def test_データをJSONファイルに書き込める(self, tmp_path):
        """辞書をJSONファイルに正しく保存できること"""
        data = {"JR山手線": {"state": "遅延", "detail": "詳細"}}
        p = tmp_path / "state.json"

        state.save(p, data)
        loaded = json.loads(p.read_text(encoding="utf-8"))
        assert loaded == data

    def test_親ディレクトリが存在しなくても作成して保存する(self, tmp_path):
        """存在しないディレクトリ階層でも自動作成してくれること"""
        p = tmp_path / "a" / "b" / "state.json"
        state.save(p, {"key": "value"})
        assert p.exists()


class TestDiff:
    """diff 関数のテストクラス"""

    TARGETS = ["JR山手線", "JR中央線（快速）", "JR京浜東北・根岸線"]

    def test_新規障害を検知する(self):
        """前回なかった障害が今回ある場合に new_or_changed に含まれること"""
        prev = {}
        current = {"JR山手線": {"state": "遅延", "detail": "遅れています。"}}

        new_or_changed, recovered = state.diff(prev, current, self.TARGETS)

        assert len(new_or_changed) == 1
        assert new_or_changed[0]["line"] == "JR山手線"
        assert new_or_changed[0]["state"] == "遅延"
        assert recovered == []

    def test_復旧を検知する(self):
        """前回障害があった路線が今回ない場合に recovered に含まれること"""
        prev = {"JR山手線": {"state": "遅延", "detail": "遅れています。"}}
        current = {}

        new_or_changed, recovered = state.diff(prev, current, self.TARGETS)

        assert new_or_changed == []
        assert "JR山手線" in recovered

    def test_変化なしの場合は両方空リスト(self):
        """障害状態が変わっていない場合は両方空リストになること"""
        prev = {"JR山手線": {"state": "遅延", "detail": "遅れています。"}}
        current = {"JR山手線": {"state": "遅延", "detail": "遅れています。"}}

        new_or_changed, recovered = state.diff(prev, current, self.TARGETS)

        assert new_or_changed == []
        assert recovered == []

    def test_状態変化を検知する(self):
        """遅延→運転見合わせのような状態変化を検知すること"""
        prev = {"JR山手線": {"state": "遅延", "detail": "遅れています。"}}
        current = {"JR山手線": {"state": "運転見合わせ", "detail": "運転を見合わせています。"}}

        new_or_changed, recovered = state.diff(prev, current, self.TARGETS)

        assert len(new_or_changed) == 1
        assert new_or_changed[0]["state"] == "運転見合わせ"
        assert recovered == []

    def test_複数路線の同時変化を正しく検知する(self):
        """複数路線が同時に変化した場合にすべて検知できること"""
        prev = {
            "JR山手線": {"state": "遅延", "detail": "遅れています。"},
        }
        current = {
            "JR中央線（快速）": {"state": "運転見合わせ", "detail": "見合わせ中。"},
        }

        new_or_changed, recovered = state.diff(prev, current, self.TARGETS)

        # 山手線が復旧、中央線が新規障害
        assert len(new_or_changed) == 1
        assert new_or_changed[0]["line"] == "JR中央線（快速）"
        assert "JR山手線" in recovered

    def test_監視対象外の路線は無視する(self):
        """TARGETS に含まれない路線は結果に現れないこと"""
        prev = {}
        current = {
            "JR武蔵野線": {"state": "遅延", "detail": "遅れています。"},
        }

        new_or_changed, recovered = state.diff(prev, current, self.TARGETS)

        assert new_or_changed == []
        assert recovered == []
