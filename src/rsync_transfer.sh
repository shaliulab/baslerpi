#! /bin/bash


DATA_DIR=$(jq -r ".videos.folder" /etc/flyhostel.conf)
LAST_EXP=$(find ${DATA_DIR} -maxdepth 2 -name metadata.yaml | sort -r | head -1 | xargs dirname | xargs basename )
REMOTE_DATA_DIR="/Dropbox/FlySleepLab_Dropbox/Data/flyhostel_data/videos"
rsync --progress --ignore-existing -Ravzr ${DATA_DIR}/./${LAST_EXP} -e ssh cv1:${REMOTE_DATA_DIR}
