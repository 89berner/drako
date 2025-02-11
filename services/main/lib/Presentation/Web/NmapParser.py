import re
import traceback
import xml.etree.ElementTree as ET
import lib.Common.Utils.Log as Log


class NmapParser:
    def __init__(self, nmap_scan):
        self.nmap_scan = self._escape_illegal_xml_characters(nmap_scan)

        self.root      = ET.fromstring(self.nmap_scan)
        self.host_tree = list(self.root.iter('host'))[0]

        self.ports = self._get_ports_from_nmap_tree()
        Log.logger.debug("PORTS DATA => %s" % self.ports)

        self.os_info = self._get_os_info_from_nmap_tree()
        Log.logger.debug("OS INFO => %s" % self.os_info)

    def get_open_ports(self):
        return self.ports

    def get_os_info(self):
        return self.os_info

    def _escape_illegal_xml_characters(self, nmap_scan):
        return re.sub(u'[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]', '', nmap_scan)

    def _get_ports_from_nmap_tree(self):
        ports = []
        element = self.host_tree.find('ports')
        for data in element:
            if data.tag == 'port':
                port_data = {}

                try:
                    state_el           = data.find('state')
                    port_data['state'] = state_el.attrib['state']
                except:
                    print("ERROR => %s" % traceback.format_exc())

                try:
                    state_el           = data.find('service')
                    port_data['name'] = state_el.attrib['name']
                except:
                    port_data['name'] = None

                try:
                    state_el                 = data.find('service')
                    port_data['application'] = state_el.attrib['product']
                except:
                    port_data['application'] = None

                try:
                    port_data['protocol'] = data.attrib['protocol']
                except:
                    print("ERROR => %s" % traceback.format_exc())

                try:
                    port_data['port'] = data.attrib['portid']
                except:
                    print("ERROR => %s" % traceback.format_exc())

                ports.append(port_data)

        return ports

    # "information": {
    #     "hostname": "LEGACY",
    #     "os_flavor": "windows",
    #     "os_name": "Windows XP"
    # },

    # <osmatch name="Microsoft Windows XP SP3" accuracy="94" line="83428">
    # <osclass type="general purpose" vendor="Microsoft" osfamily="Windows" osgen="XP" accuracy="94"><cpe>cpe:/o:microsoft:windows_xp::sp3</cpe></osclass>
    def _get_os_info_from_nmap_tree(self):
        root = self.host_tree.find('os')
        os_data = {}
        try:
            best_os_match = root.find('osmatch')
            os_name         = best_os_match.attrib['name']
            os_data['os_name'] = os_name
        except:
            print("ERROR => %s" % traceback.format_exc())

        try:
            best_os_match        = root.find('osmatch')
            os_class             = best_os_match.find('osclass')
            os_family            = os_class.attrib['osfamily'] #osfamily="Windows"
            os_data['os_flavor'] = os_family
        except:
            print("ERROR => %s" % traceback.format_exc())

        return os_data