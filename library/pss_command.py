#!/usr/bin/python
#
#TODO: license statement goes here
#

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'network'}



DOCUMENTATION = """
---
module: pss_command
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
    pss_command:
      commands:
        - show general {{ item }}
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

import time
import json
import collections

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.network.common.parsing import Conditional
from ansible.module_utils.network.common.utils import to_lines
from ansible.module_utils._text import to_text

from ansible.module_utils.pss import parse_commands, run_commands # pylint: disable=all


def main():
    """main entry point for module execution
    """
    argument_spec = dict(
        commands=dict(type='list', required=True),
        wait_for=dict(type='list', aliases=['waitfor']),
        match=dict(default='all', choices=['all', 'any']),
        retries=dict(default=10, type='int'),
        interval=dict(default=1, type='int'),
        prompt=dict(default="Enter 'yes' to confirm, 'no' to cancel:"),
        answer=dict(default='yes')
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    warnings = list()
    result = {'changed': False, 'warnings': warnings}
    commands = parse_commands(module, warnings)
    wait_for = module.params['wait_for'] or list()

    try:
        conditionals = [Conditional(c) for c in wait_for]
    except AttributeError as exc:
        module.fail_json(msg=to_text(exc))

    retries = module.params['retries']
    interval = module.params['interval']
    match = module.params['match']

    for _ in range(retries):
        responses = run_commands(module, commands)

        for item in list(conditionals):
            if item(responses):
                if match == 'any':
                    conditionals = list()
                    break
                conditionals.remove(item)

        if not conditionals:
            break

        time.sleep(interval)

    if conditionals:
        failed_conditions = [item.raw for item in conditionals]
        msg = 'One or more conditional statements have not been satisfied'
        module.fail_json(msg=msg, failed_conditions=failed_conditions)

    result.update({
        'stdout': responses,
        'stdout_lines': list(to_lines(responses)),
    })

    module.exit_json(**result)


if __name__ == '__main__':
    main()
