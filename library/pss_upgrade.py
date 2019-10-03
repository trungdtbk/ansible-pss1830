#!/usr/bin/python
#
#TODO: license statement goes here
#

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'network'}



DOCUMENTATION = """
---
module: pss_upgrade
version_added: "2.8"
author: "Trung Truong @ Nokia_NZ"
short_description: Run one or more commands on Nokia 1830PSS devices
description:
  - The command module allows running one or more commands on Nokia 1830PSS
    devices.  This module can also be introspected to validate key parameters
    before returning successfully.  If the conditional statements are not met
    in the wait period, the task fails.
extends_documentation_fragment: network
options:
  commands:
    description:
      - The ordered set of commands to execute on the remote 1830PSS node.
        The output from the command execution is returned to the playbook.
        If the I(wait_for) argument is provided, the module is not returned until
        the condition is satisfied or the number of retries has been exceeded.
    required: true
  wait_for:
    description:
      - Specifies what to evaluate from the output of the command
        and what conditionals to apply.  This argument will cause
        the task to wait for a particular conditional to be true
        before moving forward.  If the conditional is not true
        by the configured I(retries), the task fails. See examples.
    aliases: ['waitfor']
  match:
    description:
      - The I(match) argument is used in conjunction with the
        I(wait_for) argument to specify the match policy. Valid
        values are C(all) or C(any).  If the value is set to C(all)
        then all conditionals in the wait_for must be satisfied.  If
        the value is set to C(any) then only one of the values must be
        satisfied.
    default: all
    choices: ['any', 'all']
  retries:
    description:
      - Specifies the number of retries a command should be tried
        before it is considered failed. The command is run on the
        target device every retry and evaluated against the I(wait_for)
        conditionals.
    default: 10
  interval:
    description:
      - Configures the interval in seconds to wait between I(retries)
        of the command. If the command does not pass the specified
        conditions, the interval indicates how long to wait before
        trying the command again.
    default: 1
notes:
  - Tested against 1830PSS R11.0.1
  - If a command sent to the device requires answering a prompt, it is possible
    to pass a dict containing I(command), I(answer) and I(prompt). See examples.
"""

EXAMPLES = """
tasks:
  - ame: show configuration name and date
    pss_upgrade:
      command: status
    with_items:
      - name
      - date
  - name: run multiple commands and check if version output contains specific version string
    pss_command:
      commands:
        - show version
        - show software up status
      wait_for:
        - "result[0] contains '1830PSSECX-11.0-1'"
  - name: run command that requires answering a prompt
    pss_command:
      commands:
        - command: 'config card 1/15 reset cold'
          prompt: 'Enter 'yes' to confirm, 'no' to cancel:'
          answer: yes
"""

RETURN = """
stdout:
  description: The set of responses from the commands
  returned: always apart from low level errors (such as action plugin)
  type: list
  sample: ['...', '...']
stdout_lines:
  description: The value of stdout split into a list
  returned: always
  type: list
  sample: [['...', '...'], ['...'], ['...']]
failed_conditions:
  description: The list of conditionals that have failed
  returned: failed
  type: list
  sample: ['...', '...']
warnings:
  description: The list of warnings (if any) generated by module based on arguments
  returned: always
  type: list
  sample: ['...', '...']
"""

import re
import time
import json
import collections

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.network.common.parsing import Conditional as Conditional
from ansible.module_utils.network.common.utils import to_lines
from ansible.module_utils._text import to_text

from ansible.module_utils.pss import run_commands, run_command # pylint: disable=all
from ansible.module_utils.pss import PssParser as parser # pylint: disable=all


class StatusConditional(Conditional):

    def __init__(self, conditional):
        if type(conditional) == dict:
            self.desired_status = conditional
        else:
            raise ValueError('failed to parse conditional')

    def __call__(self, status):
        if type(status) == dict:
            for key, value in self.desired_status.items():
                if value is None:
                    continue
                if key not in status or status[key] != value:
                    return
        else:
            return

        return True

    def __str__(self):
        return self.desired_status


def get_upgrade_status(module):

    command = 'config soft upgrade status'
    response = run_command(module, command)
    responses = [response, 'executed: %s' % command]

    return (responses, parser.parse_upgrade_status(responses[0]))


def execute_command(module, command, **kwargs):
    conditional = kwargs.get('conditional')
    timeout = kwargs.get('timeout', 0)
    interval = kwargs.get('interval', 1)

    if command == 'commit':
        cmd_line = 'config soft upgrade commit'
    elif command == 'abort':
        cmd_line = 'config soft upgrade abort'
    elif command == 'backout':
        cmd_line = 'config soft upgrade backout yes'
    elif command == 'activate':
        cmd_line = 'config soft upgrade manual activate yes'
    elif command == 'audit':
        cmd_line = 'config soft upgrade manual audit {release} {audit_option}'.format(**kwargs)
    elif command == 'load':
        cmd_line = 'config soft upgrade manual load'
    else:
        cmd_line = ''

    responses = []
    if cmd_line:
        responses.append('executed command: %s' % cmd_line)
        responses.append(run_command(module, cmd_line))

        success = False
        if conditional:
            for _ in range(timeout):
                _, status = get_upgrade_status(module)
                if conditional(status):
                    success = True
                    break
                time.sleep(interval)

            if not success:
                msg = 'The condition (%s) has not been satisfied' % conditional
                module.fail_json(msg=msg, failed_conditions=[])


    return responses


def main():
    """main entry point for module execution
    """
    argument_spec = dict(
        command=dict(choices=['status', 'abort', 'commit', 'manual', 'backout', 'auto'], required=True),
        manual=dict(choices=['activate', 'audit', 'load']),
        release=dict(type='str'),
        audit_option=dict(choices=['force', 'nobackup', 'nobackupforce']),

        wait_for=dict(
            type='dict', aliases=['waitfor'],
            options=dict(
                operation=dict(choices=['Abort', 'Backout', 'Commit', 'Load', 'Activate']),
                operation_status=dict(choices=['Completed', 'In Progress', 'Failure']),
                committed_release=dict(type='str'),
                stdout=dict(type='str'),
                )
        ),
        wait_timeout=dict(default=18000, type='int'),
        check_interval=dict(default=10, type='int'),
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    warnings = list()
    result = {'changed': False, 'warnings': warnings}

    conditional = None
    wait_for = module.params['wait_for']
    if wait_for:
        try:
            conditional = StatusConditional(wait_for)
        except AttributeError as exc:
            module.fail_json(msg=to_text(exc))

    wait_timeout = module.params['wait_timeout']
    check_interval = module.params['check_interval']

    command = module.params['command'].lower()

    kwargs = dict(conditional=conditional,
                  timeout=wait_timeout,
                  interval=check_interval)

    commands = []
    responses = []

    if command == 'status':
        responses, status = get_upgrade_status(module)
        result['upgrade_status'] = status

    else:
        _, status = get_upgrade_status(module)

        if status['operation_status'] == 'Failure' and command != 'backout':
            module.fail_json(msg='upgrade operation %s is %s' % (status['operation'], status['operation_status']))

        if command == 'commit':
            if status['operation'] == 'Activate' or status['operation'] == 'Commit':
                if status['operation'] == 'Commit':
                    warnings.append('software (%s) has already been committed' % status['committed_release'])
            else:
                module.fail_json(msg='cannot execute commit when in state (%s, %s)' % (status['operation'], status['operation_status']))

        elif command == 'manual':
            option = module.params['manual']
            release = module.params['release']

            if option == 'audit':
                if not release:
                    module.fail_json(msg='audit operation requires release option')
                audit_option = module.params['audit_option'] or ''

                if status['working_release'] == release:
                    command = None # no need to do audit

                elif status['active_release'] != release:
                    command = 'audit'
                    kwargs['release'] = release
                    kwargs['audit_option'] = audit_option

            elif option == 'load':

                if status['operation'] == 'Load':
                    warnings.append('load operation has already executed, current status: %s' % status['operation_status'])
                    command = None
                elif status['operation'] == 'Audit' and status['operation_status'] == 'Completed':
                    command = 'load'
                else:
                    module.fail_json(msg='cannot execute load when in state %s' % status['operation'])

            elif option == 'activate':
                if status['operation'] != 'Load' and status['operation_status'] != 'Completed':
                    module.fail_json(msg='cannot execute activate when in state %s' % status['operation'])

                if status['operation'] == 'Activate':
                    warnings.append('activate operation has already executed, current status: %s' % status['operation_status'])
                    command = None
                else:
                    command = 'activate'
        elif command == 'auto':
            commands.extend(['audit', 'load', 'activate', 'commit'])

        if not commands:
            commands.append(command)

        for command in commands:
            responses.extend(execute_command(module, command, **kwargs))

    result.update({
        'stdout': responses,
        'stdout_lines': list(to_lines(responses)),
    })

    module.exit_json(**result)


if __name__ == '__main__':
    main()
