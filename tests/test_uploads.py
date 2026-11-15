import pytest

from src.config import settings
from src.uploads import save_uploads, uploader_types


class FakeUpload:
    def __init__(self, name, data=b"hello", size=None):
        self.name, self._data = name, data
        self.size = len(data) if size is None else size

    def getbuffer(self):
        return memoryview(self._data)


@pytest.fixture
def kb(tmp_path):
    return tmp_path / "kb"


def test_saves_allowed_files(kb):
    saved, rejected = save_uploads([FakeUpload("a.pdf"), FakeUpload("b.TXT")], str(kb))
    assert saved == ["a.pdf", "b.TXT"] and rejected == []
    assert (kb / "a.pdf").read_bytes() == b"hello"


def test_rejects_files_over_the_size_limit(kb, monkeypatch):
    monkeypatch.setattr(settings, "max_file_size_mb", 1)
    big = FakeUpload("big.pdf", size=1024 * 1024 + 1)
    ok = FakeUpload("ok.pdf", size=1024 * 1024)
    saved, rejected = save_uploads([big, ok], str(kb))
    assert saved == ["ok.pdf"] and rejected == [("big.pdf", "size")]
    assert not (kb / "big.pdf").exists()


def test_rejects_extensions_local_rag_cannot_read(kb):
    saved, rejected = save_uploads([FakeUpload("notes.md"), FakeUpload("x.exe")], str(kb))
    assert saved == [] and rejected == [("notes.md", "extension"), ("x.exe", "extension")]


@pytest.mark.parametrize("name", ["../../evil.txt", "..\\..\\evil.txt", "/etc/evil.txt"])
def test_client_paths_cannot_escape_the_knowledge_base(tmp_path, name):
    kb = tmp_path / "a" / "kb"
    saved, _ = save_uploads([FakeUpload(name)], str(kb))
    assert saved == ["evil.txt"]
    assert (kb / "evil.txt").exists()
    assert not (tmp_path / "evil.txt").exists()


@pytest.mark.parametrize("name", ["", "..", ".hidden.txt", "dir/"])
def test_rejects_empty_or_hidden_names(kb, name):
    saved, rejected = save_uploads([FakeUpload(name)], str(kb))
    assert saved == [] and rejected[0][1] == "name"


def test_uploader_types_follow_settings(monkeypatch):
    assert uploader_types() == ["pdf", "txt"]
    monkeypatch.setattr(settings, "allowed_file_extensions", [".PDF", "txt"])
    assert uploader_types() == ["pdf", "txt"]
