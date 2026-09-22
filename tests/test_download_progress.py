import tempfile
import unittest
from pathlib import Path
from anime_dubber.core import download_source

class FakeStreamRunner:
    def __init__(self, work):
        self.work = Path(work)
        self.commands = []
    def run_stream(self, cmd, line_callback=None, **kwargs):
        self.commands.append(cmd)
        if line_callback:
            line_callback("__YTDLP_PROGRESS__| 12.5%|3.2MiB/s|00:20|100.0MiB")
            line_callback("__YTDLP_PROGRESS__|100.0%|4.0MiB/s|00:00|100.0MiB")
        out = self.work / "source.mp4"
        out.write_bytes(b"video")
        class CP:
            stdout = "__YTDLP_FILE__:" + str(out)
        return CP()

class DownloadProgressTests(unittest.TestCase):
    def test_progress_events_are_emitted(self):
        with tempfile.TemporaryDirectory() as td:
            events=[]
            runner=FakeStreamRunner(td)
            out=download_source("https://youtu.be/example",Path(td),runner,events.append)
            self.assertTrue(out.exists())
            ev=[e for e in events if e.startswith("__DOWNLOAD_PROGRESS__|")]
            self.assertTrue(any("|12.50|" in e for e in ev))
            self.assertTrue(any("|100.00|" in e for e in ev))
            cmd=runner.commands[0]
            self.assertIn("--newline",cmd)
            self.assertIn("--progress-template",cmd)

if __name__ == "__main__":
    unittest.main()
