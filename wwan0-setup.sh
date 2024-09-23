sudo systemctl stop ModemManager.service

sudo ip link set wwan0 down

echo 'Y' | sudo tee /sys/class/net/wwan0/qmi/raw_ip

sudo ip link set wwan0 up

sudo qmicli -d /dev/cdc-wdm0 --dms-set-operating-mode='online'

sudo qmicli -p -d /dev/cdc-wdm0 --device-open-net='net-raw-ip|net-no-qos-header' --wds-start-network="apn='vzwinternet',username='ZAXISSOLUTIONS',password='cJ6j_Q+48z?HZt',ip-type=4" --client-no-release-cid

sudo udhcpc -q -f -i wwan0

iptables -t mangle -A PREROUTING -j TTL --ttl-set 65
