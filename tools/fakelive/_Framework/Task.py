"""Falsk `_Framework.Task`: wait/run/sequence og en TaskGroup som drives av update(dt)."""


def wait(seconds):
    return ('wait', seconds)


def run(fn):
    return ('run', fn)


def sequence(*steps):
    return _Task(list(steps))


class _Task:

    def __init__(self, steps):
        self._steps = steps
        self._waited = 0.0
        self._killed = False

    def kill(self):
        self._killed = True

    @property
    def is_done(self):
        return self._killed or not self._steps

    def update(self, dt):
        while self._steps and not self._killed:
            kind, arg = self._steps[0]
            if kind == 'wait':
                if self._waited + dt < arg:
                    self._waited += dt
                    return
                dt -= arg - self._waited
                self._waited = 0.0
            else:
                arg()
            self._steps.pop(0)


class TaskGroup:

    def __init__(self):
        self._tasks = []

    def add(self, task):
        if isinstance(task, tuple):
            task = _Task([task])
        self._tasks.append(task)
        return task

    def update(self, dt):
        for task in list(self._tasks):
            task.update(dt)
        self._tasks = [t for t in self._tasks if not t.is_done]

    def clear(self):
        for task in self._tasks:
            task.kill()
        self._tasks = []
