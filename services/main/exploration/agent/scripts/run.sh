#!/bin/bash

set -e

clear

. /root/drako/scripts/common/constants.env DRAKO_FOLDER_PATH AGENT_BASE_PATH AGENT_FOLDER_PATH MAIN_SERVICE_PATH PREDICTION_API_IP SERVICES_PATH

usage() { echo "Usage: $0 -r <playbook|cli|regenerate_actions|bash> [-p hackthebox/lame.playbook]" 1>&2; exit 1; }

# echo $@;
while getopts ":r:p:i:" o; do
    case "${o}" in
        r)
            RUN_MODE=${OPTARG}
            if [[ "$RUN_MODE" != "playbook" && "$RUN_MODE" != "cli" && "$RUN_MODE" != "cli_no_build" && "$RUN_MODE" != "bash" && "$RUN_MODE" != "regenerate_actions" && "$RUN_MODE" != "regenerate_actions_no_build" && "$RUN_MODE" != "replay" ]]; then
            	echo "UNKNOWN RUN_MODE value. Allowed are replay/playbook/cli/regenerate_actions"
            	usage
            	exit 1
            fi
            ;;
        p)
            PLAYBOOK=${OPTARG}
            # DEFAULT IS hackthebox/lame.playbook
            ;;
        i)
            EPISODE_ID=${OPTARG}
            ;;
        *)
            echo "UNKNOWN OPTION ${OPTARG}"
            usage
            exit 0
            ;;
    esac
done

if [ -z "$RUN_MODE" ]; then
    echo "You need to specify -r RUN_MODE (cli or playbook)"
    exit 1
fi

if [ -z "$PLAYBOOK" ]; then
    PLAYBOOK="hackthebox/lame.playbook"
fi

LOCAL_IP=$(ifconfig tun0|grep 'inet'|awk '{print $2}'|head -n1)

echo "Stopping containers.."
docker stop $(docker ps -aq --filter name="agent_playbook|agent_regenerate_actions") || true
docker container rm -f $(docker container ls -aq --filter name="agent_playbook|agent_regenerate_actions") || true

if [[ "$RUN_MODE" != "cli_no_build" && "$RUN_MODE" != "regenerate_actions_no_build" ]]; then
    echo "Building containers.."
    docker build -f $AGENT_BASE_PATH/Dockerfile.agent.base -t agent-base $SERVICES_PATH/
fi
docker build -f $AGENT_FOLDER_PATH/Dockerfile.agent -t agent $MAIN_SERVICE_PATH/

echo "RUN_MODE   = ${RUN_MODE}"
echo "LOCAL_IP   = ${LOCAL_IP}"
echo "PLAYBOOK   = ${PLAYBOOK}"
echo "EPISODE_ID = ${EPISODE_ID}"

APACHE_PORT=$(shuf -i 50000-51000 -n 1)
SRV_PORT=$(shuf -i 51000-52000 -n 1)
REVSHELL_PORT=$(shuf -i 52000-53000 -n 1)
REVSHELL_PORT_2=$(shuf -i 53000-54000 -n 1)

AGENT_NAME="agent_cli_$RANDOM"

PREDICTION_API_IP=$(ifconfig enp1s0|grep 'inet'|awk '{print $2}'|head -n1)

if [[ $RUN_MODE == "cli" || $RUN_MODE == "cli_no_build" ]]; then
    clear
	docker run --name $AGENT_NAME -v /share:/share -e "PREDICTION_API_IP=$PREDICTION_API_IP" -e "CONTAINER_NAME=$AGENT_NAME" -e "LOCAL_IP=$LOCAL_IP" \
	-e "APACHE_PORT=$APACHE_PORT" -e "SRV_PORT=$SRV_PORT" -e "REVSHELL_PORT=$REVSHELL_PORT" -e "REVSHELL_PORT_2=$REVSHELL_PORT_2" -p $LOCAL_IP:$APACHE_PORT:$APACHE_PORT/tcp -p $LOCAL_IP:$SRV_PORT:$SRV_PORT/tcp  \
	-p $LOCAL_IP:$REVSHELL_PORT:$REVSHELL_PORT/tcp -p $LOCAL_IP:$REVSHELL_PORT_2:$REVSHELL_PORT_2/tcp -it agent /app/init.sh -r cli -d2
elif [[ $RUN_MODE == "playbook" ]]; then
    echo "Starting playbook $PLAYBOOK.."
	docker run --name agent_playbook -v /share:/share -e "PREDICTION_API_IP=$PREDICTION_API_IP" -e "CONTAINER_NAME=agent_playbook" -e "LOCAL_IP=$LOCAL_IP" \
	-e "APACHE_PORT=$APACHE_PORT" -e "SRV_PORT=$SRV_PORT" -e "REVSHELL_PORT=$REVSHELL_PORT"  -e "REVSHELL_PORT_2=$REVSHELL_PORT_2" -p $LOCAL_IP:$APACHE_PORT:$APACHE_PORT/tcp -p $LOCAL_IP:$SRV_PORT:$SRV_PORT/tcp  \
	-p $LOCAL_IP:$REVSHELL_PORT:$REVSHELL_PORT/tcp -p $LOCAL_IP:$REVSHELL_PORT_2:$REVSHELL_PORT_2/tcp -it agent /app/init.sh -r playbook -d2 -n /app/playbooks/$PLAYBOOK
elif [[ $RUN_MODE == "replay" ]]; then
    echo "Starting replay for episode_id $EPISODE_ID.."
    docker run --name agent_replay -v /share:/share -e "PREDICTION_API_IP=$PREDICTION_API_IP" -e "CONTAINER_NAME=agent_replay" -e "LOCAL_IP=$LOCAL_IP" \
    -e "APACHE_PORT=$APACHE_PORT" -e "SRV_PORT=$SRV_PORT" -e "REVSHELL_PORT=$REVSHELL_PORT"  -e "REVSHELL_PORT_2=$REVSHELL_PORT_2" -p $LOCAL_IP:$APACHE_PORT:$APACHE_PORT/tcp -p $LOCAL_IP:$SRV_PORT:$SRV_PORT/tcp  \
    -p $LOCAL_IP:$REVSHELL_PORT:$REVSHELL_PORT/tcp -p $LOCAL_IP:$REVSHELL_PORT_2:$REVSHELL_PORT_2/tcp -it agent /app/init.sh -r replay -d2 -i $EPISODE_ID
elif [[ $RUN_MODE == "regenerate_actions" || $RUN_MODE == "regenerate_actions_no_build" ]]; then
    clear
    docker run --name agent_cli -v /share:/share -e "PREDICTION_API_IP=$PREDICTION_API_IP" -e "CONTAINER_NAME=agent_regenerate_actions" -e "LOCAL_IP=$LOCAL_IP" \
    -e "APACHE_PORT=$APACHE_PORT" -e "SRV_PORT=$SRV_PORT" -e "REVSHELL_PORT=$REVSHELL_PORT"  -e "REVSHELL_PORT_2=$REVSHELL_PORT_2" -p $LOCAL_IP:$APACHE_PORT:$APACHE_PORT/tcp -p $LOCAL_IP:$SRV_PORT:$SRV_PORT/tcp  \
    -p $LOCAL_IP:$REVSHELL_PORT:$REVSHELL_PORT/tcp -p $LOCAL_IP:$REVSHELL_PORT_2:$REVSHELL_PORT_2/tcp -it agent /app/init.sh -r cli -d2 -z 1
elif [[ $RUN_MODE == "bash" ]]; then
    clear
    docker run --name agent_cli -v /share:/share -e "PREDICTION_API_IP=$PREDICTION_API_IP" -e "CONTAINER_NAME=agent_cli" -e "LOCAL_IP=$LOCAL_IP" \
    -e "APACHE_PORT=$APACHE_PORT" -e "SRV_PORT=$SRV_PORT" -e "REVSHELL_PORT=$REVSHELL_PORT"  -e "REVSHELL_PORT_2=$REVSHELL_PORT_2" -p $LOCAL_IP:$APACHE_PORT:$APACHE_PORT/tcp -p $LOCAL_IP:$SRV_PORT:$SRV_PORT/tcp  \
    -p $LOCAL_IP:$REVSHELL_PORT:$REVSHELL_PORT/tcp -p $LOCAL_IP:$REVSHELL_PORT_2:$REVSHELL_PORT_2/tcp -it agent /bin/bash
else
	echo "UNKNOWN RUNMODE $RUN_MODE"
fi   

