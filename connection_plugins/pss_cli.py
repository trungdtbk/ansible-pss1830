
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = """
---
author: Trung Truong @ Nokia NZ
connection: pss_cli
short_description: Use pss_cli to run command on Nokia 1830PSS nodes
description:
  - This connection plugin provides a connection to remote Nokia 1830PSS nodes
    over the SSH and implements a CLI shell.
version_added: "2.8"
options:
  host:
    description:
      - Specifies the remote device FQDN or IP address to establish the SSH
        connection to.
    default: inventory_hostname
    vars:
      - name: ansible_host
  port:
    type: int
    description:
      - Specifies the port on the remote device that listens for connections
        when establishing the SSH connection.
    default: 22
    ini:
      - section: defaults
        key: remote_port
    env:
      - name: ANSIBLE_REMOTE_PORT
    vars:
      - name: ansible_port
  network_os:
    description:
      - Configures the device platform network operating system.  This value is
        used to load the correct terminal and cliconf plugins to communicate
        with the remote device.
    default: pss
    vars:
      - name: ansible_network_os
  remote_user:
    description:
      - The username used to authenticate to the PSS node when the CLI session
        is first established.
      - Can be configured from the CLI via the C(--user) or C(-u) options.
    ini:
      - section: defaults
        key: remote_user
    env:
      - name: ANSIBLE_REMOTE_USER
    vars:
      - name: ansible_user
  password:
    description:
      - Configures the user password used to authenticate to the PSS node when
        first establishing the CLI session.
    vars:
      - name: ansible_password
      - name: ansible_ssh_pass
      - name: ansible_ssh_password
  private_key_file:
    description:
      - The private SSH key or certificate file used to authenticate to the
        remote device when first establishing the SSH connection.
    ini:
      - section: defaults
        key: private_key_file
    env:
      - name: ANSIBLE_PRIVATE_KEY_FILE
    vars:
      - name: ansible_private_key_file
  timeout:
    type: int
    description:
      - Sets the connection time, in seconds, for communicating with the
        remote device.  This timeout is used as the default timeout value for
        commands when issuing a command to the network CLI.  If the command
        does not return in timeout seconds, an error is generated.
    default: 180
  pss_cli_user:
    description:
      - The username used to initialize a CLI session to the PSS node.
    default: cli
    ini:
      - section: defaults
        key: pss_cli_user
    env:
      - name: PSS_CLI_USER
    vars:
      - name: pss_cli_user
  pss_cli_pass:
    description:
      - The password used to initialize a CLI session to the PSS node.
    default: cli
    ini:
      - section: defaults
        key: pss_cli_pass
    env:
      - name: PSS_CLI_PASS
    vars:
      - name: pss_cli_pass
  host_key_auto_add:
    type: boolean
    description:
      - By default, Ansible will prompt the user before adding SSH keys to the
        known hosts file.  Since persistent connections such as network_cli run
        in background processes, the user will never be prompted.  By enabling
        this option, unknown host keys will automatically be added to the
        known hosts file.
      - Be sure to fully understand the security implications of enabling this
        option on production systems as it could create a security vulnerability.
    default: True
    ini:
      - section: paramiko_connection
        key: host_key_auto_add
    env:
      - name: ANSIBLE_HOST_KEY_AUTO_ADD
  persistent_connect_timeout:
    type: int
    description:
      - Configures, in seconds, the amount of time to wait when trying to
        initially establish a persistent connection.  If this value expires
        before the connection to the remote device is completed, the connection
        will fail.
    default: 120
    ini:
      - section: persistent_connection
        key: connect_timeout
    env:
      - name: ANSIBLE_PERSISTENT_CONNECT_TIMEOUT
    vars:
      - name: ansible_connect_timeout
  persistent_command_timeout:
    type: int
    description:
      - Configures, in seconds, the amount of time to wait for a command to
        return from the remote device.  If this timer is exceeded before the
        command returns, the connection plugin will raise an exception and
        close.
    default: 180
    ini:
      - section: persistent_connection
        key: command_timeout
    env:
      - name: ANSIBLE_PERSISTENT_COMMAND_TIMEOUT
    vars:
      - name: ansible_command_timeout
  persistent_buffer_read_timeout:
    type: float
    description:
      - Configures, in seconds, the amount of time to wait for the data to be read
        from Paramiko channel after the command prompt is matched. This timeout
        value ensures that command prompt matched is correct and there is no more data
        left to be received from remote host.
    default: 0.1
    ini:
      - section: persistent_connection
        key: buffer_read_timeout
    env:
      - name: ANSIBLE_PERSISTENT_BUFFER_READ_TIMEOUT
    vars:
      - name: ansible_buffer_read_timeout
  persistent_log_messages:
    type: boolean
    description:
      - This flag will enable logging the command executed and response received from
        target device in the ansible log file. For this option to work 'log_path' ansible
        configuration option is required to be set to a file path with write access.
      - Be sure to fully understand the security implications of enabling this
        option as it could create a security vulnerability by logging sensitive information in log file.
    default: False
    ini:
      - section: persistent_connection
        key: log_messages
    env:
      - name: ANSIBLE_PERSISTENT_LOG_MESSAGES
    vars:
      - name: ansible_persistent_log_messages
"""

from ansible.plugins.connection.network_cli import Connection as NetworkCLI
from ansible.plugins.loader import cliconf_loader, terminal_loader, connection_loader
from ansible.playbook.play_context import PlayContext


class Connection(NetworkCLI):

    def __init__(self, play_context, new_stdin, *args, **kwargs):
        super(Connection, self).__init__(play_context, new_stdin, *args, **kwargs)

    def _connect(self):
        '''
        Override this method in order to load a custom play context
        '''
        if not self.connected:
            _play_context = self._play_context.copy()
            _play_context.load_data({'remote_user': self.get_option('pss_cli_user'),
                                     'password': self.get_option('pss_cli_pass')})
            self.paramiko_conn = connection_loader.get('paramiko', _play_context, '/dev/null')
            self.paramiko_conn._set_log_channel(self._get_log_channel())
            self.paramiko_conn.set_options(direct={'look_for_keys': not bool(self._play_context.password and not self._play_context.private_key_file)})
            self.paramiko_conn.force_persistence = self.force_persistence
            ssh = self.paramiko_conn._connect()

            host = self.get_option('host')
            self.queue_message('vvvv', 'ssh connection done, setting terminal')

            self._ssh_shell = ssh.ssh.invoke_shell()
            self._ssh_shell.settimeout(self.get_option('persistent_command_timeout'))

            self._terminal = terminal_loader.get(self._network_os, self)
            if not self._terminal:
                raise AnsibleConnectionFailure('network os %s is not supported' % self._network_os)

            self.queue_message('vvvv', 'loaded terminal plugin for network_os %s' % self._network_os)

            self.receive(prompts=self._terminal.terminal_initial_prompt, answer=self._terminal.terminal_initial_answer,
                         newline=self._terminal.terminal_inital_prompt_newline)

            self.queue_message('vvvv', 'firing event: on_open_shell()')
            self._terminal.on_open_shell()
            self.queue_message('vvvv', 'ssh connection has completed successfully')
            self._connected = True

        return self
