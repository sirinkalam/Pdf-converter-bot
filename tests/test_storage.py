from pathlib import Path

from pdf_converter_bot.storage import cleanup_job_files, create_job_dir


def test_cleanup_job_files_removes_directory() -> None:
    job_dir = create_job_dir()
    sample_file = Path(job_dir) / "temp.txt"
    sample_file.write_text("hello", encoding="utf-8")

    assert sample_file.exists()
    cleanup_job_files(job_dir)
    assert not job_dir.exists()
