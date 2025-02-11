import os

LOGS_FOLDER_PATH     = "/share/logs"
NETWORKS_FOLDER_PATH = "/share/networks"
MYSQL_FOLDER_PATH    = "/share/mysql"
DRAKO_FOLDER_PATH    = "/root/drako"
VISUALIZER_PATH      = '/app/graphs'

SERVICES_PATH     = f"{DRAKO_FOLDER_PATH}/services"
AGENT_BASE_PATH   = f"{SERVICES_PATH}/agent-base"
MAIN_SERVICE_PATH = f"{SERVICES_PATH}/main"

TRAINING_FOLDER_PATH = f"{MAIN_SERVICE_PATH}/training"
LEARNER_FOLDER_PATH = f"{TRAINING_FOLDER_PATH}/learner"
ORCHESTRATOR_FOLDER_PATH = f"{TRAINING_FOLDER_PATH}/orchestrator"
ORCHESTRATOR_SCRIPTS_PATH = f"{ORCHESTRATOR_FOLDER_PATH}/scripts"

CITY_FOLDER_PATH = f"{TRAINING_FOLDER_PATH}/city"

EXPLORATION_FOLDER_PATH = f"{MAIN_SERVICE_PATH}/exploration"
AGENT_FOLDER_PATH       = f"{EXPLORATION_FOLDER_PATH}/agent"
RECON_FOLDER_PATH       = f"{EXPLORATION_FOLDER_PATH}/recon"
RECON_SCRIPTS_PATH      = f"{RECON_FOLDER_PATH}/scripts"
VPN_FOLDER_PATH         = f"{EXPLORATION_FOLDER_PATH}/vpn"
VULNAPP_FOLDER_PATH     = f"{EXPLORATION_FOLDER_PATH}/vulnapp"

RECOMMENDATION_FOLDER_PATH = f"{MAIN_SERVICE_PATH}/recommendation"
PREDICTION_FOLDER_PATH = f"{RECOMMENDATION_FOLDER_PATH}/prediction"

PRESENTATION_FOLDER_PATH = f"{MAIN_SERVICE_PATH}/presentation"
WEB_FOLDER_PATH = f"{PRESENTATION_FOLDER_PATH}/web"
VISUALIZER_FOLDER_PATH = f"{PRESENTATION_FOLDER_PATH}/visualizer"

# METASPLOIT
RESOURCES_FILE_PATH = f"{DRAKO_FOLDER_PATH}/resources"
METASPLOIT_FILE_PATH = "shared/resources/metasploit_actions"

ROOT_INVENTORY_LOCATION = "/root/inventory"

LEARNER_IP = "54.195.65.144"

# PREDICTIONS 
DQN_FAMILY_NAME    = "dqn"
COMMON_FAMILY_NAME = "COMMON_FAMILY_NAME"

PREDICTION_TRAINING_API_PORT = "4000"
PREDICTION_WEB_API_PORT      = "4001"

CITY_IP="192.168.1.12"
CITY_SSH_PORT=22
CITY_MANAGEMENT_PORT=4000

CASTLE_IP="192.168.1.10"
CASTLE_SSH_PORT="22"

##########################################################
#################### DATABASES ###########################
##########################################################

# TODO: Move this to use a static name like prod
DRAGON_DB_IDENTIFIER = "dragon"

## DRAGON
DRAGON_DB_USER = "root"
DRAGON_DB_PWD  = "XXXXXX"
DRAGON_DB_PORT = 6612

PRIMARY_KEYS_MAP = {
    "episode":              "episode_id",
    "game":                 "game_id",
    "raw_observation":      "raw_observation_id",
    "step":                 "transition_id",
    "test_episode":         "test_episode_id",
    "training":             "training_id",
    "training_game":        "training_game_id",
    "training_states":      "training_state_id",
    "training_step":        "training_step_id",
    "training_target":      "target_id",
    "training_target_path": "target_path_id",
    "benchmark":            "benchmark_id"
}

## DRAGON STAGING
LOCALHOST                   = "127.0.0.1"
DRAGON_STAGING_DB_IP        = "192.168.1.12"

DRAGON_STAGING_SAMPLE_TABLE = "training_game"
DRAGON_STAGING_TRAINING_DB_IP = DRAGON_STAGING_DB_IP #PARROT_IP # This is fixed to PARROT for training

## DRAGON PROD
DRAGON_PROD_DNS              = DRAGON_STAGING_DB_IP #"dragon.c0mrsgj6viv5.eu-west-1.rds.amazonaws.com"
DRAGON_PROD_DB_NAME          = "dragon"
DRAGON_PROD_SAMPLE_TABLE     = "training_game"
DRAGON_PROD_TABLES           = ["episode", "game", "raw_observation", "step", "test_episode", "training", "training_game", "training_target", "training_target_path"]
DRAGON_PROD_BENCHMARK_TABLES = ["benchmark", "benchmark_step"]

def get_dragon_staging_db():
    castle_name = os.getenv('CASTLE_NAME')

    dragon_staging_db_name = "staging"
    if castle_name != None:
        dragon_staging_db_name += f"_{castle_name}"
    
    return dragon_staging_db_name

## DRAGON TEST
DRAGON_TEST_DB_IP        = DRAGON_STAGING_DB_IP
DRAGON_TEST_DB_NAME      = "dragon_test"
DRAGON_TEST_SAMPLE_TABLE = "training_game"

# ASSISTANT
ASSISTANT_DB_DNS  = DRAGON_STAGING_DB_IP #"rds.prod.drako.ai"
ASSISTANT_DB_NAME = "assistant"
ASSISTANT_DB_PWD  = DRAGON_DB_PWD
ASSISTANT_SAMPLE_TABLE = "conversations"

##########################################################
####################### AGENT ############################
##########################################################

# DEFAULT PORTS
AGENT_DEFAULT_APACHE_PORT      = "80"
AGENT_DEFAULT_POSTGRESSQL_PORT = "5432"
AGENT_DEFAULT_MSFRPC_PORT      = "5555"
AGENT_DEFAULT_SRV_PORT         = "1000"
AGENT_DEFAULT_REVSHELL_PORT    = "1001"
AGENT_DEFAULT_REVSHELL_PORT_2  = "1002"

PROFILE_EXPLORE = "EXPLORE"

# EXTRA
GAME_TYPE_NETWORK = "NETWORK"
GAME_TYPE_PRIVESC = "PRIVESC"
INITIAL_STATE = {
    GAME_TYPE_NETWORK: "FCE91",
    GAME_TYPE_PRIVESC: "", #TEC-446: THERE IS NO SINGLE INITIAL STATE FOR PRIVESC, WE NEED TO ADAPT FOR THIS
}

GAME_TYPES = [GAME_TYPE_NETWORK, GAME_TYPE_PRIVESC]

GRAPH_KEY_STATE_SUPER_SESSION = "SUPER USER"
GLOBAL_TARGET = "GLOBAL"

# WEB
LEX_AWS_ACCESS_KEY = "F"
LEX_AWS_SECRET_KEY = "X"
WEB_AWS_REGION     = "eu-west-1"
WEB_PREDICTION_API = LOCALHOST
WEB_DNS            = "46.137.18.192" #"web.prod.drako.ai"
WEB_SSH_PORT       = "22"

# AWS
AWS_REGION = "eu-west-1"
AWS_ACCOUNT_ID = "FFFF"
STATIC_BUCKET_NAME = "drako.ai"
STATIC_TEMPLATE_LOCATION = f"{MAIN_SERVICE_PATH}/presentation/web/resources/Robogard-final/"

############
############
############

S3_NN_NAME = {
    GAME_TYPE_NETWORK: "network.pt",
    GAME_TYPE_PRIVESC: "privesc.pt"
}
S3_TRAINING_DATA_DUMP = "training_data.gz"
S3_RANDOM_KEY         = "GGGG"

###

OPEN_PORT="open"

### REWARD
REWARD_FOR_REGULAR_USER_AMOUNT=200
REWARD_FOR_SUPER_USER_AMOUNT=400

REWARD_FOR_REGULAR_USER_SESSION_KEY = "new_regular_user_session_added"
REWARD_FOR_SUPER_USER_SESSION_KEY   = "new_super_user_session_added"

SUPER_USERS_LIST = ['root', 'system', 'administrator', 'admin']

VM_SOURCE_HACKTHEBOX = "hackthebox"
VM_SOURCE_GENERAL    = "general"
VM_SOURCE_VULNHUB    = "vulnhub"

VIRSH_TARGET_SOURCES = [VM_SOURCE_HACKTHEBOX, VM_SOURCE_GENERAL, VM_SOURCE_VULNHUB]

VMDK_DISK_TYPE = "vmdk"

VIRSH_SOCKET_LOCATION_DOCKER    = "/app/libvirt-sock"
VIRSH_SOCKET_LOCATION_CITY      = "/run/libvirt/libvirt-sock"

VIRSH_CONFIG_FILE_LOCATION       = "/etc/libvirt/qemu"

VIRSH_IMAGE_FILE_LOCATION       = "/var/lib/libvirt/images"
VIRSH_IMAGE_EPHEMERAL_LOCATION  = "/data/ephemeral/target_images"

VIRSH_DOCKER_TARGET_FOLDER_PATHS = "/app/resources"
VIRSH_CITY_TARGET_FOLDER_PATHS   = "/root/drako/services/main/training/city/resources"
VIRSH_DEFAULT_TARGET_XML         = f"{VIRSH_CITY_TARGET_FOLDER_PATHS}/default-target.xml"

# LONG CONSTANTS

TCP_PORT_LIST_NUM = ['80', '23', '443', '21', '22', '25', '3389', '110', '445', '139', '143', '53', '135', '3306',
                     '8080', '1723', '111', '995', '993', '5900', '1025', '587', '8888', '199', '1720', '465', '548',
                     '113', '81', '6001', '10000', '514', '5060', '179', '1026', '2000', '8443', '8000', '32768', '554',
                     '26', '1433', '49152', '2001', '515', '8008', '49154', '1027', '5666', '646', '5000', '5631',
                     '631', '49153', '8081', '2049', '88', '79', '5800', '106', '2121', '1110', '49155', '6000', '513',
                     '990', '5357', '427', '49156', '543', '544', '5101', '144', '7', '389', '8009', '3128', '444',
                     '9999', '5009', '7070', '5190', '3000', '5432', '1900', '3986', '13', '1029', '9', '5051', '6646',
                     '49157', '1028', '873', '1755', '2717', '4899', '9100', '119', '37', '1000', '3001', '5001', '82',
                     '10010', '1030', '9090', '2107', '1024', '2103', '6004', '1801', '5050', '19', '8031', '1041',
                     '255', '1048', '1049', '1053', '1054', '1056', '1064', '1065', '2967', '3703', '17', '808', '3689',
                     '1031', '1044', '1071', '5901', '100', '9102', '1039', '2869', '4001', '5120', '8010', '9000',
                     '2105', '636', '1038', '2601', '1', '7000', '1066', '1069', '625', '311', '280', '254', '4000',
                     '1761', '5003', '2002', '1998', '2005', '1032', '1050', '6112', '3690', '1521', '2161', '1080',
                     '6002', '2401', '902', '4045', '787', '7937', '1058', '2383', '32771', '1033', '1040', '1059',
                     '50000', '5555', '10001', '1494', '3', '593', '2301', '3268', '7938', '1022', '1234', '1035',
                     '1036', '1037', '1074', '8002', '9001', '464', '497', '1935', '2003', '6666', '6543', '24', '1352',
                     '3269', '1111', '407', '500', '20', '2006', '1034', '1218', '3260', '15000', '4444', '264', '33',
                     '2004', '1042', '42510', '999', '3052', '1023', '222', '1068', '888', '7100', '563', '1717', '992',
                     '2008', '32770', '7001', '32772', '2007', '8082', '5550', '512', '1043', '2009', '5801', '1700',
                     '2701', '7019', '50001', '4662', '2065', '42', '2010', '161', '2602', '3333', '9535', '5100',
                     '2604', '4002', '5002', '1047', '1051', '1052', '1055', '1060', '1062', '1311', '2702', '3283',
                     '4443', '5225', '5226', '6059', '6789', '8089', '8192', '8193', '8194', '8651', '8652', '8701',
                     '9415', '9593', '9594', '9595', '16992', '16993', '20828', '23502', '32769', '33354', '35500',
                     '52869', '55555', '55600', '64623', '64680', '65000', '65389', '1067', '13782', '366', '5902',
                     '9050', '85', '1002', '5500', '1863', '1864', '5431', '8085', '10243', '45100', '49999', '51103',
                     '49', '90', '6667', '1503', '6881', '27000', '340', '1500', '8021', '2222', '5566', '8088', '8899',
                     '9071', '1501', '5102', '6005', '9101', '9876', '32773', '32774', '163', '5679', '146', '648',
                     '1666', '901', '83', '3476', '5004', '5214', '8001', '8083', '8084', '9207', '14238', '30', '912',
                     '12345', '2030', '2605', '6', '541', '4', '1248', '3005', '8007', '306', '880', '2500', '1086',
                     '1088', '1097', '2525', '4242', '8291', '9009', '52822', '900', '6101', '2809', '7200', '211',
                     '800', '987', '1083', '12000', '32775', '705', '711', '20005', '6969', '13783', '1045', '1046',
                     '1057', '1061', '1063', '1070', '1072', '1073', '1075', '1077', '1078', '1079', '1081', '1082',
                     '1085', '1093', '1094', '1096', '1098', '1099', '1100', '1104', '1106', '1107', '1108', '1148',
                     '1169', '1272', '1310', '1687', '1718', '1783', '1840', '1947', '2100', '2119', '2135', '2144',
                     '2160', '2190', '2260', '2381', '2399', '2492', '2607', '2718', '2811', '2875', '3017', '3031',
                     '3071', '3211', '3300', '3301', '3323', '3325', '3351', '3367', '3404', '3551', '3580', '3659',
                     '3766', '3784', '3801', '3827', '3998', '4003', '4126', '4129', '4449', '5030', '5222', '5269',
                     '5414', '5633', '5718', '5810', '5825', '5877', '5910', '5911', '5925', '5959', '5960', '5961',
                     '5962', '5987', '5988', '5989', '6123', '6129', '6156', '6389', '6580', '6788', '6901', '7106',
                     '7625', '7627', '7741', '7777', '7778', '7911', '8086', '8087', '8181', '8222', '8333', '8400',
                     '8402', '8600', '8649', '8873', '8994', '9002', '9010', '9011', '9080', '9220', '9290', '9485',
                     '9500', '9502', '9503', '9618', '9900', '9968', '10002', '10012', '10024', '10025', '10566',
                     '10616', '10617', '10621', '10626', '10628', '10629', '11110', '11967', '13456', '14000', '14442',
                     '15002', '15003', '15660', '16001', '16016', '16018', '17988', '19101', '19801', '19842', '20000',
                     '20031', '20221', '20222', '21571', '22939', '24800', '25734', '27715', '28201', '30000', '30718',
                     '31038', '32781', '32782', '33899', '34571', '34572', '34573', '40193', '48080', '49158', '49159',
                     '49160', '50003', '50006', '50800', '57294', '58080', '60020', '63331', '65129', '89', '691',
                     '212', '1001', '1999', '2020', '32776', '2998', '6003', '7002', '50002', '32', '898', '2033',
                     '3372', '5510', '99', '425', '749', '5903', '43', '458', '5405', '6106', '6502', '7007', '13722',
                     '1087', '1089', '1124', '1152', '1183', '1186', '1247', '1296', '1334', '1580', '1782', '2126',
                     '2179', '2191', '2251', '2522', '3011', '3030', '3077', '3261', '3369', '3370', '3371', '3493',
                     '3546', '3737', '3828', '3851', '3871', '3880', '3918', '3995', '4006', '4111', '4446', '5054',
                     '5200', '5280', '5298', '5822', '5859', '5904', '5915', '5922', '5963', '7103', '7402', '7435',
                     '7443', '7512', '8011', '8090', '8100', '8180', '8254', '8500', '8654', '9091', '9110', '9666',
                     '9877', '9943', '9944', '9998', '10004', '10778', '15742', '16012', '18988', '19283', '19315',
                     '19780', '24444', '27352', '27353', '27355', '32784', '49163', '49165', '49175', '50389', '50636',
                     '51493', '55055', '56738', '61532', '61900', '62078', '1021', '9040', '32777', '32779', '616',
                     '666', '700', '2021', '32778', '84', '545', '1112', '1524', '2040', '4321', '5802', '38292',
                     '49400', '1084', '1600', '2048', '2111', '3006', '32780', '2638', '6547', '6699', '9111', '16080',
                     '555', '667', '720', '801', '1443', '1533', '2034', '2106', '5560', '6007', '1090', '1091', '1114',
                     '1117', '1119', '1122', '1131', '1138', '1151', '1175', '1199', '1201', '1271', '1862', '2323',
                     '2393', '2394', '2608', '2725', '2909', '3003', '3168', '3221', '3322', '3324', '3390', '3517',
                     '3527', '3800', '3809', '3814', '3826', '3869', '3878', '3889', '3905', '3914', '3920', '3945',
                     '3971', '4004', '4005', '4279', '4445', '4550', '4567', '4848', '4900', '5033', '5061', '5080',
                     '5087', '5221', '5440', '5544', '5678', '5730', '5811', '5815', '5850', '5862', '5906', '5907',
                     '5950', '5952', '6025', '6100', '6510', '6565', '6566', '6567', '6689', '6692', '6779', '6792',
                     '6839', '7025', '7496', '7676', '7800', '7920', '7921', '7999', '8022', '8042', '8045', '8093',
                     '8099', '8200', '8290', '8292', '8300', '8383', '8800', '9003', '9081', '9099', '9200', '9418',
                     '9575', '9878', '9898', '9917', '10003', '10009', '10180', '10215', '11111', '12174', '12265',
                     '14441', '15004', '16000', '16113', '17877', '18040', '18101', '19350', '25735', '26214', '27356',
                     '30951', '32783', '32785', '40911', '41511', '44176', '44501', '49161', '49167', '49176', '50300',
                     '50500', '52673', '52848', '54045', '54328', '55056', '56737', '57797', '60443', '70', '417',
                     '617', '714', '722', '777', '981', '1009', '2022', '4224', '4998', '6346', '301', '524', '668',
                     '765', '1076', '2041', '5999', '10082', '259', '416', '1007', '1417', '1434', '1984', '2038',
                     '2068', '4343', '6009', '7004', '44443', '109', '687', '726', '911', '1010', '1461', '2035',
                     '2046', '4125', '6006', '7201', '9103', '125', '481', '683', '903', '1011', '1455', '2013', '2043',
                     '2047', '6668', '6669', '256', '406', '783', '843', '2042', '2045', '5998', '9929', '31337',
                     '44442', '1092', '1095', '1102', '1105', '1113', '1121', '1123', '1126', '1130', '1132', '1137',
                     '1141', '1145', '1147', '1149', '1154', '1163', '1164', '1165', '1166', '1174', '1185', '1187',
                     '1192', '1198', '1213', '1216', '1217', '1233', '1236', '1244', '1259', '1277', '1287', '1300',
                     '1301', '1309', '1322', '1328', '1556', '1583', '1594', '1641', '1658', '1688', '1719', '1721',
                     '1805', '1812', '1839', '1875', '1914', '1971', '1972', '1974', '2099', '2170', '2196', '2200',
                     '2288', '2366', '2382', '2557', '2710', '2800', '2910', '2920', '2968', '3007', '3013']
UDP_PORT_LIST_NUM = ['631', '161', '137', '123', '138', '1434', '445', '135', '67', '53', '139', '500', '68', '520',
                     '1900', '4500', '514', '49152', '162', '69', '5353', '111', '49154', '1701', '998', '996', '997',
                     '999', '3283', '49153', '1812', '136', '2222', '2049', '32768', '5060', '1025', '1433', '3456',
                     '80', '20031', '1026', '7', '1646', '1645', '593', '518', '2048', '626', '1027', '177', '1719',
                     '427', '497', '4444', '1023', '65024', '19', '9', '49193', '1029', '49', '88', '1028', '17185',
                     '1718', '49186', '2000', '31337', '49192', '49201', '515', '2223', '443', '49181', '1813', '120',
                     '158', '49200', '3703', '32815', '17', '5000', '32771', '33281', '1030', '623', '1022', '32769',
                     '5632', '10000', '49156', '49182', '49191', '49194', '9200', '30718', '49185', '49188', '49190']


# RECON

RECON_PROD_DB_NAME = "recon"
RECON_VM_NAME      = RECON_PROD_DB_NAME
RECON_DB_IP        = "192.168.1.12"
RECON_ES_IP        = "192.168.1.12"

# SHARED

TUNNEL_SSH = "34.249.203.30"
ML_IP      = "54.75.24.218"
