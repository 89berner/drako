nmap_data = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE nmaprun>
<?xml-stylesheet href="file:///usr/bin/../share/nmap/nmap.xsl" type="text/xsl"?>
<!-- Nmap 7.80 scan initiated Wed Mar 10 22:18:40 2021 as: nmap -A -oX out.xml 127.0.0.1 -->
<nmaprun scanner="nmap" args="nmap -A -oX out.xml 127.0.0.1" start="1615414720" startstr="Wed Mar 10 22:18:40 2021" version="7.80" xmloutputversion="1.04">
<scaninfo type="syn" protocol="tcp" numservices="1000" services="1,3-4,6-7,9,13,17,19-26,30,32-33,37,42-43,49,53,70,79-85,88-90,99-100,106,109-111,113,119,125,135,139,143-144,146,161,163,179,199,211-212,222,254-256,259,264,280,301,306,311,340,366,389,406-407,416-417,425,427,443-445,458,464-465,481,497,500,512-515,524,541,543-545,548,554-555,563,587,593,616-617,625,631,636,646,648,666-668,683,687,691,700,705,711,714,720,722,726,749,765,777,783,787,800-801,808,843,873,880,888,898,900-903,911-912,981,987,990,992-993,995,999-1002,1007,1009-1011,1021-1100,1102,1104-1108,1110-1114,1117,1119,1121-1124,1126,1130-1132,1137-1138,1141,1145,1147-1149,1151-1152,1154,1163-1166,1169,1174-1175,1183,1185-1187,1192,1198-1199,1201,1213,1216-1218,1233-1234,1236,1244,1247-1248,1259,1271-1272,1277,1287,1296,1300-1301,1309-1311,1322,1328,1334,1352,1417,1433-1434,1443,1455,1461,1494,1500-1501,1503,1521,1524,1533,1556,1580,1583,1594,1600,1641,1658,1666,1687-1688,1700,1717-1721,1723,1755,1761,1782-1783,1801,1805,1812,1839-1840,1862-1864,1875,1900,1914,1935,1947,1971-1972,1974,1984,1998-2010,2013,2020-2022,2030,2033-2035,2038,2040-2043,2045-2049,2065,2068,2099-2100,2103,2105-2107,2111,2119,2121,2126,2135,2144,2160-2161,2170,2179,2190-2191,2196,2200,2222,2251,2260,2288,2301,2323,2366,2381-2383,2393-2394,2399,2401,2492,2500,2522,2525,2557,2601-2602,2604-2605,2607-2608,2638,2701-2702,2710,2717-2718,2725,2800,2809,2811,2869,2875,2909-2910,2920,2967-2968,2998,3000-3001,3003,3005-3007,3011,3013,3017,3030-3031,3052,3071,3077,3128,3168,3211,3221,3260-3261,3268-3269,3283,3300-3301,3306,3322-3325,3333,3351,3367,3369-3372,3389-3390,3404,3476,3493,3517,3527,3546,3551,3580,3659,3689-3690,3703,3737,3766,3784,3800-3801,3809,3814,3826-3828,3851,3869,3871,3878,3880,3889,3905,3914,3918,3920,3945,3971,3986,3995,3998,4000-4006,4045,4111,4125-4126,4129,4224,4242,4279,4321,4343,4443-4446,4449,4550,4567,4662,4848,4899-4900,4998,5000-5004,5009,5030,5033,5050-5051,5054,5060-5061,5080,5087,5100-5102,5120,5190,5200,5214,5221-5222,5225-5226,5269,5280,5298,5357,5405,5414,5431-5432,5440,5500,5510,5544,5550,5555,5560,5566,5631,5633,5666,5678-5679,5718,5730,5800-5802,5810-5811,5815,5822,5825,5850,5859,5862,5877,5900-5904,5906-5907,5910-5911,5915,5922,5925,5950,5952,5959-5963,5987-5989,5998-6007,6009,6025,6059,6100-6101,6106,6112,6123,6129,6156,6346,6389,6502,6510,6543,6547,6565-6567,6580,6646,6666-6669,6689,6692,6699,6779,6788-6789,6792,6839,6881,6901,6969,7000-7002,7004,7007,7019,7025,7070,7100,7103,7106,7200-7201,7402,7435,7443,7496,7512,7625,7627,7676,7741,7777-7778,7800,7911,7920-7921,7937-7938,7999-8002,8007-8011,8021-8022,8031,8042,8045,8080-8090,8093,8099-8100,8180-8181,8192-8194,8200,8222,8254,8290-8292,8300,8333,8383,8400,8402,8443,8500,8600,8649,8651-8652,8654,8701,8800,8873,8888,8899,8994,9000-9003,9009-9011,9040,9050,9071,9080-9081,9090-9091,9099-9103,9110-9111,9200,9207,9220,9290,9415,9418,9485,9500,9502-9503,9535,9575,9593-9595,9618,9666,9876-9878,9898,9900,9917,9929,9943-9944,9968,9998-10004,10009-10010,10012,10024-10025,10082,10180,10215,10243,10566,10616-10617,10621,10626,10628-10629,10778,11110-11111,11967,12000,12174,12265,12345,13456,13722,13782-13783,14000,14238,14441-14442,15000,15002-15004,15660,15742,16000-16001,16012,16016,16018,16080,16113,16992-16993,17877,17988,18040,18101,18988,19101,19283,19315,19350,19780,19801,19842,20000,20005,20031,20221-20222,20828,21571,22939,23502,24444,24800,25734-25735,26214,27000,27352-27353,27355-27356,27715,28201,30000,30718,30951,31038,31337,32768-32785,33354,33899,34571-34573,35500,38292,40193,40911,41511,42510,44176,44442-44443,44501,45100,48080,49152-49161,49163,49165,49167,49175-49176,49400,49999-50003,50006,50300,50389,50500,50636,50800,51103,51493,52673,52822,52848,52869,54045,54328,55055-55056,55555,55600,56737-56738,57294,57797,58080,60020,60443,61532,61900,62078,63331,64623,64680,65000,65129,65389"/>
<verbose level="0"/>
<debugging level="0"/>
<host starttime="1615414721" endtime="1615414728"><status state="up" reason="localhost-response" reason_ttl="0"/>
<address addr="127.0.0.1" addrtype="ipv4"/>
<hostnames>
<hostname name="localhost" type="PTR"/>
</hostnames>
<ports><extraports state="closed" count="998">
<extrareasons reason="resets" count="998"/>
</extraports>
<port protocol="tcp" portid="22"><state state="open" reason="syn-ack" reason_ttl="64"/><service name="ssh" product="OpenSSH" version="8.2p1 Ubuntu 4ubuntu0.1" extrainfo="Ubuntu Linux; protocol 2.0" ostype="Linux" method="probed" conf="10"><cpe>cpe:/a:openbsd:openssh:8.2p1</cpe><cpe>cpe:/o:linux:linux_kernel</cpe></service></port>
<port protocol="tcp" portid="8888"><state state="open" reason="syn-ack" reason_ttl="64"/><service name="http" product="Tornado httpd" version="6.1" method="probed" conf="10"><cpe>cpe:/a:tornadoweb:tornado:6.1</cpe></service><script id="http-robots.txt" output="1 disallowed entry &#xa;/ "/><script id="http-server-header" output="TornadoServer/6.1"><elem>TornadoServer/6.1</elem>
</script><script id="http-title" output="Jupyter Notebook&#xa;Requested resource was /login?next=%2Ftree%3F"><elem key="title">Jupyter Notebook</elem>
<elem key="redirect_url">/login?next=%2Ftree%3F</elem>
</script></port>
</ports>
<os><portused state="open" proto="tcp" portid="22"/>
<portused state="closed" proto="tcp" portid="1"/>
<portused state="closed" proto="udp" portid="31660"/>
<osmatch name="Linux 2.6.32" accuracy="100" line="55543">
<osclass type="general purpose" vendor="Linux" osfamily="Linux" osgen="2.6.X" accuracy="100"><cpe>cpe:/o:linux:linux_kernel:2.6.32</cpe></osclass>
</osmatch>
</os>
<uptime seconds="992095" lastboot="Sat Feb 27 10:43:53 2021"/>
<distance value="0"/>
<tcpsequence index="262" difficulty="Good luck!" values="8D7A5895,2C71C3B1,C9EEFDE2,6FF3B326,67A00D96,E61D3FF6"/>
<ipidsequence class="All zeros" values="0,0,0,0,0,0"/>
<tcptssequence class="1000HZ" values="3B22277C,3B2227E0,3B222844,3B2228A8,3B22290C,3B222970"/>
<times srtt="20" rttvar="8" to="100000"/>
</host>
<runstats><finished time="1615414728" timestr="Wed Mar 10 22:18:48 2021" elapsed="8.29" summary="Nmap done at Wed Mar 10 22:18:48 2021; 1 IP address (1 host up) scanned in 8.29 seconds" exit="success"/><hosts up="1" down="0" total="1"/>
</runstats>
</nmaprun>
"""

import sys
sys.path.append("/root/drako/services/main")

import lib.Presentation.Web.NmapParser as NmapParser
import lib.Common.Utils.Log as Log
Log.initialize_log("2")



# import traceback
# import re
# import xml.etree.ElementTree as ET
#
# class NmapParser:
#     def __init__(self, nmap_scan):
#         self.nmap_scan = self._escape_illegal_xml_characters(nmap_scan)
#
#         self.root      = ET.fromstring(self.nmap_scan)
#         self.host_tree = list(self.root.iter('host'))[0]
#
#         self.ports = self._get_ports_from_nmap_tree()
#         print("PORTS DATA => %s" % self.ports)
#
#         self.os_info = self._get_os_info_from_nmap_tree()
#         print("OS INFO => %s" % self.ports)
#
#     def get_open_ports(self):
#         return self.ports
#
#     def get_os_info(self):
#         return self.os_info
#
#     def _escape_illegal_xml_characters(self, nmap_scan):
#         return re.sub(u'[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]', '', nmap_scan)
#
#     def _get_ports_from_nmap_tree(self):
#         ports = []
#         element = self.host_tree.find('ports')
#         for data in element:
#             if data.tag == 'port':
#                 port_data = {}
#
#                 try:
#                     state_el           = data.find('state')
#                     port_data['state'] = state_el.attrib['state']
#                 except:
#                     print("ERROR => %s" % traceback.format_exc())
#
#                 try:
#                     state_el           = data.find('service')
#                     port_data['name'] = state_el.attrib['name']
#                 except:
#                     print("ERROR => %s" % traceback.format_exc())
#
#                 try:
#                     state_el                 = data.find('service')
#                     port_data['application'] = state_el.attrib['product']
#                 except:
#                     pass
#
#                 try:
#                     port_data['protocol'] = data.attrib['protocol']
#                 except:
#                     print("ERROR => %s" % traceback.format_exc())
#
#                 try:
#                     port_data['port'] = data.attrib['portid']
#                 except:
#                     print("ERROR => %s" % traceback.format_exc())
#
#                 ports.append(port_data)
#
#         return ports
#
#     # "information": {
#     #     "hostname": "LEGACY",
#     #     "os_flavor": "windows",
#     #     "os_name": "Windows XP"
#     # },
#
#     # <osmatch name="Microsoft Windows XP SP3" accuracy="94" line="83428">
#     # <osclass type="general purpose" vendor="Microsoft" osfamily="Windows" osgen="XP" accuracy="94"><cpe>cpe:/o:microsoft:windows_xp::sp3</cpe></osclass>
#     def _get_os_info_from_nmap_tree(self):
#         root = self.host_tree.find('os')
#         os_data = {}
#         try:
#             best_os_match = root.find('osmatch')
#             os_name         = best_os_match.attrib['name']
#             os_data['os_name'] = os_name
#         except:
#             print("ERROR => %s" % traceback.format_exc())
#
#         try:
#             best_os_match        = root.find('osmatch')
#             os_class             = best_os_match.find('osclass')
#             os_family            = os_class.attrib['osfamily'] #osfamily="Windows"
#             os_data['os_flavor'] = os_family
#         except:
#             print("ERROR => %s" % traceback.format_exc())
#
#         return os_data

parser = NmapParser(nmap_data)

