#
# TODO: add license info
#

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import re

from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils._text import to_text, to_bytes
from ansible.plugins.terminal import TerminalBase
from ansible.utils.display import Display

display = Display()


class TerminalModule(TerminalBase):

    terminal_stdout_re = [
        re.compile(br"[\r\n]?[\w-]+(?:[#]) ?$"),
        re.compile(br"Username:"),
        re.compile(br"Password:"),
        re.compile(br"Do you.*\(Y/N\)\?")
    ]

    #TODO: populate terminal stderr regex
    terminal_stderr_re = [
        re.compile(br"Command aborted"),
        re.compile(br"Error:", re.I),
        re.compile(br"(?:incomplete|ambiguous) command", re.I),
        re.compile(br"connection timed out", re.I),
        re.compile(br"[^\r\n]+ not found"),
        re.compile(br"[%\S] ?Error: ?[\s]+", re.I),
    ]

    def on_open_shell(self):
        try:
            prompt = self._get_prompt()
            if prompt.strip().startswith(b'Username'):
                username = self._connection._play_context.remote_user
                password = self._connection._play_context.password
                display.vvvv('logging to CLI with user: %s' % username)
                self._exec_cli_command(username.encode())
                self._exec_cli_command(password.encode())
                self._exec_cli_command(br"Y")

            self._exec_cli_command(br"paging status disabled")
        except AnsibleConnectionFailure:
            raise AnsibleConnectionFailure('unable to establish a CLI session')
