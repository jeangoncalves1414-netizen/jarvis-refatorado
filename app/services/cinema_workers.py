"""Bounded browser workers; Playwright objects never cross thread boundaries."""
from concurrent.futures import Future
from queue import Queue, Empty
from threading import Lock, Thread


class BrowserWorkers:
    def __init__(self, size=4, idle_seconds=30):
        self.size = size
        self.idle_seconds = idle_seconds
        self._jobs = Queue()
        self._lock = Lock()
        self._threads = []
        self._closed = False

    def run(self, callback):
        future = Future()
        with self._lock:
            if self._closed:
                raise RuntimeError('Browser workers are closed')
            if not self._threads:
                for index in range(self.size):
                    thread = Thread(target=self._worker, name=f'cinema-probe-{index}', daemon=True)
                    thread.start()
                    self._threads.append(thread)
            self._jobs.put((future, callback))
        return future.result()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for _ in self._threads:
                self._jobs.put(None)
        for thread in self._threads:
            thread.join(timeout=5)

    def _worker(self):
        browser = playwright = None

        def release():
            nonlocal browser, playwright
            for resource, method in ((browser, 'close'), (playwright, 'stop')):
                if resource is not None:
                    try:
                        getattr(resource, method)()
                    except Exception:
                        pass
            browser = playwright = None

        try:
            while True:
                try:
                    job = self._jobs.get(timeout=self.idle_seconds)
                except Empty:
                    release()
                    continue
                if job is None:
                    break
                future, callback = job
                try:
                    if browser is None or not browser.is_connected():
                        release()
                        from playwright.sync_api import sync_playwright
                        playwright = sync_playwright().start()
                        browser = playwright.chromium.launch(headless=True)
                    future.set_result(callback(browser))
                except Exception as error:
                    release()
                    future.set_exception(error)
        finally:
            release()
