"""HypertgTransfer (WZML-X wzv3, trimmed for this bot).

Real HyperUP is load-balance across helper bots + user session.
If HELPER_TOKENS empty, clients={} and callers must use normal bot/user send.
"""
from logging import getLogger

from ... import bot, user

LOGGER = getLogger(__name__)

helper_bots = {}
helper_loads = {}


def hyper_ready():
    return bool(helper_bots or user)


def pick_hyper_client():
    """Least-loaded helper bot, else user session, else main bot."""
    if helper_bots:
        idx = min(helper_loads, key=helper_loads.get)
        helper_loads[idx] = helper_loads.get(idx, 0) + 1
        return helper_bots[idx], idx
    if user:
        return user, None
    return bot, None


def release_hyper_client(idx):
    if idx is None:
        return
    helper_loads[idx] = max(0, helper_loads.get(idx, 1) - 1)


class HypertgTransfer:
    def __init__(self, obj=None):
        self._obj = obj
        self.clients = dict(helper_bots)
        if user:
            self.clients[-1] = user
        self.num_clients = len(self.clients)
        LOGGER.info("HypertgTransfer clients=%s", self.num_clients)
