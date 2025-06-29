import asyncio


class DynIncAsyncSemaphore:
    def __init__(self, threshold: int):
        self._threshold = threshold
        self._counter = 0
        self._cond = asyncio.Condition()

    async def acquire(self):
        async with self._cond:
            while self._counter >= self._threshold:
                await self._cond.wait()
            self._counter += 1

    async def release(self):
        async with self._cond:
            self._counter -= 1
            self._counter = max(self._counter, 0)
            self._cond.notify_all()

    async def update_threshold(self, value: int):
        async with self._cond:
            self._threshold = value
            if self._cond._waiters:
                self._cond.notify_all()
