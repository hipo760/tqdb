#!/bin/bash

# Source the profile script if it exists (for shell compatibility)
if [ -f /etc/profile.d/profile_tqdb.sh ]; then
    source /etc/profile.d/profile_tqdb.sh
fi

# Set defaults if variables are not set (fallback for direct script execution)
CASS_IP=${CASS_IP:-127.0.0.1}
CASS_PORT=${CASS_PORT:-9042}
D2TQ_IP=${D2TQ_IP:-192.168.56.1}
D2TQ_PORT=${D2TQ_PORT:-14568}
TQDB_DIR=${TQDB_DIR:-/home/tqdb/codes/tqdb}

mkdir -p /tmp/TQAlert/
chmod 777 /tmp/TQAlert/

echo $CASS_IP":"$CASS_PORT > /tmp/cass.info
echo $D2TQ_IP":"$D2TQ_PORT > /tmp/d2tq.info

# cd $TQDB_DIR/script_for_sys && ./demo_d2tq_server.sh > /tmp/demo_d2tq_server.log &
cd $TQDB_DIR/tools/ && python -u TQAlert.py > /tmp/TQAlert.py.log &


sleep 10

cd $TQDB_DIR/tools && ./autoIns2Cass.sh > /tmp/autoIns2Cass.log &
# cd $TQDB_DIR/tools && ./watchdogAutoIns2Cass.sh &


#su - tqdb -c "cd /home/tqdb/.ipython && ipython notebook --profile=nbserver &"
# su - tqdb -c "cd /home/tqdb/ && jupyter notebook &" 

