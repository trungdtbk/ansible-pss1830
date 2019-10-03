
import re
import json

from ansible.module_utils.connection import Connection, ConnectionError
from ansible.module_utils.network.common.utils import transform_commands
from ansible.module_utils._text import to_text


class PssParser():

    @classmethod
    def parse_system_name(cls, data):
            m = re.search(r'System Name.*: (.*)', data)
            if m:
                return m.group(1)

    @classmethod
    def parse_system_capacity(cls, data):
        m = re.search(r'Capacity.*: (\d+[G])', data)
        if m:
            return m.group(1)

    @classmethod
    def parse_version(cls, data):
            m = re.search(r'Software Version: (1830PSS.*)', data)
            if m:
                return m.group(1)

    @classmethod
    def parse_redundancy(cls, data):
        match = re.search(r'(\d/\d+)[ ]+([A-Za-z0-9]+)[ ]+([A-Za-z]+)[ ]+(Yes|No)', data)
        if match:
            standby_ec_slot, standby_ec_type, standby_ec_state, standby_ec_ready = match.groups()
            if standby_ec_ready.upper() == 'YES':
                standby_ec_ready = True
            else:
                standby_ec_ready = False
        else:
            standby_ec_slot = standby_ec_type = standby_ec_state = None

        match = re.search(r'(\d/\d+)[ ]+([A-Za-z0-9]+)[ ]+(Active)', data)
        if match:
            active_ec_slot, active_ec_type, _ = match.groups()
        else:
            active_ec_slot = active_ec_type = None

        return dict(active_ec_slot=active_ec_slot,
                    active_ec_type=active_ec_type,
                    standby_ec_slot=standby_ec_slot,
                    standby_ec_type=standby_ec_type,
                    standby_ec_state=standby_ec_state,
                    standby_ec_ready=standby_ec_ready)

    @classmethod
    def parse_upgrade_status(cls, data):
        status = dict(
                    software_server_ip=None,
                    software_root_dir=None,
                    committed_release=None,
                    working_release_dir=None,
                    working_release=None,
                    active_release=None,
                    operation=None,
                    operation_status=None,
                    percent_completion=None,
                    upgrade_path_avail=None)

        lines = [line for line in data.splitlines() if line]

        attrs = [('Software Server IP', 'software_server_ip'),
                 ('Software Server Root Directory', 'software_root_dir'),
                 ('Committed Release', 'committed_release'),
                 ('Working Release Directory', 'working_release_dir'),
                 ('Working Release', 'working_release'),
                 ('Active Release', 'active_release'),
                 ('Operation', 'operation'),
                 ('Operation Status', 'operation_status'),
                 ('Percent Completion', 'percent_completion'),
                 ('Upgrade Path Available', 'upgrade_path_avail')]
        for line in lines:
            for attr, key in attrs:
                result = re.search(r'(%s[\t ]+):(.*)' % attr, line)
                if result:
                    status[key] = result.group(2).strip()
                    break

        return status


def parse_commands(module, warnings):
    commands = transform_commands(module)

    if module.check_mode:
        for item in list(commands):
            if not item['command'].startswith('show'):
                warnings.append(
                    'Only show commands are supported when using check mode, not '
                    'executing %s' % item['command']
                )
                commands.remove(item)

    return commands


def get_capabilities(module):
    if hasattr(module, '_pss_capabilities'):
        return module._pss_capabilities

    try:
        capabilities = Connection(module._socket_path).get_capabilities()
    except ConnectionError as exc:
        module.fail_json(msg=to_text(exc, errors='surrogate_then_replace'))

    module._pss_capabilities = json.loads(capabilities)
    return module._pss_capabilities


def get_connection(module):
    if hasattr(module, '_pss_connection'):
        return module._pss_connection

    capabilities = get_capabilities(module)
    network_api = capabilities.get('network_api')
    if network_api == 'cliconf':
        module._pss_connection = Connection(module._socket_path)
    else:
        module.fail_json(msg='Connection type not supported: %s' % network_api)

    return module._pss_connection


def run_commands(module, commands, check_rc=True):
    connection = get_connection(module)
    try:
        response = connection.run_commands(commands=commands, check_rc=check_rc)
    except ConnectionError as exc:
        module.fail_json(msg=to_text(exc, errors='surrogate_then_replace'))
    return response

def run_command(module, command):
    connection = get_connection(module)
    try:
        response = connection.get(command=command)
    except ConnectionError as exc:
        module.fail_json(msg=to_text(exc, errors='surrogate_then_replace'))
    return response
