Ansible Modules for Nokia Photonic Service Switch (1830PSS) Network Elements
****************************************************************************

Introduction
=============

This repo includes several modules for interacting with the 1830PSS nodes and a
connection based on network_cli, specifically designed to work with the 1830PSS nodes.

Modules are:

- pss_facts: get facts/current state/current configs of the node
- pss_command: Used to execute any command on the node and get the output
- pss_software: get current software status and upgrade (audit/load/activate/commit)
  new software release on the node

How to Use
==========

Clone this repository to a dictory and place the playbooks in the directory
(but not in subdirectories).

To see documentation for each module, use the following command:
:code:`ansible-doc -t <type> -M <path> <module/plugin name>`
e.g. :code:`ansible-doc -t module -M library/ pss_command`


Examples
========
Examples of playbooks are provided in directory :code:`examples`. To run these playbooks,
copy them to the parent directory.
