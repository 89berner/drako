#!/bin/bash

LOCKFILE=/tmp/run_vpn_lockfile

cleanup() {
    echo "Caught SIGTERM signal, cleaning up..."
    rm $LOCKFILE
    exit
}

# Trap TERM signal (which Docker sends on stop) and call cleanup function
trap 'cleanup' SIGTERM

if [[ "$MODE" = "nordvpn" ]]; then
    # Check if the lockfile exists
    if [ -e "${LOCKFILE}" ]; then
        # The lockfile exists so exit the script
        echo "Lockfile exists, exiting"
        exit 1
    fi
    # Create the lockfile to signify the script is running
    touch "${LOCKFILE}"

    ln -s /usr/bin/resolvectl /usr/bin/systemd-resolve
    nordvpnd &
    echo "Started nordvpnd daemon, will sleep for 30 seconds"
    sleep 30

    # nordvpn login --token cf0664e14b89ee5db7585c811fa7805fd3da81a031d9160bddf4fb613175c960 && nordvpn connect

    echo "Now setting up nordvpn killswitch and login in"
    nordvpn set killswitch on && nordvpn set analytics off && nordvpn whitelist add subnet 192.168.1.1/24 && nordvpn login --token cf0664e14b89ee5db7585c811fa7805fd3da81a031d9160bddf4fb613175c960 && nordvpn connect
    ip route add 192.168.1.0/24 via 172.17.0.1

    echo "Sleeping for 30 seconds"
    sleep 30
    echo "Now starting check loop"
    COUNTER=0
    while true; do
        COUNTER=$((COUNTER + 1))
        RES=$(nordvpn status 2>/dev/null|grep 'Status: Connected'| tr -dc '[:alnum:]:')
        echo "Result of RES is $RES"
        if [[ "$RES" == "Status:Connected" ]]; then
            if [ $(( $COUNTER % 60 )) -eq 0 ]; then
                echo "========================================"
                nordvpn status 2>/dev/null|egrep 'Status:|Current|Transfer|Uptime'|grep -v 'version for feature MESHNET,'
            fi
            sleep 1
        else
            echo "========================================"
            echo "========================================"
            echo "========================================"
            echo "========================================"
            echo "========================================"
            nordvpn status
            echo "The connection to nordvpn is disconnected, will reconnect"
            CONNECTION_RESULT=$(nordvpn connect 2>&1| sed 's/\x1b\[[0-9;]*m//g'| sed 's/\r//g')
            echo "Connection result is:\"$CONNECTION_RESULT\""
            if [[ "$CONNECTION_RESULT" == "-Whoops! Cannot reach System Daemon." ]]; then
                echo "We will now exit!"
                exit 1
            fi
            if [[ "$CONNECTION_RESULT" == "-Whoops! /run/nordvpn/nordvpnd.sock not found." ]]; then
                echo "We will now exit!"
                exit 1
            fi
            sleep 5
            echo "Setting killswitch again ON"
            nordvpn set killswitch on
            echo "Will now sleep 10 seconds"
            sleep 10
        fi
        sleep 1
    done
elif [[ "$MODE" = "aws" || "$MODE" = "protonvpn" || "$MODE" = "hetzner" ]]; then
    echo "Create tun device"
    mkdir -p /dev/net
    mknod /dev/net/tun c 10 200
    chmod 600 /dev/net/tun

    echo "Setting firewall rules for mode $MODE"
    ufw allow in to 192.168.1.0/16
    ufw allow out to 192.168.1.0/16
    ufw allow in to 172.17.1.0/16
    ufw allow out to 172.17.1.0/16
    ufw default deny outgoing
    ufw default deny incoming

    ufw allow out to 149.34.244.205 port 443 proto tcp
    ufw allow out to 213.152.162.218 port 443 proto tcp
    ufw allow out to 213.232.87.93 port 443 proto tcp
    ufw allow out to 143.244.41.65 port 443 proto tcp
    ufw allow out to 213.232.87.95 port 443 proto tcp
    ufw allow out to 213.232.87.97 port 443 proto tcp
    ufw allow out to 52.51.20.228
    ufw allow out to 194.127.172.70
    ufw allow out to 8.8.8.8
    ufw allow out to 190.2.131.156
    ufw allow out to 5.75.173.113
    ufw allow out to 195.201.8.233

    ufw allow out on tun0 from any to any
    ufw enable

    echo "Set routing needed"
    ip route add 192.168.0.0/16 via 172.17.0.1

    echo "Starting vpn"

    if [[ "$MODE" = "protonvpn" ]]; then
        if [[ "$VPN" = "1" ]]; then
            /usr/sbin/openvpn /etc/openvpn/protonnl30udp.conf
        # elif [[ "$VPN" = "2" ]]; then
        #     /usr/sbin/openvpn /etc/openvpn/nl882tcp.conf
        # elif [[ "$VPN" = "3" ]]; then
        #     /usr/sbin/openvpn /etc/openvpn/nl883tcp.conf
        # elif [[ "$VPN" = "4" ]]; then
        #     /usr/sbin/openvpn /etc/openvpn/nl978tcp.conf
        # elif [[ "$VPN" = "5" ]]; then
        #     /usr/sbin/openvpn /etc/openvpn/nl993tcp.conf
        # elif [[ "$VPN" = "6" ]]; then
        #     /usr/sbin/openvpn /etc/openvpn/nl1008tcp.conf
        fi
    elif [[ "$MODE" = "aws" ]]; then
        /usr/sbin/openvpn /etc/openvpn/aws.conf
    elif [[ "$MODE" = "hetzner" ]]; then
        /usr/sbin/openvpn /etc/openvpn/hetzner.conf
    fi
else
    echo "IN NONE MODE, WE WILL FORWARD TRAFFIC NORMALLY"
    sleep 10000000000000
fi

cleanup