#!/bin/bash
set -e

if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

usage() { echo "Usage: $0 [-e <network|dreamatorium>] [-g target] [-r <cli>] [-r <playbook> -n <playbook.txt>] [-r <replay> -i <episode_id>] [-r <agent> -a <random|GoExplore|NNRecommendationTester> -z <?>] [-d <log_level>] [-s <steps>] [-y <timeout>]" 1>&2; exit 1; }

# TODO: REVIEW IF THIS IS NEEDED
# cleanup() {
#     echo "Killing metasploit sessions"
#     msfconsole -x 'sessions -K; exit;' -q
#     exit
# }
# trap cleanup INT TERM

# DEFAULTS
LOG_LEVEL=0
STEPS=30
ENVIRONMENT="network"
CLI_IN_DOCKER="NO"

echo $@;
while getopts ":e:r:t:d:a:n:s:g:z:m:i:y:" o; do
    case "${o}" in
        e)
            ENVIRONMENT=${OPTARG}
            if [[ "$ENVIRONMENT" != "dreamatorium" && "$ENVIRONMENT" != "network" ]]; then
            	echo "UNKNOWN ENVIRONMENT value. Allowed are network/dreamatorium"
            	usage
            	exit 1
            fi
            ;;
        r)
            RUNNER=${OPTARG}
            if [[ "$RUNNER" != "agent" && "$RUNNER" != "cli" && "$RUNNER" != "playbook" && "$RUNNER" != "test" && "$RUNNER" != "replay" ]]; then
            	echo "UNKNOWN RUNNER value. Allowed are agent/cli/replay/playbook/test"
            	usage
            	exit 1
            fi
            ;;
        n)
            PLAYBOOK_NAME=${OPTARG}
            if [[ "$PLAYBOOK_NAME" == "" ]]; then
                echo "EMPTY PLAYBOOK_NAME value. A value must be set!"
                usage
                exit 1
            fi
            ;;
        a)
            AGENT=${OPTARG}
            if [[ "$AGENT" != "random" && "$AGENT" != "GoExplore" && "$AGENT" != "NNRecommendationTester" ]]; then
                echo "UNKNOWN AGENT value. Available are random / GoExplore / NNRecommendationTester"
                usage
                exit 1
            fi
            ;;
        d)
            LOG_LEVEL=${OPTARG}
            if [[ "$LOG_LEVEL" != "0" && "$LOG_LEVEL" != "1" && "$LOG_LEVEL" != "2" ]]; then
                echo "UNKNOWN LOG_LEVEL value. Available are 0,1,2"
                usage
                exit 1
            fi
            ;;
        m)
            TEST_MODULE=${OPTARG}
            ;;
        i)
            EPISODE_ID=${OPTARG}
            ;;
        s)
            STEPS=${OPTARG}
            ;;
        t)
            TRAINING_ID=${OPTARG}
            ;;
        g)
            TARGET=${OPTARG}
            ;;
        z)
            REGENERATE_ACTIONS=${OPTARG}
            ;;
        y)
            TIMEOUT=${OPTARG}
            ;;
        *)
            echo "UNKNOWN OPTION ${OPTARG}"
            usage
            exit 0
            ;;
    esac
done
# shift all the parameters passed
shift $((OPTIND-1))

########################################################################
########################################################################
########################################################################

if ls /docker-env 1>/dev/null 2>&1; then
    export INSIDE_DOCKER=1
    export CONTAINER_ID=$(hostname)

    if [[ "$RUNNER" == "cli" ]]; then
        CLI_IN_DOCKER="YES"
    fi
else
    echo "Not inside docker container!"
fi

if [ -z "$APACHE_PORT" ]; then
    export APACHE_PORT=80
fi

if [ -z "$MSFRPCD_PORT" ]; then
    export MSFRPCD_PORT=5555
fi

if [ -z "$REGENERATE_ACTIONS" ]; then
    export REGENERATE_ACTIONS=0
fi

########################################################################
########################################################################
########################################################################

echo "ENVIRONMENT        = ${ENVIRONMENT}"
echo "RUNNER             = ${RUNNER}"
echo "PLAYBOOK_NAME      = ${PLAYBOOK_NAME}"
echo "LOG_LEVEL          = ${LOG_LEVEL}"
echo "APACHE_PORT        = ${APACHE_PORT}"
echo "MSFRPCD_PORT       = ${MSFRPCD_PORT}"
echo "TRAINING_ID        = ${TRAINING_ID}"
echo "CLI_IN_DOCKER      = ${CLI_IN_DOCKER}"
echo "CONTAINER_ID       = ${CONTAINER_ID}"
echo "INSIDE_DOCKER      = ${INSIDE_DOCKER}"
echo "REGENERATE_ACTIONS = ${REGENERATE_ACTIONS}"
echo "TEST_MODULE        = ${TEST_MODULE}"
echo "EPISODE_ID         = ${EPISODE_ID}"
echo "LOCAL_IP           = ${LOCAL_IP}"
echo "PREDICTION_API_IP  = ${PREDICTION_API_IP}"
echo "TIMEOUT            = ${TIMEOUT}"
echo "TARGET             = ${TARGET}"

if [ -z "$RUNNER" ]; then
    echo "A a RUNNER must be set!"
    usage
    exit 1
fi

if [[ "$RUNNER" == "agent" ]]; then
    if [ -z "$AGENT" ]; then
        echo "An agent must be set!"
        usage
        exit 1
    fi

    if [ -z "$TRAINING_ID" ]; then
        echo "A TRAINING_ID must be set for an AGENT!"
        usage
        exit 1
    fi
fi

if [[ "$RUNNER" == "playbook" ]]; then
    if [ -z "$PLAYBOOK_NAME" ]; then
        echo "EMPTY $PLAYBOOK_NAME value. A value must be set!"
        usage
        exit 1
    fi
fi

if [[ "$RUNNER" == "agent" ||  "$RUNNER" == "replay" || "$RUNNER" == "playbook" || "$RUNNER" == "test" || "$CLI_IN_DOCKER" == "YES" ]]; then
    if [[ "$ENVIRONMENT" == "network" ]]; then # No need to setup metasploit on dreamatorium
        if [ -n "$APACHE_PORT" ]; then
            echo "Updating configuration file"
            sed -i "s/APACHE_PORT/$APACHE_PORT/g" /etc/apache2/sites-enabled/000-default.conf
            sed -i "s/APACHE_PORT/$APACHE_PORT/g" /etc/apache2/ports.conf
        fi
        echo "Starting apache webserver.."
        service apache2 start

        if pgrep -x "postgres" > /dev/null; then
            echo "postgresql is already running"
        else
            echo "=====================" 
            echo "Starting the postgresql service"
            /etc/init.d/postgresql start
            echo "=====================" 
        fi

        # ### ADDING EXCEPTION FOR WARNING ON MSFRPCD
        # if grep -q 'Warning[:deprecated] = false' "/usr/bin/msfrpcd"; then
        #   echo 'Warning[:deprecated] = false'
        # fi
        if [[ "$INSIDE_DOCKER" == "1" ]]; then
            if pgrep -f "msfrpcd" > /dev/null; then
                echo "Killing msfrpcd..."
                sudo kill -9 "$(pgrep -f "msfrpc" -n)"
            fi

            echo "Starting the msfrpcd process.."
            msfrpcd -P "Amdspon200ss11a" -a 127.0.0.1 -p $MSFRPCD_PORT -S
            
            # Now wait for service to be up
            python3 scripts/msfrpc_check.py

            # ENABLE CONSOLE LOGGING
            #msfconsole -x'set ConsoleLogging true; set VERBOSE true; set LogLevel 3; set SessionLogging true; set TimestampOutput true;exit;' -q
        fi
    fi
else
    echo "Starting apache webserver.."
    service apache2 start
    echo "Starting the postgresql service"
    /etc/init.d/postgresql start

    if netstat -ltnp |grep ':555'>/dev/null; then
        echo "Killing msfrpcd process"
        kill $(netstat -ltnp |grep ':555'|awk '{print $7}'|cut -d '/' -f 1)
    fi
    
    echo "Starting the msfrpcd process.."
    msfrpcd -P "Amdspon200ss11a" -a 127.0.0.1 -p $MSFRPCD_PORT -S
    sleep 4
fi

if [[ $RUNNER == "cli" ]]; then
    #clear  
    COMMAND="python3 agent.py --log-level=$LOG_LEVEL --runner=cli --environment=$ENVIRONMENT --steps=$STEPS --target=$TARGET --regenerate_actions=$REGENERATE_ACTIONS"
elif [[ $RUNNER == "playbook" ]]; then
    COMMAND="python3 agent.py --playbook=$PLAYBOOK_NAME --log-level=$LOG_LEVEL --runner=playbook --environment=$ENVIRONMENT --steps=$STEPS --target=$TARGET"
elif [[ $RUNNER == "replay" ]]; then
    COMMAND="python3 agent.py --episode_id=$EPISODE_ID --log-level=$LOG_LEVEL --runner=replay --environment=$ENVIRONMENT --steps=$STEPS --target=$TARGET"
elif [[ $RUNNER == "agent" ]]; then   
    COMMAND="timeout $TIMEOUT python3 agent.py --log-level=$LOG_LEVEL --runner=agent --agent=$AGENT --environment=$ENVIRONMENT --steps=$STEPS --training_id=$TRAINING_ID"
elif [[ $RUNNER == "test" ]]; then
    COMMAND="/usr/bin/python3 -m unittest discover -v $TEST_MODULE"
fi

echo "$COMMAND"
$COMMAND