import io
import sys


class StdoutCapture:
    def __enter__(self):
        self.buffer = io.StringIO()
        self._old_stdout = sys.stdout
        sys.stdout = self.buffer
        return self.buffer

    def __exit__(self, *args):
        sys.stdout = self._old_stdout


def run_with_logs(func, *args, **kwargs):
    with StdoutCapture() as buf:
        result = func(*args, **kwargs)
    return result, buf.getvalue()
